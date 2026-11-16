# GPIO: interactive pin panel for the Grove port and the EXT header.
#
#   ;/. (fn) select pin    Enter / F1  mode menu
#   Space / F2  toggle OUT    +/- PWM duty ±5%   F3 PWM freq/duty
#   F4 I2C scan    F5 reset all pins    Esc  exit (pins are released)
import gc
from cardgcalc import hal, gfx, ui
from cardgcalc.i18n import T
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC

try:
    import machine
    from machine import Pin

    _HW = hasattr(machine, "Pin") and hal.IS_DEVICE
except ImportError:
    machine = None
    _HW = False

# (gpio, location)
PINS = (
    (1, "Grove W"),
    (2, "Grove Y"),
    (3, "EXT 1"),
    (4, "EXT 3"),
    (6, "EXT 5"),
    (5, "EXT 13"),
    (13, "EXT 12"),
    (15, "EXT 14"),
)
MODES = ("-", "IN", "IN-PU", "IN-PD", "OUT", "ADC", "PWM")
I2C_NAMES = {0x34: "TCA8418 keyboard", 0x18: "ES8311 audio", 0x68: "BMI270 IMU", 0x69: "BMI270 IMU",
             0x3C: "OLED", 0x76: "BME280/BMP", 0x77: "BME/BMP", 0x40: "INA219/SHT", 0x44: "SHT3x",
             0x38: "AHT20", 0x29: "VL53L0X/TCS", 0x48: "ADS1115", 0x5A: "MLX90614", 0x57: "MAX30102",
             0x23: "BH1750", 0x70: "TCA9548A"}


class P:
    def __init__(self, gpio, loc):
        self.gpio = gpio
        self.loc = loc
        self.mode = "-"
        self.out = 0
        self.freq = 1000
        self.duty = 50
        self.obj = None
        self.val = None

    def release(self):
        if self.obj is not None and self.mode == "PWM":
            try:
                self.obj.deinit()
            except Exception:
                pass
        self.obj = None
        if _HW and self.mode != "-":
            try:
                Pin(self.gpio, Pin.IN)
            except Exception:
                pass
        self.mode = "-"
        self.val = None

    def set_mode(self, m):
        self.release()
        self.mode = m
        if not _HW or m == "-":
            return
        g = self.gpio
        try:
            if m == "IN":
                self.obj = Pin(g, Pin.IN)
            elif m == "IN-PU":
                self.obj = Pin(g, Pin.IN, Pin.PULL_UP)
            elif m == "IN-PD":
                self.obj = Pin(g, Pin.IN, Pin.PULL_DOWN)
            elif m == "OUT":
                self.obj = Pin(g, Pin.OUT, value=self.out)
            elif m == "ADC":
                self.obj = machine.ADC(Pin(g), atten=machine.ADC.ATTN_11DB)
            elif m == "PWM":
                self.obj = machine.PWM(Pin(g), freq=self.freq, duty_u16=int(self.duty * 655.35))
        except Exception as e:
            self.mode = "-"
            self.obj = None
            ui.error("G%d %s: %s" % (g, m, e))

    def read(self):
        if not _HW or self.obj is None:
            self.val = None
            return
        try:
            if self.mode.startswith("IN"):
                self.val = self.obj.value()
            elif self.mode == "OUT":
                self.val = self.out
            elif self.mode == "ADC":
                self.val = self.obj.read_uv() / 1000000
        except Exception:
            self.val = None

    def value_str(self):
        m = self.mode
        if m == "-":
            return ""
        if m == "OUT":
            return "HIGH" if self.out else "LOW"
        if m == "PWM":
            return "%dHz %d%%" % (self.freq, self.duty)
        if self.val is None:
            return "n/a"
        if m == "ADC":
            return "%.3f V" % self.val
        return "HIGH" if self.val else "LOW"

    def toggle(self):
        if self.mode != "OUT":
            self.set_mode("OUT")
        self.out ^= 1
        if self.obj is not None:
            self.obj.value(self.out)

    def set_pwm(self, freq=None, duty=None):
        if freq is not None:
            self.freq = max(1, min(40000000, int(freq)))
        if duty is not None:
            self.duty = max(0, min(100, int(duty)))
        if self.mode != "PWM":
            self.set_mode("PWM")
        elif self.obj is not None:
            self.obj.freq(self.freq)
            self.obj.duty_u16(int(self.duty * 655.35))


def i2c_scan():
    lines = []
    if not _HW:
        ui.message("I2C scan", "n/a in the simulator")
        return
    ui.busy("Scanning I2C...")
    try:
        bus = machine.SoftI2C(scl=Pin(1), sda=Pin(2), freq=100000)
        found = bus.scan()
        lines.append("Grove (SDA=G2, SCL=G1):")
        if not found:
            lines.append("  " + T("no devices"))
        for a in found:
            lines.append("  0x%02X %s" % (a, I2C_NAMES.get(a, "")))
        Pin(1, Pin.IN)
        Pin(2, Pin.IN)
    except Exception as e:
        lines.append("Grove: " + T("error") + " %s" % e)
    try:
        kb = hal.keyboard
        bus = getattr(kb, "i2c", None)
        if bus is not None:
            found = bus.scan()
            lines.append(T("Internal") + " (SDA=G8, SCL=G9):")
            for a in found:
                lines.append("  0x%02X %s" % (a, I2C_NAMES.get(a, "")))
    except Exception as e:
        lines.append(T("Internal") + ": " + T("error") + " %s" % e)
    ui.text_view("I2C scan", lines)


class Gpio:
    def __init__(self):
        self.pins = [P(g, l) for g, l in PINS]
        self.sel = 0

    def draw(self):
        f = gfx.font("normal")
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("GPIO", "" if _HW else "sim")
        y0 = ui.TOP + 1
        rowh = 12
        # header
        sf = gfx.font("small")
        for hx, ht in ((4, "PIN"), (34, "WHERE"), (100, "MODE"), (150, "VALUE")):
            sf.text(T(ht), hx, y0, gfx.DIM)
        y0 += 10
        for i, p in enumerate(self.pins):
            y = y0 + i * rowh
            if y + rowh > ui.BOT:
                break
            if i == self.sel:
                fb.fill_rect(0, y - 1, ui.W, rowh, gfx.SEL)
            f.text("G%d" % p.gpio, 4, y + 1, gfx.ACCENT)
            f.text(f.clip(T(p.loc), 64), 34, y + 1, gfx.DIM if i != self.sel else gfx.FG)
            f.text(p.mode, 100, y + 1, gfx.FG)
            v = p.value_str()
            col = gfx.FG
            if v == "HIGH":
                col = gfx.OK
            elif v == "LOW":
                col = gfx.DIM
            elif p.mode == "ADC":
                col = gfx.CYAN
            elif p.mode == "PWM":
                col = gfx.MAGENTA
            f.text(v, 150, y + 1, col)
            if p.mode == "ADC" and p.val is not None:
                w = int(min(1.0, p.val / 3.1) * 30)
                fb.fill_rect(ui.W - 34, y + 3, 30, 5, gfx.PANEL2)
                fb.fill_rect(ui.W - 34, y + 3, w, 5, gfx.CYAN)
        ui.softkeys(["Mode", "Toggle", "PWM", "I2C", "Reset", ""])
        gfx.show()

    def mode_menu(self):
        p = self.pins[self.sel]
        i = ui.choose(T("G%d (%s) mode") % (p.gpio, T(p.loc)), list(MODES), p.mode)
        if i is not None:
            p.set_mode(MODES[i])

    def pwm_dialog(self):
        p = self.pins[self.sel]
        fr = ui.input_number(T("G%d PWM frequency (Hz)") % p.gpio, p.freq)
        if fr is None:
            return
        du = ui.input_number(T("G%d duty (0-100 %%)") % p.gpio, p.duty)
        if du is None:
            return
        try:
            p.set_pwm(fr, du)
        except Exception as e:
            ui.error(str(e))

    def run(self):
        try:
            while True:
                for p in self.pins:
                    p.read()
                self.draw()
                k = hal.wait_key(100 if _HW else -1)
                if k is None:
                    continue
                kk = k.nav()
                fk = ui.fkey(k)
                p = self.pins[self.sel]
                if kk == UP:
                    self.sel = (self.sel - 1) % len(self.pins)
                elif kk == DOWN:
                    self.sel = (self.sel + 1) % len(self.pins)
                elif kk == ENTER or fk == 0:
                    self.mode_menu()
                elif kk == " " or fk == 1:
                    p.toggle()
                elif kk in ("+", "=") and p.mode == "PWM":
                    p.set_pwm(duty=p.duty + 5)
                elif kk == "-" and p.mode == "PWM":
                    p.set_pwm(duty=p.duty - 5)
                elif fk == 2:
                    self.pwm_dialog()
                elif fk == 3:
                    if _HW:
                        # the scan uses G1/G2 as I2C and leaves them as inputs
                        for q in self.pins:
                            if q.gpio in (1, 2):
                                q.release()
                    i2c_scan()
                elif fk == 4:
                    for q in self.pins:
                        q.release()
                elif kk == ESC or kk == LEFT:
                    return
        finally:
            for q in self.pins:
                q.release()
            gc.collect()


def run():
    Gpio().run()
