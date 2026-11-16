# Running user Python code: output capture, input(), break key, auto refresh.
#
# Output capture
#   device : os.dupterm(stream) mirrors everything printed (also from
#            imported modules and tracebacks) to the console.
#   sim    : `print` is injected into the script namespace.
# Break (Ctrl+C or Esc)
#   A 50 ms machine.Timer polls the keyboard.  If the firmware provides
#   ncore.kbd_interrupt() (mp_sched_keyboard_interrupt) a KeyboardInterrupt is
#   raised asynchronously; otherwise `break_req` is set and checked by
#   console writes, card-gcalc drawing / key / sleep calls (cooperative).
import gc
import sys
import time
from cardgcalc import hal, gfx

break_req = False
kb_busy = 0  # >0 while UI code reads the keyboard itself
disp_busy = 0  # >0 while main code pushes the frame buffer
dirty = False  # screen changed by script drawing -> auto refresh
graphics_used = False
pending = False  # drawing not yet acknowledged by a key press
_timer = None
_dup_prev = None
_con = None
_stream = None

try:
    import ncore

    _kbd_interrupt = ncore.kbd_interrupt
except Exception:
    _kbd_interrupt = None


def _is_break(k):
    return k.key == hal.ESC or (k.mods & hal.CTRL and k.base == "c")


def scan_break():
    """Read pending key events into the queue; remove and report break keys."""
    kb = hal.keyboard
    if hal.IS_DEVICE:
        try:
            for ev in kb._raw_events():
                if ev:
                    kb.feed(ev)
        except Exception:
            pass
    q = kb.queue
    for i in range(len(q)):
        if _is_break(q[i]):
            del q[i:]
            return True
    return False


_simn = 0


def check():
    """Raise KeyboardInterrupt if a break was requested (cooperative)."""
    global break_req, _simn
    if break_req:
        break_req = False
        raise KeyboardInterrupt
    if not hal.IS_DEVICE and _con is not None:
        # simulator: deliver scripted keys "asynchronously"
        _simn += 1
        if _simn % 200 == 0:
            if not hal.keyboard.queue:
                hal.sim_idle()
            if scan_break():
                raise KeyboardInterrupt


def mark_dirty():
    global dirty, graphics_used, pending
    dirty = True
    graphics_used = True
    pending = True
    if _con is not None:
        _con.suspended = True


def _tick(_t=None):
    global break_req, dirty
    if dirty and disp_busy == 0:
        dirty = False
        try:
            hal.display.show()
        except Exception:
            pass
    if kb_busy == 0 and scan_break():
        if _kbd_interrupt is None:
            break_req = True
            return
        # Must be the last thing the callback does: the KeyboardInterrupt is
        # pending from now on, and any further code in this callback would
        # raise it here (and lose it) instead of in the running script.
        _kbd_interrupt()


def show():
    """Push the frame buffer from main code (guarded against the timer)."""
    global dirty, disp_busy
    disp_busy += 1
    try:
        dirty = False
        hal.display.show()
    finally:
        disp_busy -= 1


def start(con):
    """Begin capturing output to console `con` and watching for break."""
    global _timer, _dup_prev, _con, _stream, break_req, dirty, graphics_used, pending
    from cardgcalc import console

    _con = con
    break_req = False
    dirty = False
    graphics_used = False
    pending = False
    _stream = console.stream(con)
    if hal.IS_DEVICE:
        try:
            import os

            _dup_prev = os.dupterm(_stream)
        except Exception as e:
            _dup_prev = None
        try:
            from machine import Timer

            _timer = Timer(0)
            _timer.init(period=50, mode=Timer.PERIODIC, callback=_tick)
        except Exception:
            _timer = None
    return _stream


def stop():
    global _timer, _con, _stream, break_req, dirty
    if _timer is not None:
        try:
            _timer.deinit()
        except Exception:
            pass
        _timer = None
    if hal.IS_DEVICE:
        try:
            import os

            os.dupterm(_dup_prev)
        except Exception:
            pass
    if dirty:
        dirty = False
        try:
            hal.display.show()
        except Exception:
            pass
    _con = None
    _stream = None
    break_req = False


def make_namespace(con, name="__main__", path=None):
    ns = {"__name__": name}
    if path:
        ns["__file__"] = path
    ns["input"] = con.input
    if True:
        # print is injected so that printing also checks for break (and the
        # unix port has no dupterm).  Output of imported modules reaches the
        # console through dupterm on the device.
        def _print(*a, sep=" ", end="\n", file=None):
            if file is not None and file is not _stream:
                file.write(sep.join(str(x) for x in a) + end)
                return
            check()
            con.write(sep.join(str(x) for x in a) + end)

        ns["print"] = _print
    return ns


def run_file(path):
    try:
        with open(path) as f:
            src = f.read()
    except OSError as e:
        from cardgcalc import ui

        from cardgcalc.i18n import T

        ui.error(T("Cannot read %s") % path + "\n%s" % e)
        return
    name = path.split("/")[-1]
    run_source(src, name, path)


def run_source(src, name="script", path=None):
    """Run a script in a fresh namespace; show output; wait for a key."""
    from cardgcalc import console

    gc.collect()
    con = console.Console(name)
    con.draw()
    stream = start(con)
    ns = make_namespace(con, "__main__", path)
    d = None
    if path and "/" in path:
        d = path[: path.rfind("/")] or "/"
        sys.path.insert(0, d)
    mods_before = set(sys.modules)
    err = None
    try:
        try:
            code = compile(src, name, "exec")
        except NameError:
            code = src
        del src
        gc.collect()
        exec(code, ns)
    except KeyboardInterrupt:
        err = "int"
    except SystemExit:
        pass
    except BaseException as e:
        err = e
    finally:
        stop()
        if d is not None:
            try:
                sys.path.remove(d)
            except ValueError:
                pass
        # unload modules the script imported (user modules), keep system ones
        for m in list(sys.modules):
            if m not in mods_before and not m.startswith("cardgcalc") and m not in _KEEP:
                del sys.modules[m]
    con.suspended = False
    if err == "int":
        con.write("\nKeyboardInterrupt\n", gfx.YELLOW)
    elif err is not None:
        con.color = gfx.ERR
        con.write("\n")
        sys.print_exception(err, console.stream(con))
        con.color = gfx.FG
    if graphics_used and err is None:
        if pending:
            # leave the picture on screen until a key is pressed
            con.suspended = True
            hal.display.show()
            k = hal.wait_key()
            if con.used and not _is_break(k):
                con.suspended = False
                con.wait_end()
        elif con.used:
            con.suspended = False
            con.wait_end()
    else:
        con.wait_end()
    del ns
    gc.collect()


_KEEP = ()
