# Common UI widgets for card-gcalc apps.
#
# Screen layout: status bar (0..11), content (12..123), soft keys (124..134).
import gc
from cardgcalc import hal, gfx, keymap
from cardgcalc.i18n import T
from cardgcalc.hal import (UP, DOWN, LEFT, RIGHT, ENTER, BS, DEL, ESC, TAB,
                    SHIFT, CTRL, OPT, ALT, FN)

W = hal.W
H = hal.H
TOP = 12
BOT = H - 11
CONTENT_H = BOT - TOP

_status_title = ""


def settings():
    from cardgcalc import settings as s

    return s


def status_bar(title=None, right=None):
    """Draw the top status bar: title, modifier latches, angle unit, battery."""
    global _status_title
    if title is not None:
        _status_title = T(title)
    f = gfx.font("normal")
    fb = gfx.fb()
    fb.fill_rect(0, 0, W, TOP, gfx.PANEL)
    f.text(_status_title, 3, 1, gfx.ACCENT)
    x = W - 2
    bat = hal.battery_pct()
    if bat is not None:
        # battery glyph
        x -= 16
        fb.rect(x, 3, 13, 6, gfx.DIM)
        fb.fill_rect(x + 13, 5, 2, 2, gfx.DIM)
        fb.fill_rect(x + 1, 4, max(1, 11 * bat // 100), 4, gfx.OK if bat > 20 else gfx.ERR)
        x -= 3
    s = settings()
    ang = {"deg": "DEG", "rad": "RAD", "grad": "GRA"}.get(s.get("angle"), "")
    if right is not None:
        ang = right
    if ang:
        x -= f.width(ang)
        f.text(ang, x, 1, gfx.DIM)
        x -= 4
    kb = hal.keyboard
    if kb is not None:
        for bit, lab, col in ((ALT, "alt", gfx.MAGENTA), (OPT, "opt", gfx.ACCENT2),
                              (CTRL, "ctl", gfx.YELLOW), (SHIFT, "SFT", gfx.FG), (FN, "fn", gfx.OK)):
            if (kb.latched | kb.locked) & bit:
                x -= f.width(lab) + 2
                fb.fill_rect(x - 1, 1, f.width(lab) + 2, 10, col if kb.locked & bit else gfx.PANEL2)
                f.text(lab, x, 1, gfx.BLACK if kb.locked & bit else col)
                x -= 2


def refresh_status():
    status_bar()
    gfx.show_rect(0, 0, W, TOP)


def softkeys(labels, active=None):
    """Bottom soft-key bar.  labels: list of up to 6 strings (F1..F6 = fn+1..6)."""
    f = gfx.font("small")
    fb = gfx.fb()
    fb.fill_rect(0, BOT, W, H - BOT, gfx.BG)
    n = 6
    w = W // n
    for i in range(n):
        lab = labels[i] if i < len(labels) else None
        if not lab:
            continue
        x = i * w
        col = gfx.SEL if active == i else gfx.PANEL2
        fb.fill_rect(x + 1, BOT + 1, w - 2, H - BOT - 1, col)
        lab = f.clip(T(lab), w - 4)
        f.text(lab, x + (w - f.width(lab)) // 2, BOT + 2, gfx.FG)


def clear_content(c=gfx.BG):
    gfx.fb().fill_rect(0, TOP, W, BOT - TOP, c)


def fkey(k):
    """Return 0..9 if k is F1..F10, else None."""
    if k.key and len(k.key) >= 2 and k.key[0] == "F" and k.key[1:].isdigit():
        return int(k.key[1:]) - 1
    return None


def _hook_mods():
    if hal.keyboard is not None:
        hal.keyboard.on_mods = refresh_status


# ---------------------------------------------------------------------------
# LineEdit: single line math/text input
# ---------------------------------------------------------------------------
class LineEdit:
    """Single-line editor.

    math=True enables opt/alt math tokens and token-wise deletion.
    handle(key) returns:
        None      key consumed
        'enter'   Enter pressed
        'esc'     Esc pressed
        Key       not handled (caller may use it: UP/DOWN/F-keys ...)
    """

    def __init__(self, text="", math=True, font="medium", maxlen=200):
        self.text = text
        self.cur = len(text)
        self.math = math
        self.font = gfx.font(font)
        self.maxlen = maxlen
        self.scroll = 0
        self.insert_mode = True
        # When set, the first character typed replaces the whole text
        # (used for dialogs pre-filled with the current value).
        self.replace_on_type = False

    def set(self, text):
        self.text = text
        self.cur = len(text)
        self.scroll = 0

    def insert(self, s):
        if self.replace_on_type:
            self.replace_on_type = False
            self.text = ""
            self.cur = 0
        if len(self.text) + len(s) > self.maxlen:
            return
        t = self.text
        if not self.insert_mode and self.cur < len(t):
            t = t[: self.cur] + t[self.cur + len(s):]
        self.text = t[: self.cur] + s + t[self.cur:]
        self.cur += len(s)

    def _tok_before(self):
        if self.math:
            for tok in keymap.TOKENS:
                if self.text.endswith(tok, 0, self.cur):
                    return len(tok)
        return 1

    def _tok_after(self):
        if self.math:
            for tok in keymap.TOKENS:
                if self.text.startswith(tok, self.cur):
                    return len(tok)
        return 1

    def handle(self, k):
        key = k.key
        if self.replace_on_type and key in (LEFT, RIGHT, BS, DEL, "HOME", "END"):
            self.replace_on_type = False
        if self.math and (k.mods & (OPT | ALT)):
            tok = keymap.lookup(k)
            if tok:
                self.insert(tok)
                return None
        if key == ENTER:
            return "enter"
        if key == ESC:
            return "esc"
        if key == LEFT:
            if self.cur > 0:
                self.cur -= self._tok_before()
            return None
        if key == RIGHT:
            if self.cur < len(self.text):
                self.cur += self._tok_after()
            return None
        if key == "HOME":
            self.cur = 0
            return None
        if key == "END":
            self.cur = len(self.text)
            return None
        if key == BS:
            if self.cur > 0:
                n = self._tok_before()
                self.text = self.text[: self.cur - n] + self.text[self.cur:]
                self.cur -= n
            return None
        if key == DEL:
            if self.cur < len(self.text):
                n = self._tok_after()
                self.text = self.text[: self.cur] + self.text[self.cur + n:]
            return None
        if k.mods & CTRL:
            if key in ("u", "U"):
                self.set("")
                return None
            return k
        if len(key) == 1 and not (k.mods & FN):
            ch = key
            if self.math:
                if ch == "*":
                    ch = "×"
                elif ch == "/":
                    ch = "÷"
            self.insert(ch)
            return None
        return k

    def draw(self, x, y, w, fg=gfx.FG, bg=gfx.BG, cursor=True, align_right=False):
        f = self.font
        fb = gfx.fb()
        fb.fill_rect(x, y, w, f.h, bg)
        ncols = w // f.w
        t = self.text
        # keep cursor visible
        if self.cur < self.scroll:
            self.scroll = self.cur
        if self.cur - self.scroll > ncols - 1:
            self.scroll = self.cur - ncols + 1
        vis = t[self.scroll: self.scroll + ncols]
        f.text(vis, x, y, fg)
        if self.scroll > 0:
            fb.fill_rect(x, y, 1, f.h, gfx.ACCENT)
        if len(t) - self.scroll > ncols:
            fb.fill_rect(x + w - 1, y, 1, f.h, gfx.ACCENT)
        if cursor:
            cx = x + f.width(t[self.scroll: self.cur])
            if self.replace_on_type and t:
                fb.rect(x - 1, y - 1, f.width(t[self.scroll:]) + 2, f.h + 1, gfx.ACCENT)
            if self.insert_mode:
                fb.fill_rect(cx, y, 1, f.h, gfx.ACCENT)
            else:
                fb.fill_rect(cx, y + f.h - 2, f.w, 2, gfx.ACCENT)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
def message(title, lines, wait=True, color=None):
    """Modal message box; returns the key that dismissed it."""
    title = T(title)
    if isinstance(lines, str):
        lines = T(lines).split("\n")
    else:
        lines = [T(l) for l in lines]
    f = gfx.font("normal")
    fb = gfx.fb()
    w = min(W - 16, max(f.width(title), max([f.width(l) for l in lines] + [0])) + 16)
    h = 16 + len(lines) * 11 + 6
    x = (W - w) // 2
    y = max(TOP, (H - h) // 2)
    fb.fill_rect(x + 2, y + 2, w, h, gfx.BLACK)
    fb.fill_rect(x, y, w, h, gfx.PANEL)
    fb.rect(x, y, w, h, color or gfx.ACCENT)
    fb.fill_rect(x, y, w, 13, color or gfx.ACCENT)
    f.text(f.clip(title, w - 6), x + 4, y + 2, gfx.BLACK)
    for i, l in enumerate(lines):
        f.text(f.clip(l, w - 8), x + 6, y + 17 + i * 11, gfx.FG)
    gfx.show()
    if wait:
        return hal.wait_key()


def error(msg):
    return message("Error", msg, color=gfx.ERR)


def confirm(title, text="Enter: yes   Esc: no"):
    text = T(text)
    k = message(title, text)
    return k.key in (ENTER, "y", "Y")


def input_line(title, text="", math=True, prompt=None, typed=False):
    """Ask for a line of input in a dialog.  Returns str or None (Esc).
    text: initial value, replaced as a whole by typing.  typed=True: text
    is what the user already started typing, so further keys append."""
    title = T(title)
    prompt = T(prompt)
    ed = LineEdit(text, math=math, font="normal")
    ed.replace_on_type = bool(text) and not typed
    f = gfx.font("normal")
    fb = gfx.fb()
    w = W - 16
    x = 8
    h = 44 if prompt else 34
    y = (H - h) // 2
    while True:
        fb.fill_rect(x + 2, y + 2, w, h, gfx.BLACK)
        fb.fill_rect(x, y, w, h, gfx.PANEL)
        fb.rect(x, y, w, h, gfx.ACCENT)
        fb.fill_rect(x, y, w, 13, gfx.ACCENT)
        f.text(f.clip(title, w - 6), x + 4, y + 2, gfx.BLACK)
        yy = y + 17
        if prompt:
            f.text(prompt, x + 6, yy, gfx.DIM)
            yy += 11
        fb.fill_rect(x + 4, yy - 1, w - 8, 12, gfx.BG)
        ed.draw(x + 6, yy, w - 12, bg=gfx.BG)
        gfx.show()
        k = hal.wait_key()
        r = ed.handle(k)
        if r == "enter":
            return ed.text
        if r == "esc":
            return None


def input_number(title, value=None, ctx=None, typed=None):
    """Ask for a numeric expression; returns a number or None.
    typed: text the user already started typing (replaces value)."""
    from cardgcalc.calc import numfmt

    txt = "" if value is None else numfmt.fmt(value)
    if typed:
        txt = typed
    while True:
        s = input_line(title, txt, typed=bool(typed))
        if s is None:
            return None
        try:
            return evaluate(s, ctx)
        except Exception as e:
            error(str(e))
            txt = s
            typed = s


def evaluate(s, ctx=None):
    if ctx is None:
        from cardgcalc import state

        ctx = state.ctx()
    return ctx.evaluate(s) if "→" in s else _eval_noans(ctx, s)


def _eval_noans(ctx, s):
    ans = ctx.vars.get("Ans")
    v = ctx.evaluate(s)
    if ans is None:
        ctx.vars.pop("Ans", None)
    else:
        ctx.vars["Ans"] = ans
    return v


# ---------------------------------------------------------------------------
# List menu
# ---------------------------------------------------------------------------
def menu(title, items, sel=0, keys=None, help_line=None):
    """Vertical list menu.  items: list of str or (str, right_str).
    Returns the selected index, or None on Esc.  Number keys 1-9 jump."""
    f = gfx.font("normal")
    rowh = 13
    top = TOP + 2
    vis = (BOT - top) // rowh
    off = 0
    n = len(items)
    while True:
        if sel < off:
            off = sel
        if sel >= off + vis:
            off = sel - vis + 1
        gfx.fill()
        status_bar(title)
        for r in range(vis):
            i = off + r
            if i >= n:
                break
            it = items[i]
            right = None
            if isinstance(it, tuple):
                it, right = it
                right = T(right)
            it = T(it)
            y = top + r * rowh
            if i == sel:
                gfx.fb().fill_rect(0, y - 1, W, rowh, gfx.SEL)
            num = "%d" % (i + 1) if i < 9 else " "
            f.text(num, 4, y + 1, gfx.ACCENT if i != sel else gfx.YELLOW)
            f.text(f.clip(it, W - 24 - (f.width(right) if right else 0)), 16, y + 1, gfx.FG)
            if right:
                f.text(right, W - 6 - f.width(right), y + 1, gfx.DIM)
        if n > vis:
            sh = max(6, (BOT - top) * vis // n)
            sy = top + (BOT - top - sh) * off // max(1, n - vis)
            gfx.fb().fill_rect(W - 2, sy, 2, sh, gfx.DIM)
        softkeys([] if keys is None else keys)
        if help_line:
            gfx.font("small").text(T(help_line), 2, BOT + 2, gfx.DIM)
        gfx.show()
        k = hal.wait_key()
        kk = k.nav()
        if kk == UP:
            sel = (sel - 1) % n if n else 0
        elif kk == DOWN:
            sel = (sel + 1) % n if n else 0
        elif kk == "PGUP":
            sel = max(0, sel - vis)
        elif kk == "PGDN":
            sel = min(n - 1, sel + vis)
        elif kk == ENTER or kk == RIGHT:
            if n:
                return sel
        elif kk == ESC or kk == LEFT:
            return None
        elif len(kk) == 1 and kk.isdigit() and kk != "0":
            i = int(kk) - 1
            if i < n:
                return i


def choose(title, options, current=None):
    """Pick one of options (list of str). Returns index or None."""
    sel = 0
    if current is not None and current in options:
        sel = options.index(current)
    items = [("● " if o == current else "  ") + T(o) for o in options]
    return menu(title, items, sel)


def text_view(title, lines, font="normal"):
    """Scrollable read-only text view.  Esc/Enter to close."""
    f = gfx.font(font)
    rowh = f.h + 1
    vis = (BOT - TOP - 2) // rowh
    # wrap (width-aware: Japanese glyphs are 8px wide)
    out = []
    for l in lines:
        while l and f.width(l) > W - 2:
            n = max(1, f.fits(l, W - 2))
            out.append(l[:n])
            l = l[n:]
        out.append(l)
    off = 0
    while True:
        gfx.fill()
        status_bar(title)
        for r in range(vis):
            i = off + r
            if i >= len(out):
                break
            f.text(out[i], 1, TOP + 2 + r * rowh, gfx.FG)
        softkeys([])
        gfx.font("small").text("%d/%d  " % (min(off + vis, len(out)), len(out)) + T(";. scroll  ` back"), 2, BOT + 2, gfx.DIM)
        gfx.show()
        k = hal.wait_key().nav()
        if k == UP:
            off = max(0, off - 1)
        elif k == DOWN:
            off = max(0, min(len(out) - vis, off + 1))
        elif k == "PGUP" or k == LEFT:
            off = max(0, off - vis)
        elif k == "PGDN" or k == RIGHT:
            off = max(0, min(len(out) - vis, off + vis))
        elif k in (ESC, ENTER):
            return


def show_keymap_help():
    lines = []
    for layer, text in keymap.HELP:
        lines.append("%-3s %s" % (layer, T(text)))
    text_view("Key map (opt/alt/fn)", lines)


def busy(msg="Working..."):
    msg = T(msg)
    f = gfx.font("normal")
    w = f.width(msg) + 16
    x = (W - w) // 2
    y = (H - 18) // 2
    gfx.fb().fill_rect(x, y, w, 18, gfx.PANEL2)
    gfx.fb().rect(x, y, w, 18, gfx.ACCENT)
    f.text(msg, x + 8, y + 4, gfx.FG)
    gfx.show_rect(x, y, w, 18)


def collect():
    gc.collect()
