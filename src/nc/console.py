# Scrolling text console used by the Python runner and the shell.
#
# Text is kept as a list of already-wrapped lines (max MAXLINES) with one
# colour per line.  Redraws are throttled so that heavy printing stays fast.
import time
from nc import hal, gfx, ui
from nc.i18n import T
from nc.hal import UP, DOWN, ENTER, ESC, BS

MAXLINES = 200
ROWH = 11


class Console:
    def __init__(self, title="Console", font="normal"):
        self.title = title
        self.f = gfx.font(font)
        self.cols = ui.W // self.f.w - 0
        self._lw = 0  # pixel width of the last line (wrap by width)
        self.rows = (ui.H - ui.TOP - 1) // ROWH
        self.lines = [""]
        self.colors = [gfx.FG]
        self.color = gfx.FG
        self._last = 0
        self.off = 0  # scroll-back offset (lines from the bottom)
        self.suspended = False  # True while a script owns the screen
        self.used = False  # anything printed?
        self._pend = b""

    # ---- text ----------------------------------------------------------
    def _newline(self):
        self._lw = 0
        self.lines.append("")
        self.colors.append(self.color)
        if len(self.lines) > MAXLINES:
            del self.lines[0]
            del self.colors[0]

    def write(self, s, color=None):
        if not isinstance(s, str):
            s = self._decode(s)
            if not s:
                return 0
        if color is not None:
            old = self.color
            self.color = color
        self.used = True
        if self.lines[-1] == "":
            self.colors[-1] = self.color
        f = self.f
        fw = f.w
        W = ui.W
        for ch in s:
            if ch == "\n":
                self._newline()
            elif ch == "\r":
                continue
            elif ch == "\t":
                l = self.lines[-1]
                n = 4 - len(l) % 4
                if self._lw + n * fw > W:
                    self._newline()
                    n = 4
                self.lines[-1] += " " * n
                self._lw += n * fw
            elif ch == "\b":
                self.lines[-1] = self.lines[-1][:-1]
                self._lw = f.width(self.lines[-1])
            else:
                # Japanese glyphs are 8px wide: wrap by pixel width
                cw = fw if ch < "\x80" else f.cw(ch)
                if self._lw + cw > W:
                    self._newline()
                self.lines[-1] += ch
                self._lw += cw
        if color is not None:
            self.color = old
        self.off = 0
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last) > 80:
            self.draw()
        return len(s)

    def _decode(self, b):
        b = self._pend + bytes(b)
        # keep an incomplete UTF-8 sequence for the next write
        n = len(b)
        cut = n
        i = n - 1
        while i >= 0 and i >= n - 4:
            c = b[i]
            if c & 0xC0 == 0x80:
                i -= 1
                continue
            if c & 0x80:
                need = 2 if c & 0xE0 == 0xC0 else (3 if c & 0xF0 == 0xE0 else 4)
                if n - i < need:
                    cut = i
            break
        self._pend = b[cut:]
        try:
            return b[:cut].decode()
        except Exception:
            return "".join(chr(c) if c < 128 else "?" for c in b[:cut])

    def print(self, *a, sep=" ", end="\n", color=None):
        self.write(sep.join(str(x) for x in a) + end, color)

    def clear(self):
        self._lw = 0
        self.lines = [""]
        self.colors = [self.color]
        self.off = 0

    # ---- drawing -------------------------------------------------------
    def draw(self, extra=None, edit=None):
        """Redraw.  extra: text appended to the last line (input prompt),
        edit: LineEdit drawn after it."""
        self._last = time.ticks_ms()
        if self.suspended:
            return
        fb = gfx.fb()
        ui.status_bar(self.title, "")
        fb.fill_rect(0, ui.TOP, ui.W, ui.H - ui.TOP, gfx.BG)
        n = len(self.lines)
        end = n - self.off
        start = max(0, end - self.rows)
        y = ui.TOP + 1
        f = self.f
        for i in range(start, end):
            f.text(self.lines[i], 0, y, self.colors[i])
            if i == end - 1 and edit is not None and self.off == 0:
                x = f.width(self.lines[i])
                if ui.W - x < 8 * f.w:
                    # not enough room: edit on its own line handled by caller
                    x = ui.W - 8 * f.w
                edit.draw(x, y, ui.W - x, bg=gfx.BG)
            y += ROWH
        if self.off:
            s = "-%d-" % self.off
            fb.fill_rect(ui.W - f.width(s) - 2, ui.TOP, f.width(s) + 2, ROWH, gfx.SEL)
            f.text(s, ui.W - f.width(s) - 1, ui.TOP, gfx.FG)
        from nc import runner

        runner.show()

    def scroll(self, d):
        self.off = max(0, min(len(self.lines) - self.rows, self.off + d))
        if self.off < 0:
            self.off = 0

    # ---- input ---------------------------------------------------------
    def readline(self, prompt="", history=None, init=""):
        """Read a line from the keyboard (shown at the end of the console).
        Returns str, or None if Esc was pressed on an empty line."""
        from nc import runner

        if prompt:
            self.write(prompt)
        ed = ui.LineEdit(init, math=False, font="normal")
        hi = len(history) if history is not None else 0
        was = self.suspended
        self.suspended = False
        runner.kb_busy += 1
        try:
            while True:
                self.draw(edit=ed)
                k = hal.wait_key()
                if k.mods & hal.CTRL and k.base == "c":
                    raise KeyboardInterrupt
                kk = k.key
                if kk == UP and history:
                    if hi > 0:
                        hi -= 1
                        ed.set(history[hi])
                    continue
                if kk == DOWN and history is not None:
                    if hi < len(history) - 1:
                        hi += 1
                        ed.set(history[hi])
                    else:
                        hi = len(history)
                        ed.set("")
                    continue
                if kk == "PGUP":
                    self.scroll(self.rows - 1)
                    continue
                if kk == "PGDN":
                    self.scroll(-(self.rows - 1))
                    continue
                if k.mods & hal.CTRL and k.base == "d" and not ed.text:
                    return None
                r = ed.handle(k)
                if r == "enter":
                    self.write(ed.text + "\n")
                    return ed.text
                if r == "esc":
                    if ed.text:
                        ed.set("")
                    else:
                        self.write("\n")
                        return None
        finally:
            runner.kb_busy -= 1
            self.suspended = was

    def input(self, prompt=""):
        s = self.readline(str(prompt))
        if s is None:
            raise KeyboardInterrupt
        return s

    def wait_end(self, msg="[press any key]"):
        """Show the final screen; ;/. (fn) scroll back. Returns on any other key."""
        self.suspended = False
        self.write(T(msg), gfx.DIM)
        while True:
            self.draw()
            k = hal.wait_key()
            kk = k.nav()
            if kk == UP:
                self.scroll(1)
            elif kk == DOWN:
                self.scroll(-1)
            elif kk == "PGUP":
                self.scroll(self.rows - 1)
            elif kk == "PGDN":
                self.scroll(-(self.rows - 1))
            else:
                return k


def stream(con):
    """A stream object (for os.dupterm / sys.print_exception) writing to con."""
    import io

    class _S(io.IOBase):
        def write(self, b):
            con.write(b)
            return len(b)

        def readinto(self, b):
            return None

        def ioctl(self, req, arg):
            return 0

    return _S()
