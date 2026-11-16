# Full-screen code editor (Python by default; plugins can pass a Syntax
# for another language).
#
#   fn+; , . /    cursor          fn+- / fn+=   home / end of line
#   fn+[ / fn+]   page up / down  Tab / shift+Tab   indent / dedent
#   ctrl+s save   ctrl+r run      ctrl+f find    ctrl+n find next
#   ctrl+g goto   ctrl+k cut line ctrl+u paste   ctrl+z undo
#   ctrl+d duplicate line         opt+<key> snippets (fn+h: help)
#   Esc (`)       close (asks to save if modified)
from cardgcalc import hal, gfx, ui
from cardgcalc.i18n import T
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, BS, DEL, ESC, TAB, SHIFT, CTRL, OPT, ALT, FN
from cardgcalc.hal import rgb

ROWH = 11
GUT = 3  # gutter digits

KEYWORDS = set((
    "False None True and as assert async await break class continue def del elif else "
    "except finally for from global if import in is lambda nonlocal not or pass raise "
    "return try while with yield").split())
BUILTINS = set((
    "abs all any bin bool bytearray bytes callable chr dict dir divmod enumerate eval exec "
    "filter float getattr globals hasattr hash hex id input int isinstance issubclass iter "
    "len list locals map max min next object oct open ord pow print range repr reversed "
    "round set setattr slice sorted str sum super tuple type zip self").split())

C_KW = rgb(255, 120, 170)
C_BI = rgb(110, 200, 255)
C_STR = rgb(150, 220, 110)
C_NUM = rgb(255, 180, 90)
C_COM = rgb(120, 130, 145)
C_OP = rgb(220, 220, 150)
C_TXT = gfx.FG

SNIPPETS = {
    "d": "def ", "f": "for i in range(", "w": "while ", "i": "if ", "l": "elif ",
    "e": "else:", "r": "return ", "p": "print(", "m": "import ", "n": "cardgcalc",
    "t": "True", "a": "False", "c": "class ", "x": "except ", "y": "try:",
}

_clip = []  # shared line clipboard


def highlight(line, in_str=None):
    """Split a line into (text, colour) runs.  in_str: open triple quote
    carried from a previous line ('\"\"\"' / \"'''\") or None.
    Returns (runs, in_str_at_end)."""
    runs = []
    i = 0
    n = len(line)
    if in_str:
        j = line.find(in_str)
        if j < 0:
            return [(line, C_STR)], in_str
        runs.append((line[: j + 3], C_STR))
        i = j + 3
        in_str = None
    start = i
    while i < n:
        c = line[i]
        if c == "#":
            runs.append((line[i:], C_COM))
            return runs, None
        if c == '"' or c == "'":
            q3 = line[i: i + 3]
            if q3 == c * 3:
                j = line.find(q3, i + 3)
                if j < 0:
                    runs.append((line[i:], C_STR))
                    return runs, q3
                runs.append((line[i: j + 3], C_STR))
                i = j + 3
                continue
            j = i + 1
            while j < n and line[j] != c:
                if line[j] == "\\":
                    j += 1
                j += 1
            runs.append((line[i: j + 1], C_STR))
            i = j + 1
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (line[j].isalpha() or line[j].isdigit() or line[j] == "_"):
                j += 1
            w = line[i:j]
            if w in KEYWORDS:
                col = C_KW
            elif w in BUILTINS:
                col = C_BI
            else:
                col = C_TXT
            runs.append((w, col))
            i = j
            continue
        if c.isdigit():
            j = i + 1
            while j < n and (line[j].isalpha() or line[j].isdigit() or line[j] in "._"):
                j += 1
            runs.append((line[i:j], C_NUM))
            i = j
            continue
        if c == " ":
            j = i + 1
            while j < n and line[j] == " ":
                j += 1
            runs.append((line[i:j], C_TXT))
            i = j
            continue
        runs.append((c, C_OP if c in "()[]{}:=+-*/%<>!,.&|^~@" else C_TXT))
        i += 1
    return runs, None


class Syntax:
    """Language support for the editor.  Plugins pass an object with the
    same attributes to edit(path, syntax) for another language:
      highlight(line, state) -> (runs, state)  runs: [(text, colour), ...]
      multiline   True if state can carry across lines (else state is None)
      snippets    {key: text} inserted by opt+key
      indent_after(line) -> True to indent the line after `line`"""

    multiline = True
    snippets = SNIPPETS

    def highlight(self, line, state=None):
        return highlight(line, state)

    def indent_after(self, line):
        return line.rstrip().endswith(":")


PYTHON = Syntax()


class Editor:
    def __init__(self, path, text=None, syntax=None):
        self.path = path
        self.syn = syntax or PYTHON
        if text is None:
            try:
                with open(path) as f:
                    text = f.read()
            except OSError:
                text = ""
        self.lines = text.replace("\r", "").split("\n")
        if not self.lines:
            self.lines = [""]
        self.cy = 0
        self.cx = 0
        self.top = 0
        self.left = 0
        self.mod = False
        self.undo = []
        self._typing = None
        self.find_s = ""
        self.f = gfx.font("normal")
        self.cols = (ui.W - (GUT * self.f.w + 3)) // self.f.w
        self.rows = (ui.H - ui.TOP) // ROWH
        self.msg = None
        self.run_requested = False

    # ---- editing primitives ------------------------------------------------
    def _change(self, y0, n_old, new, typing=False):
        """Replace lines[y0:y0+n_old] with list `new`, recording undo."""
        if typing and self._typing == y0 and n_old == 1 and len(new) == 1:
            pass  # coalesce consecutive typing on the same line
        else:
            self.undo.append((y0, len(new), self.lines[y0: y0 + n_old], self.cy, self.cx))
            if len(self.undo) > 40:
                del self.undo[0]
        self._typing = y0 if typing else None
        self.lines[y0: y0 + n_old] = new
        self.mod = True

    def do_undo(self):
        if not self.undo:
            self.msg = T("Nothing to undo")
            return
        y0, n_new, old, cy, cx = self.undo.pop()
        self.lines[y0: y0 + n_new] = old
        self.cy, self.cx = cy, cx
        self._typing = None
        self.mod = True

    def insert(self, s):
        l = self.lines[self.cy]
        self._change(self.cy, 1, [l[: self.cx] + s + l[self.cx:]], typing=True)
        self.cx += len(s)

    def newline(self):
        l = self.lines[self.cy]
        before = l[: self.cx]
        after = l[self.cx:]
        ind = len(before) - len(before.lstrip(" "))
        if self.syn.indent_after(before):
            ind += 4
        after = after.lstrip(" ")
        self._change(self.cy, 1, [before.rstrip() if before.strip() else before, " " * ind + after])
        self.cy += 1
        self.cx = ind

    def backspace(self):
        l = self.lines[self.cy]
        if self.cx > 0:
            n = 1
            pre = l[: self.cx]
            if pre.strip() == "" and len(pre) >= 1:
                n = (len(pre) - 1) % 4 + 1
            self._change(self.cy, 1, [l[: self.cx - n] + l[self.cx:]], typing=True)
            self.cx -= n
        elif self.cy > 0:
            p = self.lines[self.cy - 1]
            self._change(self.cy - 1, 2, [p + l])
            self.cy -= 1
            self.cx = len(p)

    def delete(self):
        l = self.lines[self.cy]
        if self.cx < len(l):
            self._change(self.cy, 1, [l[: self.cx] + l[self.cx + 1:]], typing=True)
        elif self.cy < len(self.lines) - 1:
            self._change(self.cy, 2, [l + self.lines[self.cy + 1]])

    def indent(self, d):
        l = self.lines[self.cy]
        if d > 0:
            sp = 4 - self.cx % 4
            self.insert(" " * sp)
        else:
            ind = len(l) - len(l.lstrip(" "))
            n = min(4, ind) if ind % 4 == 0 else ind % 4
            if n:
                self._change(self.cy, 1, [l[n:]])
                self.cx = max(0, self.cx - n)

    def cut_line(self):
        global _clip
        if self._last_cut:
            _clip.append(self.lines[self.cy])
        else:
            _clip = [self.lines[self.cy]]
        if len(self.lines) == 1:
            self._change(0, 1, [""])
        else:
            self._change(self.cy, 1, [])
            if self.cy >= len(self.lines):
                self.cy = len(self.lines) - 1
        self.cx = 0
        self.msg = T("Cut %d line(s)") % len(_clip)

    def paste(self):
        if not _clip:
            self.msg = T("Clipboard empty")
            return
        self._change(self.cy, 0, list(_clip))
        self.cy += len(_clip)
        self.cx = 0

    def dup_line(self):
        self._change(self.cy, 1, [self.lines[self.cy], self.lines[self.cy]])
        self.cy += 1

    # ---- file -------------------------------------------------------------
    def text(self):
        return "\n".join(self.lines)

    def save(self):
        try:
            with open(self.path, "w") as f:
                for i, l in enumerate(self.lines):
                    f.write(l)
                    if i < len(self.lines) - 1:
                        f.write("\n")
            self.mod = False
            self.msg = T("Saved")
            return True
        except OSError as e:
            ui.error("Save failed: %s" % e)
            return False

    # ---- search -----------------------------------------------------------
    def find(self, again=False):
        if not again or not self.find_s:
            s = ui.input_line("Find", self.find_s, math=False)
            if not s:
                return
            self.find_s = s
        s = self.find_s
        n = len(self.lines)
        y = self.cy
        x = self.cx + (1 if again else 0)
        for k in range(n + 1):
            yy = (y + k) % n
            j = self.lines[yy].find(s, x if k == 0 else 0)
            if j >= 0:
                self.cy, self.cx = yy, j
                self.msg = None
                return
        self.msg = T("Not found:") + " " + s

    def goto(self):
        s = ui.input_line("Go to line", "", math=False, prompt="1-%d" % len(self.lines))
        if s and s.strip().isdigit():
            self.cy = max(0, min(len(self.lines) - 1, int(s) - 1))
            self.cx = 0

    # ---- drawing ----------------------------------------------------------
    def _str_state(self, upto):
        st = None
        if not self.syn.multiline:
            return st
        if self.syn is not PYTHON:
            for i in range(upto):
                _, st = self.syn.highlight(self.lines[i], st)
            return st
        for i in range(upto):
            l = self.lines[i]
            if '"""' not in l and "'''" not in l and st is None:
                continue
            _, st = highlight(l, st)
        return st

    def draw(self):
        f = self.f
        fb = gfx.fb()
        name = self.path.split("/")[-1]
        right = "%d:%d" % (self.cy + 1, self.cx + 1)
        ui.status_bar(("*" if self.mod else "") + name, right)
        fb.fill_rect(0, ui.TOP, ui.W, ui.H - ui.TOP, gfx.BG)
        gx = GUT * f.w + 3
        fb.fill_rect(0, ui.TOP, gx - 2, ui.H - ui.TOP, gfx.PANEL)
        # scrolling
        if self.cy < self.top:
            self.top = self.cy
        if self.cy >= self.top + self.rows:
            self.top = self.cy - self.rows + 1
        if self.cx < self.left:
            self.left = max(0, self.cx - 4)
        if self.cx >= self.left + self.cols:
            self.left = self.cx - self.cols + 4
        # wide (Japanese) characters: keep the cursor inside by pixel width
        cl = self.lines[self.cy] if self.cy < len(self.lines) else ""
        while self.left < self.cx and gx + f.width(cl[self.left: self.cx]) > ui.W - 3:
            self.left += 1
        st = self._str_state(self.top)
        for r in range(self.rows):
            i = self.top + r
            if i >= len(self.lines):
                break
            y = ui.TOP + 1 + r * ROWH
            if i == self.cy:
                fb.fill_rect(gx - 1, y - 1, ui.W - gx + 1, ROWH, gfx.PANEL)
            num = "%d" % (i + 1)
            f.text(num[-GUT:], gx - 3 - f.width(num[-GUT:]), y, gfx.ACCENT if i == self.cy else gfx.DIM)
            runs, st = self.syn.highlight(self.lines[i], st)
            # draw runs starting at character `left`; widths are measured so
            # Japanese (8px) characters in strings/comments render correctly
            x = gx
            ci = 0
            left = self.left
            for t, col in runs:
                n = len(t)
                if ci + n <= left:
                    ci += n
                    continue
                if ci < left:
                    t = t[left - ci:]
                ci += n
                if x >= ui.W:
                    break
                t = t[: f.fits(t, ui.W - x + f.w)]
                x = f.text(t, x, y, col)
            if self.left > 0:
                fb.fill_rect(gx - 1, y, 1, f.h, gfx.ACCENT)
        # cursor
        cyr = self.cy - self.top
        cx = gx + f.width(cl[self.left: self.cx])
        fb.fill_rect(cx, ui.TOP + 1 + cyr * ROWH - 1, 2, ROWH, gfx.ACCENT)
        if self.msg:
            s = self.msg
            w = f.width(s) + 6
            fb.fill_rect(ui.W - w, ui.H - ROWH - 1, w, ROWH + 1, gfx.SEL)
            f.text(s, ui.W - w + 3, ui.H - ROWH, gfx.FG)
            self.msg = None
        gfx.show()

    def help(self):
        lines = [
            "fn+;,./  move   fn+- fn+= home/end",
            "fn+[ ]   page   Tab/sh+Tab indent",
            "ctrl+s save  ctrl+r run  ctrl+z undo",
            "ctrl+f find  ctrl+n next ctrl+g goto",
            "ctrl+k cut line  ctrl+u paste",
            "ctrl+d duplicate line",
            "` (esc) close",
            "opt snippets:",
        ]
        lines = [T(l) for l in lines]
        sn = self.syn.snippets
        ks = sorted(sn)
        for i in range(0, len(ks), 3):
            lines.append("  " + "  ".join("%s %s" % (k, sn[k].strip()) for k in ks[i: i + 3]))
        ui.text_view("Editor keys", lines)

    # ---- main loop --------------------------------------------------------
    def run(self):
        """Edit until closed.  Returns 'run' if ctrl+r was pressed (after save)."""
        self._last_cut = False
        while True:
            self.draw()
            k = hal.wait_key()
            key = k.key
            cut = False
            if k.mods & CTRL:
                b = k.base
                if b == "s":
                    self.save()
                elif b == "r":
                    if self.mod and not self.save():
                        continue
                    return "run"
                elif b == "f":
                    self.find()
                elif b == "n":
                    self.find(True)
                elif b == "g":
                    self.goto()
                elif b == "k":
                    self.cut_line()
                    cut = True
                elif b == "u":
                    self.paste()
                elif b == "z":
                    self.do_undo()
                elif b == "d":
                    self.dup_line()
                elif b == "a":
                    self.cx = 0
                elif b == "e":
                    self.cx = len(self.lines[self.cy])
                self._last_cut = cut
                continue
            self._last_cut = False
            if k.mods & OPT and k.base in self.syn.snippets:
                self.insert(self.syn.snippets[k.base])
                continue
            if k.mods & FN and k.base == "h":
                self.help()
                continue
            n = len(self.lines)
            if key == UP:
                if self.cy > 0:
                    self.cy -= 1
                    self.cx = min(self.cx, len(self.lines[self.cy]))
                self._typing = None
            elif key == DOWN:
                if self.cy < n - 1:
                    self.cy += 1
                    self.cx = min(self.cx, len(self.lines[self.cy]))
                self._typing = None
            elif key == LEFT:
                if self.cx > 0:
                    self.cx -= 1
                elif self.cy > 0:
                    self.cy -= 1
                    self.cx = len(self.lines[self.cy])
            elif key == RIGHT:
                if self.cx < len(self.lines[self.cy]):
                    self.cx += 1
                elif self.cy < n - 1:
                    self.cy += 1
                    self.cx = 0
            elif key == "HOME":
                l = self.lines[self.cy]
                ind = len(l) - len(l.lstrip(" "))
                self.cx = 0 if self.cx == ind else ind
            elif key == "END":
                self.cx = len(self.lines[self.cy])
            elif key == "PGUP":
                self.cy = max(0, self.cy - self.rows + 1)
                self.cx = min(self.cx, len(self.lines[self.cy]))
            elif key == "PGDN":
                self.cy = min(n - 1, self.cy + self.rows - 1)
                self.cx = min(self.cx, len(self.lines[self.cy]))
            elif key == ENTER:
                self.newline()
            elif key == BS:
                self.backspace()
            elif key == DEL:
                self.delete()
            elif key == TAB:
                self.indent(-1 if k.mods & SHIFT else 1)
            elif key == ESC:
                if not self.mod:
                    return None
                i = ui.menu("Save changes?", ["Save", "Discard", "Cancel"])
                if i == 0:
                    if self.save():
                        return None
                elif i == 1:
                    return None
            elif len(key) == 1 and not (k.mods & (FN | ALT)):
                self.insert(key)


def edit(path, syntax=None):
    """Open path in the editor; returns 'run' if the user asked to run it.
    syntax: a Syntax-like object for other languages (see Syntax)."""
    import gc

    gc.collect()
    e = Editor(path, syntax=syntax)
    r = e.run()
    del e
    gc.collect()
    return r
