# cardgcalc: Python API for scripts on the Cardputer(-Adv) graphing calculator.
#
# This package also holds the calculator itself (cardgcalc.hal, .gfx, .ui,
# .apps ...); `import cardgcalc` gives scripts the API below.
#
# Screen (240x135, origin top-left)
#   cls(c), pixel(x,y[,c]), line, rect, fill_rect, circle, text, show()
#   color(r,g,b) / color((r,g,b)) / color('red') -> colour value
#   BLACK WHITE RED GREEN BLUE YELLOW ...  (colours may also be given as
#   (r,g,b) tuples or names wherever a colour is expected)
#   also: set_pixel(x,y,c),
#   get_pixel(x,y) -> (r,g,b), draw_string(s,x,y[,c[,bg]]), wait_vblank()
# Keyboard
#   get_key() -> str or None (non-blocking), wait_key() -> str,
#   key_down(name) -> bool  (names: 'a', '1', 'ENTER', 'UP' (;), 'SPACE' ...)
#   keydown(KEY_xxx) with key name constants KEY_LEFT, KEY_OK ...
# Plot
#   plot(f, xmin=-10, xmax=10, ymin=None, ymax=None)
# GPIO  (Grove: G1 G2,  EXT header: G3 G4 G5 G6 G13 G15)
#   pin_out(p, v), pin_in(p, pull=None), analog(p) -> volts, pwm(p, freq, duty%)
# Misc
#   sleep_ms(ms), sleep(s), ticks_ms(), battery() -> %
import time
from cardgcalc import hal, gfx
from cardgcalc import runner as _r
from cardgcalc.hal import rgb as _rgb

W = hal.W
H = hal.H
width = W
height = H

BLACK = _rgb(0, 0, 0)
WHITE = _rgb(255, 255, 255)
RED = _rgb(255, 60, 60)
GREEN = _rgb(60, 220, 90)
BLUE = _rgb(60, 120, 255)
YELLOW = _rgb(255, 220, 40)
CYAN = _rgb(40, 220, 230)
MAGENTA = _rgb(230, 70, 220)
ORANGE = _rgb(255, 150, 30)
GRAY = _rgb(128, 128, 128)
GREY = GRAY

# colour names accepted by color() and every drawing function
_NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 200, 0),
    "blue": (0, 0, 255), "yellow": (255, 255, 0), "cyan": (0, 255, 255),
    "magenta": (255, 0, 255), "orange": (255, 165, 0), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "purple": (128, 0, 128), "brown": (139, 69, 19), "pink": (255, 160, 200),
}

G1 = 1
G2 = 2
G3 = 3
G4 = 4
G5 = 5
G6 = 6
G13 = 13
G15 = 15
PINS = (1, 2, 3, 4, 5, 6, 13, 15)
if hal.MODEL == "cardputer":
    PINS = (1, 2)  # no EXT header: G3-G6/G13/G15 read the keyboard


def _hw():
    # The calculator initialises the hardware at boot; from the REPL or
    # `mpremote run` (no calculator running) do it on first use.
    if hal.display is None or hal.keyboard is None:
        hal.init()


def _fb():
    _hw()
    _r.mark_dirty()
    return hal.display.fb


def _c(c):
    if isinstance(c, str):
        c = _NAMED.get(c.lower(), (0, 0, 0))
    if isinstance(c, (tuple, list)):
        return _rgb(int(c[0]), int(c[1]), int(c[2]))
    return int(c)


def color(r, g=None, b=None):
    """Colour value from r, g, b (0..255), an (r,g,b) tuple or a name."""
    if g is None:
        return _c(r)
    return _rgb(int(r), int(g), int(b))


# ---- drawing --------------------------------------------------------------
def cls(c=BLACK):
    _fb().fill(_c(c))


clear = cls


def pixel(x, y, c=None):
    if c is None:
        _hw()
        return hal.display.fb.pixel(int(x), int(y))
    _fb().pixel(int(x), int(y), _c(c))


def line(x0, y0, x1, y1, c=WHITE):
    _fb().line(int(x0), int(y0), int(x1), int(y1), _c(c))


def hline(x, y, w, c=WHITE):
    _fb().hline(int(x), int(y), int(w), _c(c))


def vline(x, y, h, c=WHITE):
    _fb().vline(int(x), int(y), int(h), _c(c))


def rect(x, y, w, h, c=WHITE):
    _fb().rect(int(x), int(y), int(w), int(h), _c(c))


def fill_rect(x, y, w, h, c=WHITE):
    _fb().fill_rect(int(x), int(y), int(w), int(h), _c(c))


def circle(x, y, r, c=WHITE, fill=False):
    _fb().ellipse(int(x), int(y), int(r), int(r), _c(c), fill)


def ellipse(x, y, rx, ry, c=WHITE, fill=False):
    _fb().ellipse(int(x), int(y), int(rx), int(ry), _c(c), fill)


def poly(points, c=WHITE, fill=False):
    import array

    a = array.array("h")
    for p in points:
        a.append(int(p[0]))
        a.append(int(p[1]))
    _fb().poly(0, 0, a, _c(c), fill)


def _ink(c):
    # pure black equals the transparent key used by gfx text blits
    return hal.rgb(0, 0, 8) if c == 0 else c


def text(s, x, y, c=WHITE, bg=None, font="normal"):
    """Draw text. font: 'small' 5x8, 'normal' 6x10, 'medium' 6x13, 'large' 10x20.
    Returns the x coordinate after the text."""
    _hw()
    _r.mark_dirty()
    return gfx.font(font).text(str(s), int(x), int(y), _ink(_c(c)), None if bg is None else _c(bg))


def text_width(s, font="normal"):
    return gfx.font(font).width(str(s))


# drawing with (r, g, b) colours
def set_pixel(x, y, c):
    _fb().pixel(int(x), int(y), _c(c))


def get_pixel(x, y):
    """Colour at (x, y) as an (r, g, b) tuple."""
    _hw()
    return hal.unrgb(hal.display.fb.pixel(int(x), int(y)))


def draw_string(s, x, y, c=(0, 0, 0), bg=(255, 255, 255)):
    _hw()
    _r.mark_dirty()
    gfx.font("medium").text(str(s), int(x), int(y), _c(c), _c(bg))


def wait_vblank():
    _hw()
    _r.check()
    if _r.dirty:
        _r.show()


def show():
    """Push the frame buffer to the display now."""
    _hw()
    _r.check()
    _r.show()


def brightness(pct):
    _hw()
    hal.display.set_brightness(pct)


# ---- keyboard --------------------------------------------------------------
_held = set()
_ARROWS = {"UP": ";", "DOWN": ".", "LEFT": ",", "RIGHT": "/", "SPACE": " ", "ESC": "`"}


def _install_held():
    _hw()
    kb = hal.keyboard
    if getattr(kb, "_nc_held", False):
        return
    press = kb._press
    release = kb._release

    def _p(row, col):
        _held.add(_cap(row, col))
        press(row, col)

    def _rl(row, col):
        _held.discard(_cap(row, col))
        release(row, col)

    kb._press = _p
    kb._release = _rl
    kb._nc_held = True


def _cap(row, col):
    cap = hal._LAYOUT[row][col]
    if cap[0] == "*":
        return cap[1:]
    if len(cap) == 2 and cap != hal.BS:
        return cap[0]
    return cap


def _pump():
    kb = hal.keyboard
    if hal.IS_DEVICE:
        _r.kb_busy += 1
        try:
            for ev in kb._raw_events():
                if ev:
                    kb.feed(ev)
        finally:
            _r.kb_busy -= 1


def _name(k):
    if k is None:
        return None
    if _r._is_break(k):
        raise KeyboardInterrupt
    _r.pending = False
    return k.key


def get_key():
    """Next key press as a string ('a', 'A', '1', 'ENTER', 'UP', ...) or None."""
    _hw()
    _r.check()
    if _r.dirty:
        show()
    _r.kb_busy += 1
    try:
        return _name(hal.keyboard.poll())
    finally:
        _r.kb_busy -= 1


def wait_key():
    """Wait for a key press and return it as a string."""
    _hw()
    _r.check()
    if _r.dirty:
        show()
    _r.kb_busy += 1
    try:
        return _name(hal.wait_key())
    finally:
        _r.kb_busy -= 1


def key_down(name):
    """True while the key is held.  name: 'a', '1', 'ENTER', 'BS', 'TAB',
    'SPACE', 'UP'/'DOWN'/'LEFT'/'RIGHT' (the ; . , / keys), 'SHIFT', 'FN',
    'CTRL', 'OPT', 'ALT'."""
    _install_held()
    _r.check()
    _pump()
    n = _ARROWS.get(name, name)
    if len(n) == 1:
        n = n.lower()
    return n in _held


def keys_down():
    _install_held()
    _pump()
    return set(_held)


# keyboard with key name constants: keydown(KEY_xxx).
# Arrows are the ; , . / keys, OK/EXE = Enter, BACK = ` (esc),
# BACKSPACE = BS, SHIFT = shift, ALPHA = alt, digits/operators as printed.
keydown = key_down

KEY_LEFT = ","
KEY_UP = ";"
KEY_DOWN = "."
KEY_RIGHT = "/"
KEY_OK = "ENTER"
KEY_BACK = "`"
KEY_HOME = "TAB"
KEY_ONOFF = "\\"
KEY_SHIFT = "SHIFT"
KEY_ALPHA = "ALT"
KEY_XNT = "x"
KEY_VAR = "v"
KEY_TOOLBOX = "t"
KEY_BACKSPACE = "BS"
KEY_EXP = "e"
KEY_LN = "n"
KEY_LOG = "l"
KEY_IMAGINARY = "i"
KEY_COMMA = "'"
KEY_POWER = "p"
KEY_SINE = "s"
KEY_COSINE = "c"
KEY_TANGENT = "a"
KEY_PI = "o"
KEY_SQRT = "q"
KEY_SQUARE = "w"
KEY_SEVEN = "7"
KEY_EIGHT = "8"
KEY_NINE = "9"
KEY_LEFTPARENTHESIS = "["
KEY_RIGHTPARENTHESIS = "]"
KEY_FOUR = "4"
KEY_FIVE = "5"
KEY_SIX = "6"
KEY_MULTIPLICATION = "m"
KEY_DIVISION = "d"
KEY_ONE = "1"
KEY_TWO = "2"
KEY_THREE = "3"
KEY_PLUS = "="
KEY_MINUS = "-"
KEY_ZERO = "0"
KEY_DOT = "k"
KEY_EE = "z"
KEY_ANS = "b"
KEY_EXE = "ENTER"


# ---- time -----------------------------------------------------------------
def sleep_ms(ms):
    if not hal.IS_DEVICE:
        _r.check()
        return
    end = time.ticks_add(time.ticks_ms(), int(ms))
    while True:
        _r.check()
        if _r.dirty:
            show()
        left = time.ticks_diff(end, time.ticks_ms())
        if left <= 0:
            return
        time.sleep_ms(min(left, 20))


def sleep(s):
    sleep_ms(int(s * 1000))


def ticks_ms():
    return time.ticks_ms()


def battery():
    return hal.battery_pct()


# ---- plotting ----------------------------------------------------------------
def plot(f, xmin=-10, xmax=10, ymin=None, ymax=None, c=None, wait=True):
    """Quick plot of y=f(x).  Auto-scales y if ymin/ymax are omitted."""
    _hw()
    n = W
    xs = [xmin + (xmax - xmin) * i / (n - 1) for i in range(n)]
    ys = []
    for x in xs:
        try:
            y = f(x)
            if isinstance(y, complex):
                y = None
        except Exception:
            y = None
        ys.append(y)
    good = [y for y in ys if y is not None and y == y and abs(y) < 1e30]
    if ymin is None or ymax is None:
        if good:
            lo = min(good)
            hi = max(good)
        else:
            lo, hi = -1, 1
        if hi - lo < 1e-12:
            lo -= 1
            hi += 1
        pad = (hi - lo) * 0.05
        ymin = lo - pad if ymin is None else ymin
        ymax = hi + pad if ymax is None else ymax
    fb = _fb()
    fb.fill(gfx.BG)

    def sy(y):
        return int((ymax - y) * (H - 1) / (ymax - ymin))

    def sx(x):
        return int((x - xmin) * (W - 1) / (xmax - xmin))

    if ymin <= 0 <= ymax:
        fb.hline(0, sy(0), W, gfx.AXIS)
    if xmin <= 0 <= xmax:
        fb.vline(sx(0), 0, H, gfx.AXIS)
    col = gfx.SERIES[0] if c is None else _c(c)
    prev = None
    for i in range(n):
        y = ys[i]
        if y is None or y != y:
            prev = None
            continue
        py = sy(y)
        if prev is not None and abs(prev - py) < 4 * H:
            fb.line(i - 1, prev, i, py, col)
        else:
            fb.pixel(i, py, col)
        prev = py
    sf = gfx.font("small")
    sf.text("x:[%g,%g] y:[%.4g,%.4g]" % (xmin, xmax, ymin, ymax), 1, 1, gfx.DIM)
    show()
    if wait:
        wait_key()


# ---- GPIO ---------------------------------------------------------------------
_pins = {}
_pwms = {}


def _machine():
    try:
        import machine

        return machine
    except ImportError:
        raise OSError("GPIO not available in the simulator")


def pin_out(p, v=None):
    """Configure p as output; set value v (0/1) if given. Returns machine.Pin."""
    m = _machine()
    pw = _pwms.pop(p, None)
    if pw:
        pw.deinit()
    pn = _pins.get(p)
    if pn is None or pn[1] != "out":
        pn = (m.Pin(p, m.Pin.OUT), "out")
        _pins[p] = pn
    if v is not None:
        pn[0].value(1 if v else 0)
    return pn[0]


def pin_in(p, pull=None):
    """Read a digital input.  pull: None, 'up' or 'down'."""
    m = _machine()
    pl = {None: None, "up": m.Pin.PULL_UP, "down": m.Pin.PULL_DOWN}[pull]
    key = "in%s" % pull
    pn = _pins.get(p)
    if pn is None or pn[1] != key:
        pn = (m.Pin(p, m.Pin.IN, pl), key)
        _pins[p] = pn
    return pn[0].value()


def analog(p):
    """Voltage on pin p (0..~3.1 V)."""
    m = _machine()
    a = m.ADC(m.Pin(p), atten=m.ADC.ATTN_11DB)
    return a.read_uv() / 1000000


def pwm(p, freq=1000, duty=50):
    """PWM output on p: freq in Hz, duty in percent.  duty=None stops."""
    m = _machine()
    pw = _pwms.get(p)
    if duty is None:
        if pw:
            pw.deinit()
            del _pwms[p]
        return None
    d = int(max(0, min(100, duty)) * 655.35)
    if pw is None:
        pw = m.PWM(m.Pin(p), freq=int(freq), duty_u16=d)
        _pwms[p] = pw
    else:
        pw.freq(int(freq))
        pw.duty_u16(d)
    return pw


def tone(p, freq, ms):
    """Square-wave tone on a pin (e.g. a piezo buzzer on G1)."""
    pwm(p, freq, 50)
    try:
        sleep_ms(ms)
    finally:
        pwm(p, duty=None)


def i2c_grove(freq=100000):
    """machine.I2C on the Grove port (SDA=G2, SCL=G1)."""
    m = _machine()
    return m.SoftI2C(scl=m.Pin(1), sda=m.Pin(2), freq=freq)
