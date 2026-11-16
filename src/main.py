# card-gcalc boot entry (frozen).
#
# Safe mode: hold the G0 button (or the ` / ESC key) while the splash is
# shown to skip the calculator and stay in the MicroPython REPL.
# If /main_user.py exists it is run instead of the calculator.
import sys


def _safe_mode():
    import time
    from machine import Pin
    from cardgcalc import hal

    g0 = Pin(0, Pin.IN, Pin.PULL_UP)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 350:
        if g0.value() == 0:
            return True
        k = hal.keyboard.poll()
        if k is not None and k.key in ("`", "ESC"):
            return True
        time.sleep_ms(20)
    return False


def _splash(msg=None):
    from cardgcalc import hal, gfx

    gfx.fill(gfx.BG)
    f = gfx.font("large")
    t = "card-gcalc"
    f.text(t, (hal.W - f.width(t)) // 2, 44, gfx.ACCENT)
    s = gfx.font("normal")
    try:
        from cardgcalc.i18n import T
    except Exception:
        T = str
    sub = T(msg or "graphing calculator")
    s.text(sub, (hal.W - s.width(sub)) // 2, 72, gfx.DIM)
    gfx.show()


def _boot():
    from cardgcalc import hal

    hal.init()
    _splash()
    if _safe_mode():
        _splash("safe mode: REPL on USB")
        return
    try:
        import os

        os.stat("/main_user.py")
        exec(open("/main_user.py").read(), {"__name__": "__main__"})
        return
    except OSError:
        pass
    from cardgcalc import app

    app.main()


try:
    _boot()
except KeyboardInterrupt:
    pass
except Exception as e:
    sys.print_exception(e)
    try:
        import io
        from cardgcalc import ui

        buf = io.StringIO()
        sys.print_exception(e, buf)
        ui.text_view("Fatal error (REPL on USB)", buf.getvalue().split("\n"))
    except Exception:
        pass
