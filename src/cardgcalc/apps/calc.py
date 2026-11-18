# Calc: the main calculation screen (history + input line).
#
#   Enter        evaluate            (empty line: repeat last)
#   ; / .        (fn) browse history; Enter inserts expression, → inserts result
#   F1 Exact       toggle exact form (fraction / π / √) of the result
#
# Numbers are computed exactly as fractions where possible (calc/frac.py):
# 1/3+1/6 shows 1/2.  A fraction result is shown as a fraction unless the
# expression contains a decimal number; F1 switches to the decimal.
#
# History entry: [expr, decimal, exact, show_exact, error, mixed]; exact and
# mixed are template text (see mathtext.py), mixed only for fractions > 1.
#   F2 Vars      list variables
#   F3 Angle     cycle DEG / RAD / GRA
#   F4 Format    Norm / Fix / Sci / Eng
#   F5 Clear     clear history
#   F6 Keys      math key map
#   expr→A  /  A=expr   store to a variable
#   opt+/  alt+/  fraction / mixed number template (drawn stacked)
from cardgcalc import hal, gfx, ui, settings, state, storage, mathtext
from cardgcalc.i18n import T
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL
from cardgcalc.calc import numfmt, frac
from cardgcalc.calc.expr import CalcError, has_decimal

MAXHIST = 40
MAXFRAC = 20  # longest fraction shown (characters)
_OPS_ANS = ("+", "-", "×", "÷", "^", "²", "³", "!", "⁻¹", "→", "%", "*", "/")


class Calc:
    def __init__(self):
        self.ctx = state.ctx()
        self.hist = storage.load_json("calc_hist.json", []) or []
        self.ed = ui.LineEdit("", math=True, font="medium", frac=True)
        self.sel = None  # selected history index (None = editing)
        self.f_in = gfx.font("normal")
        self.f_out = gfx.font("medium")
        self.f_big = gfx.font("large")

    # ---- evaluation ------------------------------------------------------
    def fmt(self, v):
        return numfmt.fmt(v, settings.get("fmt"), settings.get("digits"))

    def evaluate(self, src):
        try:
            v = self.ctx.evaluate(src, exact=True)
            if isinstance(v, frac.Q):
                out = self.fmt(v.dec())
                ex = mx = None
                if self.frac_str(v):
                    ex = frac.text(v)
                    if abs(v.n) > v.d:
                        mx = frac.text(v, True)
                entry = [src, out, ex, 1 if ex and not has_decimal(src) else 0, 0, mx]
            else:
                ex = numfmt.exact(v)  # None for integers and complex values
                if ex:
                    ex = frac.template(ex)
                entry = [src, self.fmt(v), ex, 0]
        except CalcError as e:
            entry = [src, str(e), None, 0]
            entry.append(1)  # error flag
        except Exception as e:
            entry = [src, "Error: %s" % e, None, 0, 1]
        self.hist.append(entry)
        if len(self.hist) > MAXHIST:
            self.hist.pop(0)

    @staticmethod
    def frac_str(q):
        """'n/d' for a non-integer fraction that fits on the screen."""
        if q.d == 1:
            return None
        s = frac.to_str(q)
        return s if len(s) <= MAXFRAC else None

    # ---- drawing -----------------------------------------------------------
    def draw(self):
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("Calc", self._right())
        # input box (taller while it holds a fraction)
        iy = ui.BOT - 4 - self.ed.height()
        fb.fill_rect(0, iy - 2, ui.W, ui.BOT - iy + 2, gfx.PANEL)
        fb.hline(0, iy - 2, ui.W, gfx.PANEL2)
        self.ed.draw(4, iy + 1, ui.W - 8, bg=gfx.PANEL, cursor=self.sel is None)
        # history, newest at the bottom
        y = iy - 4
        i = len(self.hist) - 1
        fi = self.f_in
        fo = self.f_out
        mixed = settings.get("mixedfrac")
        while i >= 0 and y > ui.TOP:
            e = self.hist[i]
            src, out = e[0], e[1]
            err = len(e) > 4 and e[4]
            shown = out
            if e[3] and e[2]:
                shown = e[5] if (mixed and len(e) > 5 and e[5]) else e[2]
            if err:
                shown = T(shown)
            # heights (fractions are drawn stacked)
            s2d = mathtext.has_marks(src)
            r2d = mathtext.has_marks(shown)
            hi = fi.h
            if s2d:
                _, iu, idn = mathtext.measure(src, fi)
                hi = iu + idn
            if r2d:
                rw, ru, rd = mathtext.measure(shown, fo)
                ho = ru + rd
            else:
                ho = fo.h
            h = hi + ho + 3
            top = y - h
            if self.sel == i:
                fb.fill_rect(0, max(ui.TOP, top), ui.W, y - max(ui.TOP, top) + 1, gfx.SEL)
            # expression (left)
            if top + 1 >= ui.TOP:
                col = gfx.DIM if self.sel != i else gfx.FG
                if s2d:
                    mathtext.draw(src, fi, 3, top + 1 + iu, col, x1=ui.W - 3)
                else:
                    fi.text(fi.clip(src, ui.W - 6), 3, top + 1, col)
            # result (right)
            ry = top + hi + 2
            if ry >= ui.TOP:
                col = gfx.ERR if err else (gfx.ACCENT2 if e[3] and e[2] else gfx.FG)
                if r2d:
                    mathtext.draw(shown, fo, max(4, ui.W - 4 - rw), ry + ru, col, x1=ui.W - 4)
                else:
                    s = fo.clip(shown, ui.W - 8)
                    fo.text(s, ui.W - 4 - fo.width(s), ry, col)
            if i > 0:
                fb.hline(4, top - 1, ui.W - 8, gfx.GRID)
            y = top - 2
            i -= 1
        if self.sel is None:
            ui.softkeys(["Exact", "Vars", "Angle", "Format", "Clear", "Keys"])
        else:
            gfx.fb().fill_rect(0, ui.BOT, ui.W, ui.H - ui.BOT, gfx.BG)
            gfx.font("small").text(T("Enter:expr  /:result  BS:delete  `:back"), 2, ui.BOT + 2, gfx.DIM)
        gfx.show()

    def _right(self):
        a = {"deg": "DEG", "rad": "RAD", "grad": "GRA"}.get(settings.get("angle"), "")
        f = settings.get("fmt")
        if f != "norm":
            a = "%s%d %s" % (f.upper()[:3], settings.get("digits"), a)
        if settings.get("complex"):
            a = "Cplx " + a
        return a

    # ---- actions -----------------------------------------------------------
    def toggle_exact(self):
        idx = self.sel if self.sel is not None else len(self.hist) - 1
        if 0 <= idx < len(self.hist):
            e = self.hist[idx]
            if e[2]:
                e[3] = 0 if e[3] else 1

    def show_vars(self):
        v = self.ctx.vars
        names = sorted(v)
        if not names:
            ui.message("Variables", "No variables yet.\nUse  expr→A  or  A=expr")
            return
        items = []
        for n in names:
            q = self.ctx.exact_var(n)
            s = self.frac_str(q) if isinstance(q, frac.Q) else None
            items.append((n, s or self.fmt(v[n])))
        i = ui.menu("Variables (Enter: insert)", items)
        if i is not None:
            self.ed.insert(names[i])

    def cycle_angle(self):
        a = settings.get("angle")
        a = {"rad": "deg", "deg": "grad", "grad": "rad"}[a]
        settings.set("angle", a)
        self.ctx.angle = a

    def choose_format(self):
        opts = ["Norm", "Fix", "Sci", "Eng", T("Complex") + ": " + T("on" if settings.get("complex") else "off"),
                T("Fraction") + ": " + T("mixed" if settings.get("mixedfrac") else "improper")]
        i = ui.menu("Display format", opts)
        if i is None:
            return
        if i == 4:
            settings.set("complex", not settings.get("complex"))
            self.ctx.complex = settings.get("complex")
            return
        if i == 5:
            settings.set("mixedfrac", not settings.get("mixedfrac"))
            return
        mode = ("norm", "fix", "sci", "eng")[i]
        if mode == "norm":
            settings.set("fmt", mode)
            settings.set("digits", 10)
            return
        lo, hi = (0, 9) if mode == "fix" else (1, 10)
        n = ui.input_number("Digits (0-9)" if mode == "fix" else "Significant digits (1-10)",
                            max(lo, min(hi, settings.get("digits"))))
        if n is None:
            return  # cancelled: keep the current format
        settings.set("fmt", mode)
        settings.set("digits", max(lo, min(hi, int(n))))

    def history_key(self, k):
        kk = k.nav()
        n = len(self.hist)
        if kk == UP:
            if self.sel > 0:
                self.sel -= 1
        elif kk == DOWN:
            self.sel += 1
            if self.sel >= n:
                self.sel = None
        elif kk == ENTER:
            self.ed.insert(self.hist[self.sel][0])
            self.sel = None
        elif kk == RIGHT or k.key == "/":
            e = self.hist[self.sel]
            if not (len(e) > 4 and e[4]):
                s = e[1]
                if e[3] and e[2]:
                    s = e[5] if (settings.get("mixedfrac") and len(e) > 5 and e[5]) else e[2]
                if "/" in s and self.ed.text:
                    s = "(" + s + ")"  # old linear form: 2^(1/2), not 2^1/2
                self.ed.insert(s)
            self.sel = None
        elif kk in (BS, DEL):
            del self.hist[self.sel]
            if self.sel >= len(self.hist):
                self.sel = None if not self.hist else len(self.hist) - 1
        elif kk == ESC or kk == LEFT:
            self.sel = None
        elif ui.fkey(k) == 0:
            self.toggle_exact()
        else:
            self.sel = None
            return k
        return None

    def run(self):
        while True:
            self.draw()
            k = hal.wait_key()
            if self.sel is not None:
                k = self.history_key(k)
                if k is None:
                    continue
            fk = ui.fkey(k)
            if fk is not None:
                if fk == 0:
                    self.toggle_exact()
                elif fk == 1:
                    self.show_vars()
                elif fk == 2:
                    self.cycle_angle()
                elif fk == 3:
                    self.choose_format()
                elif fk == 4:
                    if self.hist and ui.confirm("Clear history?"):
                        self.hist = []
                elif fk == 5:
                    ui.show_keymap_help()
                continue
            if k.base == "h" and k.mods & hal.FN:
                ui.show_keymap_help()
                continue
            if k.key in (UP, DOWN) and self.ed.updown(k.key):
                continue  # inside a fraction: numerator <-> denominator
            if k.key == UP:
                if self.hist:
                    self.sel = len(self.hist) - 1
                continue
            if k.key == DOWN:
                continue
            # typing an operator on an empty line continues from Ans
            if not self.ed.text and self.hist:
                from cardgcalc import keymap

                tok = keymap.lookup(k) if k.mods & (hal.OPT | hal.ALT) else k.key
                if k.mods & (hal.OPT | hal.ALT) and k.base == "/":
                    tok = None  # fraction template, not ÷
                if tok in _OPS_ANS:
                    self.ed.insert("Ans")
            r = self.ed.handle(k)
            if r == "enter":
                src = self.ed.text.strip()
                if not src:
                    if self.hist:
                        src = self.hist[-1][0]
                    else:
                        continue
                self.evaluate(src)
                self.ed.set("")
            elif r == "esc":
                if self.ed.text:
                    self.ed.set("")
                else:
                    break
        self.save()

    def save(self):
        storage.save_json("calc_hist.json", self.hist[-MAXHIST:])
        state.save_vars()


def run():
    Calc().run()
