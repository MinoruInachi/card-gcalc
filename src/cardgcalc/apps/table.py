# Table: numeric table of the enabled y=f(x) functions (shared with Graph).
#
#   arrows       move the cell cursor (scrolls without limit, columns scroll
#                horizontally when they do not fit)
#   Enter        on the x column: jump to an x value; on a Y cell: show value
#   F1 Start  F2 Step  F3 Y= (edit functions)  F4 Go to x  F5 Graph
#
# x values are decimal (bcd.D): start + row * step is exact (0.1, 0.2, 0.3 ...).
import gc
import sys
import bcd
from bcd import D
from cardgcalc import hal, gfx, ui, funcs, state
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC
from cardgcalc.calc import numfmt
from cardgcalc.i18n import T

XW = 54  # x column width
CW = 62  # function column width
ROWH = 11
HEAD = 12
_ALT = hal.rgb(22, 25, 33)
ROWS = (ui.BOT - ui.TOP - HEAD - 12) // ROWH


def _cell(v, w):
    """Format v to fit in w pixels (6 px per char)."""
    if v is None:
        return T("undef")
    n = w // 6 - 1
    s = numfmt.fmt(v)
    if len(s) <= n:
        return s
    if not isinstance(v, D):
        return T("cplx")
    for sig in range(min(10, n), 0, -1):
        s = numfmt.fmt(bcd.rsig(v, sig))
        if "E" not in s and len(s) <= n:
            return s
    for sig in range(max(1, n - 5), 0, -1):
        s = numfmt.fmt_real(v, "sci", sig)
        if len(s) <= n:
            return s
    return "#"


class Table:
    def __init__(self, from_graph=False):
        self.from_graph = from_graph
        self.row = 0  # selected row (absolute, may be negative)
        self.top = 0  # first visible row
        self.col = 0  # 0 = x column, 1.. = function columns
        self.left = 0  # first visible function column
        self.cols = []
        self.fns = []
        self.errors = []

    def compile(self):
        self.cols = []
        self.fns = []
        self.errors = []
        for i in funcs.active("y"):
            try:
                self.fns.append(funcs.safe(funcs.compile(i)))
                self.cols.append(i)
            except Exception as e:
                self.errors.append("%s: %s" % (funcs.label(i), T(str(e))))

    def x_at(self, r):
        t = funcs.table()
        return t["start"] + r * t["step"]

    def nvis(self):
        return max(1, (ui.W - XW) // CW)

    def draw(self):
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("Table")
        f = gfx.font("normal")
        y0 = ui.TOP
        # header
        fb.fill_rect(0, y0, ui.W, HEAD, gfx.PANEL)
        f.text("x", (XW - 6) // 2, y0 + 1, gfx.ACCENT)
        nv = self.nvis()
        vis = range(self.left, min(len(self.cols), self.left + nv))
        for j, c in enumerate(vis):
            x = XW + j * CW
            lab = funcs.label(self.cols[c])
            f.text(lab, x + (CW - f.width(lab)) // 2, y0 + 1, gfx.SERIES[self.cols[c] % 6])
            fb.vline(x, y0, HEAD + ROWS * ROWH, gfx.PANEL2)
        if self.left > 0:
            f.text("◀", XW + 1, y0 + 1, gfx.DIM)
        if self.left + nv < len(self.cols):
            f.text("▶", ui.W - 7, y0 + 1, gfx.DIM)
        # rows
        for r in range(ROWS):
            ar = self.top + r
            y = y0 + HEAD + r * ROWH
            x = self.x_at(ar)
            if r % 2:
                fb.fill_rect(0, y, ui.W, ROWH, _ALT)
            selrow = ar == self.row
            if selrow and self.col == 0:
                fb.fill_rect(0, y, XW, ROWH, gfx.SEL)
            s = _cell(x, XW)
            f.text(s, XW - 3 - f.width(s), y + 1, gfx.ACCENT if not selrow else gfx.YELLOW)
            for j, c in enumerate(vis):
                cx = XW + j * CW
                if selrow and self.col == c + 1:
                    fb.fill_rect(cx + 1, y, CW - 1, ROWH, gfx.SEL)
                v = self.fns[c](x)
                s = _cell(v, CW)
                f.text(s, cx + CW - 3 - f.width(s), y + 1, gfx.FG if v is not None else gfx.DIM)
        fb.hline(0, y0 + HEAD - 1, ui.W, gfx.PANEL2)
        # info line: full value of the selected cell
        iy = ui.BOT - 12
        fb.fill_rect(0, iy, ui.W, 12, gfx.PANEL)
        x = self.x_at(self.row)
        if self.col == 0 or not self.cols:
            info = "x=%s" % numfmt.fmt(x)
        else:
            c = self.col - 1
            v = self.fns[c](x)
            info = "%s(%s)=%s" % (funcs.label(self.cols[c]), numfmt.fmt(x),
                                  numfmt.fmt(v) if v is not None else T("undefined"))
        f.text(f.clip(info, ui.W - 4), 2, iy + 1, gfx.FG)
        ui.softkeys(["Start", "Step", "Y=", "Go to x", "Graph" if not self.from_graph else "", ""])
        gfx.show()

    def scroll_into_view(self):
        if self.row < self.top:
            self.top = self.row
        if self.row >= self.top + ROWS:
            self.top = self.row - ROWS + 1
        if self.col > 0:
            c = self.col - 1
            nv = self.nvis()
            if c < self.left:
                self.left = c
            if c >= self.left + nv:
                self.left = c - nv + 1

    def ask(self, title, value):
        v = ui.input_number(T("%s (now %s)") % (T(title), numfmt.fmt(value)), None, state.ctx())
        return funcs.real(v) if v is not None else None

    def goto_x(self):
        x = self.ask("Go to x", self.x_at(self.row))
        if x is None:
            return
        t = funcs.table()
        if t["step"] == 0:
            return
        r = (x - t["start"]) / t["step"]
        ri = int(bcd.rnd(r))
        if abs(r - ri) < D("1e-9"):
            self.row = ri
            self.top = ri - ROWS // 2
        else:
            # not on the grid: restart the table at x
            t["start"] = x
            self.row = 0
            self.top = 0
            funcs.save()

    def run(self):
        self.compile()
        if self.errors:
            ui.message("Table", self.errors[:4])
        while True:
            self.scroll_into_view()
            self.draw()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            t = funcs.table()
            if fk == 0:
                v = self.ask("Table start", t["start"])
                if v is not None:
                    t["start"] = v
                    self.row = self.top = 0
                    funcs.save()
            elif fk == 1:
                v = self.ask("Table step", t["step"])
                if v is not None:
                    if v == 0:
                        ui.error("Step must not be 0")
                    else:
                        t["step"] = v
                        funcs.save()
            elif fk == 2:
                _edit_functions()
                self.compile()
                self.col = min(self.col, len(self.cols))
                self.left = 0
            elif fk == 3:
                self.goto_x()
            elif fk == 4 and not self.from_graph:
                _run_graph()
                self.compile()
                self.col = min(self.col, len(self.cols))
            elif kk == UP:
                self.row -= 1
            elif kk == DOWN:
                self.row += 1
            elif kk == "PGUP":
                self.row -= ROWS
            elif kk == "PGDN":
                self.row += ROWS
            elif kk == LEFT:
                if self.col > 0:
                    self.col -= 1
            elif kk == RIGHT:
                if self.col < len(self.cols):
                    self.col += 1
            elif kk == ENTER:
                if self.col == 0:
                    self.goto_x()
                else:
                    c = self.col - 1
                    x = self.x_at(self.row)
                    v = self.fns[c](x)
                    ui.message(funcs.label(self.cols[c]),
                               ["x = %s" % numfmt.fmt(x),
                                "y = %s" % (numfmt.fmt(v) if v is not None else T("undefined"))])
            elif kk == "HOME":
                self.row = self.top = 0
            elif kk == ESC:
                return
            elif len(kk) == 1 and (kk.isdigit() or kk == "-") and self.col == 0:
                # typing a number on the x column jumps to that x
                s = ui.input_line("Go to x", kk, typed=True)
                if s is not None:
                    try:
                        x = funcs.real(ui.evaluate(s, state.ctx()))
                        if x is None:
                            raise ValueError("Non-real error")
                        t["start"] = x
                        self.row = self.top = 0
                        funcs.save()
                    except Exception as e:
                        ui.error(T(str(e)))


def _edit_functions():
    loaded = "cardgcalc.apps.graph" in sys.modules
    try:
        import cardgcalc.apps.graph as g

        g.FuncList(can_draw=False).run()
    finally:
        if not loaded:
            sys.modules.pop("cardgcalc.apps.graph", None)
        gc.collect()


def _run_graph():
    loaded = "cardgcalc.apps.graph" in sys.modules
    try:
        import cardgcalc.apps.graph as g

        gv = g.GraphView()
        gv.run()
        funcs.save()
    finally:
        if not loaded:
            sys.modules.pop("cardgcalc.apps.graph", None)
        gc.collect()


def run(from_graph=False):
    Table(from_graph).run()
    funcs.save()
