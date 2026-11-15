# Shell: interactive Python REPL on the device screen.
#
#   Enter      execute (a line ending with ':' starts a block; empty line ends it)
#   fn+; fn+.  history         fn+[ fn+]  scroll output
#   Tab        indent          ctrl+c     interrupt / cancel block
#   ctrl+d / Esc on an empty line   leave the shell
import gc
import sys
from nc import hal, gfx, runner
from nc.i18n import T
from nc.console import Console

_hist = []


def _execute(src, ns, con):
    try:
        try:
            code = compile(src, "<stdin>", "eval")
            is_expr = True
        except SyntaxError:
            code = compile(src, "<stdin>", "exec")
            is_expr = False
        except NameError:  # no compile() builtin
            code = None
            is_expr = None
        if code is None:
            try:
                v = eval(src, ns)
                is_expr = True
            except SyntaxError:
                exec(src, ns)
                is_expr = False
        elif is_expr:
            v = eval(code, ns)
        else:
            exec(code, ns)
        if is_expr and v is not None:
            ns["_"] = v
            con.write(repr(v) + "\n", gfx.ACCENT2)
    except KeyboardInterrupt:
        con.write("KeyboardInterrupt\n", gfx.YELLOW)
    except SystemExit:
        raise
    except BaseException as e:
        con.color = gfx.ERR
        from nc import console

        sys.print_exception(e, console.stream(con))
        con.color = gfx.FG


def run():
    gc.collect()
    con = Console("Shell")
    con.write(T("MicroPython %s  (card-gcalc shell)") % ".".join(str(v) for v in sys.implementation[1][:3]) + "\n", gfx.DIM)
    con.write(T("Esc on empty line: exit, fn+;/.: history") + "\n", gfx.DIM)
    runner.start(con)
    ns = runner.make_namespace(con, "__main__")
    try:
        while True:
            try:
                line = con.readline(">>> ", _hist)
            except KeyboardInterrupt:
                con.write("\nKeyboardInterrupt\n", gfx.YELLOW)
                continue
            if line is None:
                break
            if not line.strip():
                continue
            src = line
            if line.rstrip().endswith(":") or line.endswith("\\"):
                # block: read continuation lines until an empty one
                ind = len(line) - len(line.lstrip(" ")) + 4
                cancelled = False
                while True:
                    try:
                        l2 = con.readline("... ", None, " " * ind)
                    except KeyboardInterrupt:
                        cancelled = True
                        break
                    if l2 is None or not l2.strip():
                        break
                    src += "\n" + l2
                    if l2.rstrip().endswith(":"):
                        ind = len(l2) - len(l2.lstrip(" ")) + 4
                    else:
                        ind = len(l2) - len(l2.lstrip(" "))
                if cancelled:
                    con.write("\n")
                    continue
                src += "\n"
            if not _hist or _hist[-1] != src:
                _hist.append(src if "\n" not in src else line)
                if len(_hist) > 30:
                    del _hist[0]
            con.suspended = False
            runner.break_req = False
            _execute(src, ns, con)
            if runner.graphics_used:
                # a command drew on the screen: show it until a key
                hal.display.show()
                runner.graphics_used = False
                if runner.pending:
                    runner.pending = False
                    hal.wait_key()
                con.suspended = False
            gc.collect()
    finally:
        runner.stop()
        del ns
        gc.collect()
