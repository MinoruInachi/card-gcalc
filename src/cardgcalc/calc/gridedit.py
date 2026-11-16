# UI helpers shared by the Equation / Stats / Matrix apps:
#   fmt_fit      number -> string of limited width
#   Grid         spreadsheet-like cell editor
#   result_list  scrollable list of labelled results (Enter: store to variable)
#   form         labelled input fields
from cardgcalc import hal, gfx, ui, settings, state
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL, CTRL, FN, OPT, ALT
import bcd
from bcd import D
from cardgcalc.calc import numfmt
from cardgcalc.calc.dec import isreal
from cardgcalc.i18n import T

_E3 = D("1e-3")


def fmt(v):
    if v is None:
        return ""
    return numfmt.fmt(v, settings.get("fmt"), settings.get("digits"))


def fmt_fit(v, n, exact=False):
    """Format v in at most n characters."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v if len(v) <= n else v[: n - 1] + "…"
    if exact and isinstance(v, D):
        e = numfmt.exact(v)
        if e and len(e) <= n:
            return e
    s = fmt(v)
    if len(s) <= n:
        return s
    if isreal(v) and _E3 <= abs(v) < 10 ** (n - 1 - (v < 0)):
        # round in fixed notation
        intlen = len(str(int(abs(v)))) + (1 if v < 0 else 0)
        dec = n - intlen - 1
        if dec >= 1:
            t = numfmt.fmt_real(v, "fix", dec)
            if "." in t:
                t = t.rstrip("0").rstrip(".")
            if len(t) <= n:
                return t
        t = str(int(bcd.rnd(v)))
        if len(t) <= n:
            return t
    if isreal(v):
        for sig in range(min(10, n), 0, -1):
            s = numfmt.fmt_real(v, "sci", sig)
            m, _, e = s.partition("E")
            if "." in m:
                m = m.rstrip("0").rstrip(".")
            s = m + "E" + e
            if len(s) <= n:
                return s
    return s[: n - 1] + "…"


def evaluate(text):
    """Evaluate a cell expression without disturbing Ans."""
    return ui.evaluate(text, state.ctx())


# ---------------------------------------------------------------------------
class Grid:
    """Cell editor.  `model` provides:
        rows() cols() get(r, c) set(r, c, value) col_title(c) row_label(r)
    Optional: editable(r, c) -> bool, info(r, c) -> str (bottom bar text)
    """

    ROWH = 11

    def __init__(self, title, model, colw=72, labelw=20, keys=None, on_fkey=None,
                 advance="down", readonly=False, header=None):
        self.title = title
        self.m = model
        self.colw = colw
        self.labelw = labelw
        self.keys = keys or []
        self.on_fkey = on_fkey
        self.advance = advance
        self.readonly = readonly
        self.header = header  # optional line drawn above the grid
        self.r = 0
        self.c = 0
        self.top = 0
        self.left = 0
        self.ed = None
        self.exact = False
        self.f = gfx.font("normal")

    # geometry
    def _vis_cols(self):
        return max(1, (ui.W - self.labelw) // self.colw)

    def _y0(self):
        return ui.TOP + (12 if self.header else 0)

    def _vis_rows(self):
        return (ui.BOT - 14 - self._y0() - self.ROWH) // self.ROWH

    def clamp(self):
        nr = max(1, self.m.rows())
        nc = max(1, self.m.cols())
        self.r = max(0, min(self.r, nr - 1))
        self.c = max(0, min(self.c, nc - 1))
        vr = self._vis_rows()
        vc = self._vis_cols()
        if self.r < self.top:
            self.top = self.r
        if self.r >= self.top + vr:
            self.top = self.r - vr + 1
        if self.c < self.left:
            self.left = self.c
        if self.c >= self.left + vc:
            self.left = self.c - vc + 1

    def draw(self):
        self.clamp()
        fb = gfx.fb()
        f = self.f
        gfx.fill()
        ui.status_bar(self.title)
        y0 = self._y0()
        if self.header:
            fb.fill_rect(0, ui.TOP, ui.W, 12, gfx.BG)
            f.text(f.clip(T(self.header), ui.W - 4), 3, ui.TOP + 1, gfx.ACCENT2)
        vr = self._vis_rows()
        vc = self._vis_cols()
        nchar = (self.colw - 4) // f.w
        # column headers
        fb.fill_rect(0, y0, ui.W, self.ROWH, gfx.PANEL)
        for j in range(vc):
            c = self.left + j
            if c >= self.m.cols():
                break
            x = self.labelw + j * self.colw
            t = f.clip(T(self.m.col_title(c)), self.colw - 2)
            f.text(t, x + (self.colw - f.width(t)) // 2, y0 + 1,
                   gfx.YELLOW if c == self.c else gfx.ACCENT)
            fb.vline(x, y0, self.ROWH * (vr + 1), gfx.GRID)
        # rows
        for i in range(vr):
            r = self.top + i
            if r >= self.m.rows():
                break
            y = y0 + self.ROWH * (i + 1)
            lab = self.m.row_label(r)
            f.text(lab, self.labelw - 2 - f.width(lab), y + 1, gfx.YELLOW if r == self.r else gfx.DIM)
            for j in range(vc):
                c = self.left + j
                if c >= self.m.cols():
                    break
                x = self.labelw + j * self.colw
                sel = r == self.r and c == self.c
                if sel:
                    fb.fill_rect(x + 1, y, self.colw - 1, self.ROWH, gfx.SEL)
                v = self.m.get(r, c)
                s = fmt_fit(v, nchar, self.exact)
                col = gfx.FG
                if hasattr(self.m, "editable") and not self.m.editable(r, c):
                    col = gfx.DIM
                f.text(s, x + self.colw - 3 - f.width(s), y + 1, col)
            fb.hline(0, y + self.ROWH - 1, ui.W, gfx.GRID)
        # scroll marks
        if self.left > 0:
            fb.fill_rect(self.labelw, y0, 2, self.ROWH, gfx.ACCENT)
        if self.left + vc < self.m.cols():
            fb.fill_rect(ui.W - 2, y0, 2, self.ROWH, gfx.ACCENT)
        # bottom bar: info or editor
        by = ui.BOT - 13
        fb.fill_rect(0, by, ui.W, 13, gfx.PANEL)
        if hasattr(self.m, "cell_name"):
            lab = self.m.cell_name(self.r, self.c) + "="
        else:
            rl = self.m.row_label(self.r)
            lab = "%s%s=" % (self.m.col_title(self.c), "[%s]" % rl if rl else "")
        x = f.text(lab, 3, by + 2, gfx.ACCENT)
        if self.ed is not None:
            self.ed.draw(x + 2, by + 2, ui.W - x - 5, bg=gfx.PANEL)
        else:
            if hasattr(self.m, "info"):
                s = T(self.m.info(self.r, self.c))
            else:
                v = self.m.get(self.r, self.c)
                s = fmt(v) if not isinstance(v, str) else v
                if self.exact and isinstance(v, D):
                    s = numfmt.exact(v) or s
            f.text(f.clip(s or "", ui.W - x - 6), x + 2, by + 2, gfx.FG)
        ui.softkeys(self.keys)
        gfx.show()

    def _move(self, kk):
        if kk == UP:
            self.r -= 1
        elif kk == DOWN:
            self.r += 1
        elif kk == LEFT:
            self.c -= 1
        elif kk == RIGHT:
            self.c += 1
        elif kk == "PGUP":
            self.r -= self._vis_rows()
        elif kk == "PGDN":
            self.r += self._vis_rows()
        elif kk == "HOME":
            self.r = 0
        elif kk == "END":
            self.r = max(0, self.m.rows() - 1)
        else:
            return False
        return True

    def _can_edit(self):
        if self.readonly:
            return False
        if hasattr(self.m, "editable"):
            return self.m.editable(self.r, self.c)
        return True

    def _commit(self):
        txt = self.ed.text.strip()
        if not txt:
            self.ed = None
            return True
        try:
            v = evaluate(txt)
        except Exception as e:
            ui.error(str(e))
            return False
        self.m.set(self.r, self.c, v)
        self.ed = None
        if self.advance == "down":
            if self.r + 1 < self.m.rows():
                self.r += 1
        else:
            if self.c + 1 < self.m.cols():
                self.c += 1
            elif self.r + 1 < self.m.rows():
                self.r += 1
                self.c = 0
        return True

    def run(self):
        """Run until Esc (returns None) or on_fkey returns non-None."""
        while True:
            self.draw()
            k = hal.wait_key()
            if self.ed is not None:
                if k.key in (UP, DOWN):
                    if self._commit():
                        self._move(k.key)
                    continue
                r = self.ed.handle(k)
                if r == "enter":
                    self._commit()
                elif r == "esc":
                    self.ed = None
                continue
            fk = ui.fkey(k)
            if fk is not None:
                if self.on_fkey:
                    res = self.on_fkey(fk, self)
                    if res is not None:
                        return res
                continue
            kk = k.nav()
            if self._move(kk):
                continue
            if kk == ESC:
                return None
            if k.base == "h" and k.mods & FN:
                ui.show_keymap_help()
                continue
            if kk == "s" and k.mods & CTRL or (kk == "e" and k.mods & CTRL):
                self.exact = not self.exact
                continue
            if not self._can_edit():
                continue
            if kk == ENTER:
                v = self.m.get(self.r, self.c)
                self.ed = ui.LineEdit("" if v is None else fmt(v), math=True, font="normal")
                continue
            if kk in (BS, DEL):
                self.m.set(self.r, self.c, None)
                continue
            if (len(k.key) == 1 and not (k.mods & (FN | CTRL))) or (k.mods & (OPT | ALT)):
                self.ed = ui.LineEdit("", math=True, font="normal")
                self.ed.handle(k)


# ---------------------------------------------------------------------------
def store_value(v, label=""):
    """Ask for a variable name and store v there."""
    name = ui.input_line(T("Store %s to variable") % T(label), "", math=False, prompt="Letter (A-Z, x, y...)")
    if not name:
        return
    name = name.strip()
    if len(name) != 1 or not (name.isalpha() or name == "θ") or name in "ei":
        ui.error("Invalid variable name")
        return
    ctx = state.ctx()
    ctx.vars[name] = v
    state.save_vars()
    ui.message("Stored", "%s = %s" % (name, fmt(v)), color=gfx.OK)


def result_list(title, rows, header=None):
    """rows: list of (label, value[, exact_str]).  value may be str.
    Enter on a numeric row stores it into a variable.  Esc returns."""
    f = gfx.font("normal")
    fm = gfx.font("medium")
    # expand into display lines
    lines = []  # (label, text, value, colour)
    for row in rows:
        lab, v = row[0], row[1]
        ex = row[2] if len(row) > 2 else None
        if isinstance(v, str):
            lines.append((T(lab), T(v), None, gfx.FG))
        else:
            lines.append((T(lab), fmt(v), v, gfx.FG))
        if ex:
            lines.append(("", "= " + ex, None, gfx.ACCENT2))
    rowh = 13
    y0 = ui.TOP + 2 + (12 if header else 0)
    vis = (ui.BOT - y0) // rowh
    sel = 0
    off = 0
    n = len(lines)
    while True:
        if sel < off:
            off = sel
        if sel >= off + vis:
            off = sel - vis + 1
        gfx.fill()
        ui.status_bar(title)
        fb = gfx.fb()
        if header:
            f.text(f.clip(T(header), ui.W - 4), 3, ui.TOP + 2, gfx.ACCENT)
        for i in range(vis):
            j = off + i
            if j >= n:
                break
            lab, txt, v, col = lines[j]
            y = y0 + i * rowh
            if j == sel:
                fb.fill_rect(0, y - 1, ui.W, rowh, gfx.SEL)
            lw = f.text(f.clip(lab, ui.W - 48), 4, y + 1, gfx.ACCENT if j != sel else gfx.YELLOW)
            t = fm.clip(txt, ui.W - max(lw, 40) - 8)
            fm.text(t, ui.W - 4 - fm.width(t), y, col)
        if n > vis:
            sh = max(6, (ui.BOT - y0) * vis // n)
            sy = y0 + (ui.BOT - y0 - sh) * off // max(1, n - vis)
            fb.fill_rect(ui.W - 2, sy, 2, sh, gfx.DIM)
        fb.fill_rect(0, ui.BOT, ui.W, ui.H - ui.BOT, gfx.BG)
        gfx.font("small").text(T("Enter: store to var   ` back"), 2, ui.BOT + 2, gfx.DIM)
        gfx.show()
        k = hal.wait_key()
        kk = k.nav()
        if kk == UP:
            sel = max(0, sel - 1)
        elif kk == DOWN:
            sel = min(n - 1, sel + 1)
        elif kk == "PGUP":
            sel = max(0, sel - vis)
        elif kk == "PGDN":
            sel = min(n - 1, sel + vis)
        elif kk == ENTER:
            v = lines[sel][2]
            if v is not None:
                store_value(v, lines[sel][0])
        elif kk in (ESC, LEFT):
            return


def form(title, fields, submit="Run", sel=0, extra_keys=None):
    """fields: list of [label, text].  Edits texts in place.
    Enter moves to the next field; Enter on the last field or F1 submits.
    Returns True (submit), None (Esc), or ('fkey', n) for extra soft keys."""
    f = gfx.font("normal")
    eds = [ui.LineEdit(t, math=True, font="normal") for _, t in fields]
    labels = [T(l) for l, _ in fields]
    lw = min(ui.W // 2, max(f.width(l) for l in labels) + 8)
    rowh = 15
    vis = (ui.BOT - ui.TOP - 4) // rowh
    off = 0
    keys = [submit] + (extra_keys or [])
    while True:
        if sel < off:
            off = sel
        if sel >= off + vis:
            off = sel - vis + 1
        gfx.fill()
        ui.status_bar(title)
        fb = gfx.fb()
        for i in range(vis):
            j = off + i
            if j >= len(fields):
                break
            y = ui.TOP + 4 + i * rowh
            f.text(f.clip(labels[j], lw - 6), 4, y + 2, gfx.YELLOW if j == sel else gfx.DIM)
            fb.fill_rect(lw, y, ui.W - lw - 4, 13, gfx.PANEL2 if j == sel else gfx.PANEL)
            eds[j].draw(lw + 3, y + 2, ui.W - lw - 10, bg=gfx.PANEL2 if j == sel else gfx.PANEL, cursor=j == sel)
        ui.softkeys(keys)
        gfx.show()
        k = hal.wait_key()
        fk = ui.fkey(k)
        if fk is not None:
            for j in range(len(fields)):
                fields[j][1] = eds[j].text
            if fk == 0:
                return True
            if 0 < fk < len(keys):
                return ("fkey", fk)
            continue
        if k.key == UP:
            sel = (sel - 1) % len(fields)
            continue
        if k.key == DOWN:
            sel = (sel + 1) % len(fields)
            continue
        if k.base == "h" and k.mods & FN:
            ui.show_keymap_help()
            continue
        r = eds[sel].handle(k)
        if r == "enter":
            fields[sel][1] = eds[sel].text
            if sel == len(fields) - 1:
                for j in range(len(fields)):
                    fields[j][1] = eds[j].text
                return True
            sel += 1
        elif r == "esc":
            for j in range(len(fields)):
                fields[j][1] = eds[j].text
            return None
