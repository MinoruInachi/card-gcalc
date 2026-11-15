# Calc: the main calculation screen (history + input line).
#
#   Enter        evaluate            (empty line: repeat last)
#   ; / .        (fn) browse history; Enter inserts expression, → inserts result
#   F1 Exact       toggle exact form (fraction / π / √) of the result
#   F2 Vars      list variables
#   F3 Angle     cycle DEG / RAD / GRA
#   F4 Format    Norm / Fix / Sci / Eng
#   F5 Clear     clear history
#   F6 Keys      math key map
#   expr→A  /  A=expr   store to a variable
from nc import hal, gfx, ui, settings, state, storage
from nc.i18n import T
from nc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL
from nc.calc import numfmt
from nc.calc.expr import CalcError

MAXHIST = 40
_OPS_ANS = ("+", "-", "×", "÷", "^", "²", "³", "!", "⁻¹", "→", "%", "*", "/")


class Calc:
    def __init__(self):
        self.ctx = state.ctx()
        self.hist = storage.load_json("calc_hist.json", []) or []
        self.ed = ui.LineEdit("", math=True, font="medium")
        self.sel = None  # selected history index (None = editing)
        self.f_in = gfx.font("normal")
        self.f_out = gfx.font("medium")
        self.f_big = gfx.font("large")

    # ---- evaluation ------------------------------------------------------
    def fmt(self, v):
        return numfmt.fmt(v, settings.get("fmt"), settings.get("digits"))

    def evaluate(self, src):
        try:
            v = self.ctx.evaluate(src)
            out = self.fmt(v)
            ex = None
            if not isinstance(v, int):
                ex = numfmt.exact(v)  # None for integers and complex values
            entry = [src, out, ex, 0]
        except CalcError as e:
            entry = [src, str(e), None, 0]
            entry.append(1)  # error flag
        except Exception as e:
            entry = [src, "Error: %s" % e, None, 0, 1]
        self.hist.append(entry)
        if len(self.hist) > MAXHIST:
            self.hist.pop(0)

    # ---- drawing -----------------------------------------------------------
    def draw(self):
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("Calc", self._right())
        # input box
        iy = ui.BOT - 17
        fb.fill_rect(0, iy - 2, ui.W, 19, gfx.PANEL)
        fb.hline(0, iy - 2, ui.W, gfx.PANEL2)
        self.ed.draw(4, iy + 1, ui.W - 8, bg=gfx.PANEL, cursor=self.sel is None)
        # history, newest at the bottom
        y = iy - 4
        i = len(self.hist) - 1
        fi = self.f_in
        fo = self.f_out
        while i >= 0 and y > ui.TOP:
            e = self.hist[i]
            src, out = e[0], e[1]
            err = len(e) > 4 and e[4]
            shown = e[2] if (e[3] and e[2]) else out
            if err:
                shown = T(shown)
            fo_ = fo
            h = fi.h + fo_.h + 3
            top = y - h
            if self.sel == i:
                fb.fill_rect(0, max(ui.TOP, top), ui.W, y - max(ui.TOP, top) + 1, gfx.SEL)
            # expression (left)
            if top + 1 >= ui.TOP:
                fi.text(fi.clip(src, ui.W - 6), 3, top + 1, gfx.DIM if self.sel != i else gfx.FG)
            # result (right)
            ry = top + fi.h + 2
            if ry >= ui.TOP:
                col = gfx.ERR if err else (gfx.ACCENT2 if e[3] and e[2] else gfx.FG)
                s = fo_.clip(shown, ui.W - 8)
                fo_.text(s, ui.W - 4 - fo_.width(s), ry, col)
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
        items = [(n, self.fmt(v[n])) for n in names]
        i = ui.menu("Variables (Enter: insert)", items)
        if i is not None:
            self.ed.insert(names[i])

    def cycle_angle(self):
        a = settings.get("angle")
        a = {"rad": "deg", "deg": "grad", "grad": "rad"}[a]
        settings.set("angle", a)
        self.ctx.angle = a

    def choose_format(self):
        opts = ["Norm", "Fix", "Sci", "Eng", T("Complex") + ": " + T("on" if settings.get("complex") else "off")]
        i = ui.menu("Display format", opts)
        if i is None:
            return
        if i == 4:
            settings.set("complex", not settings.get("complex"))
            self.ctx.complex = settings.get("complex")
            return
        mode = ("norm", "fix", "sci", "eng")[i]
        settings.set("fmt", mode)
        if mode != "norm":
            n = ui.input_number("Digits (0-9)" if mode == "fix" else "Significant digits (1-10)",
                                settings.get("digits"))
            if n is not None:
                n = int(n)
                n = max(0 if mode == "fix" else 1, min(9 if mode == "fix" else 10, n))
                settings.set("digits", n)
        else:
            settings.set("digits", 10)

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
                self.ed.insert(e[2] if (e[3] and e[2]) else e[1])
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
            if k.key == UP:
                if self.hist:
                    self.sel = len(self.hist) - 1
                continue
            if k.key == DOWN:
                continue
            # typing an operator on an empty line continues from Ans
            if not self.ed.text and self.hist:
                from nc import keymap

                tok = keymap.lookup(k) if k.mods & (hal.OPT | hal.ALT) else k.key
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
