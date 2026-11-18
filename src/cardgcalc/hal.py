# Hardware abstraction for the M5Stack Cardputer-Adv and Cardputer.
#
# Display : ST7789V2 240x135, SPI (SCK=36, MOSI=35, DC=34, CS=37, RST=33, BL=38)
# Keyboard: 4x14 layout
#   Cardputer-Adv: TCA8418 on I2C (SDA=8, SCL=9, INT=11, addr 0x34)
#   Cardputer    : 74HC138 row select (A0=8, A1=9, A2=11) and 7 column inputs
#                  with pull-ups (13, 15, 3, 4, 5, 6, 7), active low
# microSD : SPI (SCK=40, MOSI=14, MISO=39, CS=12)
# RGB LED : WS2812 (GRB order) on G21, both models
#
# Which model the firmware is for is fixed at build time by the frozen
# module cardgcalc_board (firmware/boards/CARD_GCALC/model_*).
#
# On non-ESP32 platforms (unix MicroPython) a simulator backend is used so
# the UI can be tested on the host: see tools/sim.py.
import sys
import time
import framebuf

W = 240
H = 135
IS_DEVICE = sys.platform == "esp32"

try:
    import cardgcalc_board as _board

    MODEL = _board.MODEL  # "adv" or "cardputer"
    MODEL_NAME = _board.NAME
except ImportError:
    MODEL = "adv"
    MODEL_NAME = "M5Stack Cardputer-Adv"


def rgb(r, g, b):
    """RGB888 -> RGB565 value as stored in the frame buffer.

    The ST7789 expects big-endian pixels while framebuf stores little-endian,
    so colours are byte-swapped once here and the buffer can be sent as is.
    """
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


def unrgb(c):
    c = ((c & 0xFF) << 8) | (c >> 8)
    return ((c >> 8) & 0xF8, (c >> 3) & 0xFC, (c << 3) & 0xF8)


# Backlight PWM frequency.  The Cardputer's backlight stays dark when the
# PWM is 1 kHz or more (it lights at 200-500 Hz).
BL_FREQ = 256 if MODEL == "cardputer" else 2000


class Display:
    def __init__(self):
        self.buf = bytearray(W * H * 2)
        self.fb = framebuf.FrameBuffer(self.buf, W, H, framebuf.RGB565)
        self._mv = memoryview(self.buf)
        self._bl = None
        self.brightness = 80
        if IS_DEVICE:
            self._init_panel()

    # ---- ST7789 -----------------------------------------------------
    def _init_panel(self):
        from machine import Pin, SPI, PWM

        self.spi = SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), polarity=0, phase=0)
        self.dc = Pin(34, Pin.OUT, value=0)
        self.cs = Pin(37, Pin.OUT, value=1)
        self.rst = Pin(33, Pin.OUT, value=1)
        self.rst(0)
        time.sleep_ms(10)
        self.rst(1)
        time.sleep_ms(120)
        cmd = self._cmd
        cmd(0x01)  # SWRESET
        time.sleep_ms(150)
        cmd(0x11)  # SLPOUT
        time.sleep_ms(120)
        cmd(0x3A, b"\x55")  # COLMOD 16bit
        cmd(0x36, b"\x60")  # MADCTL: MX|MV (landscape)
        cmd(0x21)  # INVON (IPS panel)
        cmd(0x13)  # NORON
        cmd(0x29)  # DISPON
        self._bl = PWM(Pin(38), freq=BL_FREQ, duty_u16=0)
        self.fb.fill(0)
        self.show()
        self.set_brightness(self.brightness)

    def _cmd(self, c, data=None):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes((c,)))
        if data:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def _window(self, x, y, w, h):
        x += 40
        y += 53
        self._cmd(0x2A, bytes((x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF)))
        self._cmd(0x2B, bytes((y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF)))

    def show(self):
        if not IS_DEVICE:
            return
        self._window(0, 0, W, H)
        self.cs(0)
        self.dc(0)
        self.spi.write(b"\x2c")
        self.dc(1)
        self.spi.write(self.buf)
        self.cs(1)

    def show_rect(self, x, y, w, h):
        """Push only a rectangle of the frame buffer to the panel."""
        if not IS_DEVICE:
            return
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        if x + w > W:
            w = W - x
        if y + h > H:
            h = H - y
        if w <= 0 or h <= 0:
            return
        if w == W:
            self._window(0, y, W, h)
            self.cs(0)
            self.dc(0)
            self.spi.write(b"\x2c")
            self.dc(1)
            self.spi.write(self._mv[y * W * 2 : (y + h) * W * 2])
            self.cs(1)
            return
        self._window(x, y, w, h)
        self.cs(0)
        self.dc(0)
        self.spi.write(b"\x2c")
        self.dc(1)
        mv = self._mv
        for r in range(y, y + h):
            o = (r * W + x) * 2
            self.spi.write(mv[o : o + w * 2])
        self.cs(1)

    def set_brightness(self, pct):
        self.brightness = pct
        if self._bl is not None:
            pct = max(0, min(100, pct))
            self._bl.duty_u16(int(pct * 655.35))

    def sleep(self, on):
        if IS_DEVICE:
            self._cmd(0x10 if on else 0x11)
            if self._bl is not None:
                self._bl.duty_u16(0 if on else int(self.brightness * 655.35))


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

# Modifier bits
SHIFT = 1
CTRL = 2
OPT = 4
ALT = 8
FN = 16

# Special key names
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
ENTER = "ENTER"
BS = "BS"
DEL = "DEL"
ESC = "ESC"
TAB = "TAB"
SPACE = " "

# Physical layout (4 rows x 14 columns).  Tuples: (normal, shifted)
_LAYOUT = (
    ("`~", "1!", "2@", "3#", "4$", "5%", "6^", "7&", "8*", "9(", "0)", "-_", "=+", BS),
    (TAB, "qQ", "wW", "eE", "rR", "tT", "yY", "uU", "iI", "oO", "pP", "[{", "]}", "\\|"),
    ("*FN", "*SHIFT", "aA", "sS", "dD", "fF", "gG", "hH", "jJ", "kK", "lL", ";:", "'\"", ENTER),
    ("*CTRL", "*OPT", "*ALT", "zZ", "xX", "cC", "vV", "bB", "nN", "mM", ",<", ".>", "/?", " "),
)
_MODBITS = {"*FN": FN, "*SHIFT": SHIFT, "*CTRL": CTRL, "*OPT": OPT, "*ALT": ALT}
# Fn layer
_FN = {
    "`": ESC, ";": UP, ".": DOWN, ",": LEFT, "/": RIGHT, BS: DEL,
    "1": "F1", "2": "F2", "3": "F3", "4": "F4", "5": "F5", "6": "F6",
    "7": "F7", "8": "F8", "9": "F9", "0": "F10",
    "[": "PGUP", "]": "PGDN", "-": "HOME", "=": "END",
}
# Keys which act as arrows when the focused widget does not take text.
NAV = {";": UP, ".": DOWN, ",": LEFT, "/": RIGHT}


class Key:
    """A key press.

    key  : str. Printable character (shift applied) or a special key name
           (UP, DOWN, LEFT, RIGHT, ENTER, BS, DEL, ESC, TAB, F1..F10, ...).
    base : the unshifted character printed on the keycap ('a', '1', ';' ...)
    mods : modifier bitmask (SHIFT/CTRL/OPT/ALT/FN), including latched ones.
    """

    __slots__ = ("key", "base", "mods")

    def __init__(self, key, base, mods):
        self.key = key
        self.base = base
        self.mods = mods

    def nav(self):
        """Key interpreted for navigation (; , . / act as arrows)."""
        if self.mods & (CTRL | OPT | ALT):
            return self.key
        return NAV.get(self.key, self.key)

    def __repr__(self):
        return "Key(%r,%r,%d)" % (self.key, self.base, self.mods)


class Keyboard:
    REPEAT_DELAY = 450
    REPEAT_RATE = 70

    def __init__(self):
        self.held = 0  # physically held modifiers
        self.latched = 0  # one-shot modifiers (tap a modifier key)
        self.locked = 0  # locked modifiers (tap twice)
        self._tap = None  # modifier pressed with no other key yet
        self.queue = []
        self._rep = None  # (pos, next_ms)
        self.on_mods = None  # callback when latch state changes
        self.i2c = None
        self._events = None
        if IS_DEVICE:
            if MODEL == "cardputer":
                self._init_matrix()
            else:
                self._init_tca()

    # ---- Cardputer-Adv: TCA8418 -------------------------------------
    def _init_tca(self):
        from machine import I2C, Pin

        self.i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400000)
        self.addr = 0x34
        w = self._w
        try:
            w(0x1D, 0x7F)  # KP_GPIO1: R0..R6 keypad
        except OSError:
            self.i2c = None
            raise RuntimeError("keyboard not found: firmware for " + MODEL_NAME)
        w(0x1E, 0xFF)  # KP_GPIO2: C0..C7 keypad
        w(0x1F, 0x00)  # KP_GPIO3
        w(0x01, 0x01)  # CFG: KE_IEN
        # flush FIFO
        self._b1 = bytearray(1)
        for _ in range(16):
            if not self._r(0x03) & 0x0F:
                break
            self._r(0x04)
        w(0x02, 0x1F)
        self.int_pin = Pin(11, Pin.IN)
        self._events = self._tca_events

    def _w(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes((val,)))

    def _r(self, reg):
        self.i2c.readfrom_mem_into(self.addr, reg, self._b1)
        return self._b1[0]

    def _raw_events(self):
        """Pending TCA8418 event bytes."""
        out = []
        try:
            n = self._r(0x03) & 0x0F
            while n:
                out.append(self._r(0x04))
                n -= 1
                if not n:
                    n = self._r(0x03) & 0x0F
            if out:
                self._w(0x02, 0x01)
        except OSError:
            pass
        return out

    @staticmethod
    def decode(ev):
        """TCA8418 event byte -> (pressed, row, col) in the 4x14 layout."""
        v = (ev & 0x7F) - 1
        r = v // 10
        c = v % 10
        col = r * 2 + (1 if c > 3 else 0)
        row = c % 4
        return bool(ev & 0x80), row, col

    def _tca_events(self):
        for ev in self._raw_events():
            self.feed(ev)

    # ---- Cardputer: 74HC138 GPIO matrix -----------------------------
    MX_OUT = (8, 9, 11)  # 74HC138 A0, A1, A2
    MX_IN = (13, 15, 3, 4, 5, 6, 7)  # column inputs, bit 0..6
    MX_PERIOD = 5  # ms between scans
    MX_RELEASE = 2  # scans a key must read released before it counts

    def _init_matrix(self):
        from machine import Pin

        self._mx_out = [Pin(p, Pin.OUT, value=0) for p in self.MX_OUT]
        self._mx_in = [Pin(p, Pin.IN, Pin.PULL_UP) for p in self.MX_IN]
        self._mx_down = {}  # (row, col) -> scans seen released (0 = held)
        self._mx_t = time.ticks_ms()
        self._events = self._matrix_events

    @staticmethod
    def matrix_pos(i, j):
        """74HC138 output i (0..7) and input bit j (0..6) -> (row, col)."""
        return 3 - (i & 3), j * 2 + (0 if i > 3 else 1)

    def _scan_matrix(self):
        down = []
        a0, a1, a2 = self._mx_out
        ins = self._mx_in
        for i in range(8):
            a0(i & 1)
            a1((i >> 1) & 1)
            a2(i >> 2)
            for j in range(7):
                if not ins[j]():
                    down.append(self.matrix_pos(i, j))
        return down

    def _matrix_events(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._mx_t) < self.MX_PERIOD:
            return
        self._mx_t = now
        self.feed_matrix(self._scan_matrix())

    def feed_matrix(self, down):
        """Update from one scan: down = list of (row, col) read as pressed.

        A press counts at once; a release only after MX_RELEASE scans in a
        row read the key as up, which hides contact bounce.
        """
        st = self._mx_down
        for pos in list(st):
            if pos in down:
                st[pos] = 0
            else:
                st[pos] += 1
                if st[pos] >= self.MX_RELEASE:
                    del st[pos]
                    self._release(*pos)
        new = [p for p in down if p not in st]
        # modifiers first, so that "shift+a" pressed together reads as "A"
        new.sort(key=lambda p: 0 if _LAYOUT[p[0]][p[1]] in _MODBITS else 1)
        for pos in new:
            st[pos] = 0
            self._press(*pos)

    def mods(self):
        return self.held | self.latched | self.locked

    def _press(self, row, col):
        cap = _LAYOUT[row][col]
        mb = _MODBITS.get(cap)
        if mb:
            self.held |= mb
            self._tap = mb
            return
        self._tap = None
        mods = self.mods()
        if len(cap) == 2 and cap[0] != "*" and cap not in (BS,):
            base = cap[0]
            key = cap[1] if mods & SHIFT else cap[0]
        else:
            base = cap
            key = cap
        if mods & FN:
            key = _FN.get(base, key)
        self.queue.append(Key(key, base, mods))
        self._rep = ((row, col), time.ticks_add(time.ticks_ms(), self.REPEAT_DELAY))
        if self.latched:
            self.latched = 0
            if self.on_mods:
                self.on_mods()

    def _release(self, row, col):
        cap = _LAYOUT[row][col]
        mb = _MODBITS.get(cap)
        if mb:
            self.held &= ~mb
            if self._tap == mb:
                # A modifier was tapped on its own: latch / lock / clear.
                if self.locked & mb:
                    self.locked &= ~mb
                elif self.latched & mb:
                    self.latched &= ~mb
                    self.locked |= mb
                else:
                    self.latched |= mb
                if self.on_mods:
                    self.on_mods()
            self._tap = None
            return
        if self._rep and self._rep[0] == (row, col):
            self._rep = None

    def feed(self, ev):
        p, r, c = self.decode(ev)
        if p:
            self._press(r, c)
        else:
            self._release(r, c)

    def clear_mods(self):
        self.latched = 0
        self.locked = 0

    def poll(self):
        """Read pending hardware events; return a Key or None."""
        if self._events is not None:
            self._events()
            if not self.queue and self._rep:
                now = time.ticks_ms()
                pos, t = self._rep
                if time.ticks_diff(now, t) >= 0:
                    self._rep = None
                    saved = self.latched
                    self._press(pos[0], pos[1])
                    self.latched = saved
                    self._rep = (pos, time.ticks_add(now, self.REPEAT_RATE))
        if self.queue:
            return self.queue.pop(0)
        return None

    def pressed_now(self):
        return bool(self.queue)


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
display = None
keyboard = None
_idle_hooks = []


def init():
    """Set up the display and keyboard.

    Raises RuntimeError when the keyboard is missing, i.e. the firmware is
    for the other Cardputer model (the display is set up already).
    """
    global display, keyboard
    if display is None:
        display = Display()
    if keyboard is None:
        keyboard = Keyboard()
    return display, keyboard


def add_idle_hook(fn):
    _idle_hooks.append(fn)


def wait_key(timeout_ms=-1):
    """Block until a key is pressed.  Returns Key, or None on timeout."""
    kb = keyboard
    t0 = time.ticks_ms()
    while True:
        k = kb.poll()
        if k is not None:
            return k
        for h in _idle_hooks:
            h()
        if timeout_ms >= 0 and time.ticks_diff(time.ticks_ms(), t0) >= timeout_ms:
            return None
        if IS_DEVICE:
            time.sleep_ms(10)
        else:
            sim_idle()


def sim_idle():
    # Replaced by the simulator (tools/sim.py).
    raise SystemExit("no more keys")


def battery_pct():
    """Battery level estimate (0-100) from the ADC on G10, or None."""
    if not IS_DEVICE:
        return 87
    try:
        from machine import ADC, Pin

        adc = ADC(Pin(10), atten=ADC.ATTN_11DB)
        mv = adc.read_uv() * 2 // 1000  # 1:2 divider
        pct = (mv - 3300) * 100 // (4150 - 3300)
        return max(0, min(100, pct))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# RGB LED (WS2812 on G21)
# ---------------------------------------------------------------------------
LED_PIN = 21
_led_pin = None
_led_rgb = (0, 0, 0)
_led_level = 100  # brightness scale, percent
led_used = False


def _led_send():
    if not IS_DEVICE:
        return
    global _led_pin
    import machine

    if _led_pin is None:
        _led_pin = machine.Pin(LED_PIN, machine.Pin.OUT, value=0)
    r, g, b = _led_rgb
    k = _led_level
    # WS2812 timing at 800 kHz: (T0H, T0L, T1H, T1L) in ns
    machine.bitstream(_led_pin, 0, (400, 850, 800, 450),
                      bytearray((g * k // 100, r * k // 100, b * k // 100)))


def _byte(v):
    v = int(v)
    return 0 if v < 0 else 255 if v > 255 else v


def led_set(r, g, b):
    """Light the RGB LED with r, g, b (0-255); (0, 0, 0) turns it off."""
    global _led_rgb, led_used
    _led_rgb = (_byte(r), _byte(g), _byte(b))
    led_used = True
    _led_send()


def led_get():
    return _led_rgb


def led_level(pct=None):
    """Brightness scale of the LED in percent (applied to every colour);
    returns the current value."""
    global _led_level
    if pct is not None:
        _led_level = max(0, min(100, int(pct)))
        _led_send()
    return _led_level


def led_reset():
    """Turn the LED off and restore full scale if a script used it."""
    global _led_level, led_used
    if not led_used:
        return
    _led_level = 100
    try:
        led_set(0, 0, 0)
    except Exception:
        pass
    led_used = False
