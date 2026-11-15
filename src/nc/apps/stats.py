# Stats: list editor, 1/2-variable statistics, regressions, plots, distributions.
#
# List data and all results are decimal (bcd.D); floats are only used to map
# values to pixels.
import math
import bcd
from bcd import D
from nc import hal, gfx, ui, storage
from nc.calc import dec
from nc.calc.dec import DC, num, isreal, ZERO
from nc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC
from nc.calc import statlib
from nc.calc.gridedit import Grid, result_list, form, fmt, fmt_fit, evaluate
from nc.i18n import T

NAMES = ("L1", "L2", "L3")


class _Lists:
    def __init__(self):
        d = storage.load_json("stats.json", None) or {}
        self.L = [[num(v) for v in d.get(n, []) if isreal(v)] for n in NAMES]

    def save(self):
        storage.save_json("stats.json", {n: [v for v in self.L[i] if isreal(v)]
                                         for i, n in enumerate(NAMES)})

    # Grid model
    def rows(self):
        return max(len(l) for l in self.L) + 1

    def cols(self):
        return 3

    def get(self, r, c):
        l = self.L[c]
        return l[r] if r < len(l) else None

    def set(self, r, c, v):
        l = self.L[c]
        if v is None:
            if r < len(l):
                l.pop(r)
            return
        if not isreal(v):
            ui.error("Real numbers only")
            return
        v = num(v)
        while len(l) < r:
            l.append(ZERO)
        if r < len(l):
            l[r] = v
        else:
            l.append(v)

    def col_title(self, c):
        return "%s (%d)" % (NAMES[c], len(self.L[c]))

    def row_label(self, r):
        return str(r + 1)

    def cell_name(self, r, c):
        return "%s[%d]" % (NAMES[c], r + 1)


def _pick(title, allow_none=False, sel=0):
    items = list(NAMES)
    if allow_none:
        items = ["None (all 1)"] + items
    i = ui.menu(title, items, sel)
    if i is None:
        return -2
    if allow_none:
        return i - 1
    return i


# ---- statistics ----------------------------------------------------------------
def one_var(d):
    x = _pick("1-Var: data list")
    if x < 0:
        return
    f = _pick("1-Var: frequency", True)
    if f == -2:
        return
    xs = d.L[x]
    fs = d.L[f] if f >= 0 else None
    try:
        rows = statlib.one_var(xs, fs)
    except Exception as e:
        ui.error(str(e))
        return
    result_list("1-Var stats", rows, header="%s%s" % (NAMES[x], ("  %s: %s" % (T("freq"), NAMES[f])) if fs else ""))


def two_var(d):
    x = _pick("2-Var: X list")
    if x < 0:
        return
    y = _pick("2-Var: Y list", sel=min(2, x + 1))
    if y < 0:
        return
    try:
        rows = statlib.two_var(d.L[x], d.L[y])
    except Exception as e:
        ui.error(str(e))
        return
    result_list("2-Var stats", rows, header="X=%s Y=%s" % (NAMES[x], NAMES[y]))


def _pick_reg():
    i = ui.menu("Regression", [lab for _, lab in statlib.REGRESSIONS])
    if i is None:
        return None
    return statlib.REGRESSIONS[i][0]


def regression(d, plot_after=False):
    x = _pick("Regression: X list")
    if x < 0:
        return
    y = _pick("Regression: Y list", sel=min(2, x + 1))
    if y < 0:
        return
    kind = _pick_reg()
    if kind is None:
        return
    try:
        reg = statlib.regression(kind, d.L[x], d.L[y])
    except Exception as e:
        ui.error(str(e))
        return
    if plot_after:
        scatter(d.L[x], d.L[y], reg)
        return
    rows = [("form", reg["form"])] + reg["coef"]
    if reg["r"] is not None:
        rows.append(("r", reg["r"]))
    if reg["r2"] is not None:
        rows.append(("r²", reg["r2"]))
    rows.append(("y=", _reg_text(reg)))
    result_list("Regression", rows, header="X=%s Y=%s  %s" % (NAMES[x], NAMES[y], T("Enter: store")))


def _reg_text(reg):
    """Readable equation with rounded coefficients."""
    c = dict(reg["coef"])
    f = lambda v: fmt_fit(v, 8)
    form = reg["form"][2:]
    for k in ("a", "b", "c"):
        if k in c:
            form = form.replace(k, "(" + f(c[k]) + ")" if c[k] < 0 else f(c[k]), 1)
    return form


# ---- plots -----------------------------------------------------------------------
class _Plot:
    def __init__(self, xmin, xmax, ymin, ymax):
        xmin, xmax, ymin, ymax = num(xmin), num(xmax), num(ymin), num(ymax)
        if xmax == xmin:
            xmin -= 1
            xmax += 1
        if ymax == ymin:
            ymin -= 1
            ymax += 1
        px = (xmax - xmin) * D("0.08")
        py = (ymax - ymin) * D("0.1")
        self.x0 = xmin - px
        self.x1 = xmax + px
        self.y0 = ymin - py
        self.y1 = ymax + py
        self.L = 0
        self.T = ui.TOP
        self.W = ui.W
        self.H = ui.BOT - 12 - ui.TOP
        self._scale()

    def _scale(self):
        # pixel mapping in float (values themselves stay decimal)
        self._fx0 = dec.f(self.x0)
        self._fy1 = dec.f(self.y1)
        self._kx = (self.W - 1) / (dec.f(self.x1) - self._fx0)
        self._ky = (self.H - 1) / (self._fy1 - dec.f(self.y0))

    def set_y0(self, y0):
        self.y0 = num(y0)
        self._scale()

    def _px(self, v):
        v = dec.f(v)
        # keep huge values inside the int range of framebuf
        return max(-30000.0, min(30000.0, v))

    def sx(self, x):
        return int(self.L + self._px((dec.f(x) - self._fx0) * self._kx))

    def sy(self, y):
        return int(self.T + self._px((self._fy1 - dec.f(y)) * self._ky))

    def frame(self, title):
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar(title)
        if self.x0 < 0 < self.x1:
            fb.vline(self.sx(0), self.T, self.H, gfx.AXIS)
        if self.y0 < 0 < self.y1:
            fb.hline(0, self.sy(0), self.W, gfx.AXIS)

    def info(self, text):
        f = gfx.font("small")
        for s, x, y in ((fmt_fit(self.y1, 9), 2, self.T + 1), (fmt_fit(self.y0, 9), 2, self.T + self.H - 9),
                        (fmt_fit(self.x1, 9), -1, self.T + self.H - 9)):
            if x < 0:
                x = self.W - 2 - f.width(s)
            gfx.fb().fill_rect(x - 1, y, f.width(s) + 2, 8, gfx.BG)
            f.text(s, x, y, gfx.DIM)
        fb = gfx.fb()
        fb.fill_rect(0, ui.BOT - 12, ui.W, ui.H - ui.BOT + 12, gfx.PANEL)
        gfx.font("normal").text(gfx.font("normal").clip(text, ui.W - 4), 3, ui.BOT - 10, gfx.FG)
        gfx.font("small").text(T("<- -> trace   ` back"), 3, ui.BOT + 2, gfx.DIM)

    def curve(self, f, col):
        fb = gfx.fb()
        prev = None
        top = self.T
        bot = self.T + self.H - 1
        for px in range(self.W):
            x = self.x0 + (self.x1 - self.x0) * px / (self.W - 1)
            try:
                y = f(x)
                if not isreal(y):
                    raise ValueError
                py = self.sy(y)
            except Exception:
                prev = None
                continue
            if prev is not None and not ((prev < top and py < top) or (prev > bot and py > bot)):
                fb.line(px - 1, max(top, min(bot, prev)), px, max(top, min(bot, py)), col)
            prev = py


def scatter(xs, ys, reg=None):
    n = min(len(xs), len(ys))
    if n == 0:
        ui.error("No data")
        return
    pts = sorted(zip(xs[:n], ys[:n]))
    ylo = min(p[1] for p in pts)
    yhi = max(p[1] for p in pts)
    p = _Plot(pts[0][0], pts[-1][0], ylo, yhi)
    i = 0
    title = T("Scatter") if reg is None else T("Regression") + " " + reg["form"]
    while True:
        p.frame(title)
        fb = gfx.fb()
        if reg is not None:
            p.curve(reg["f"], gfx.SERIES[1])
        for (x, y) in pts:
            cx, cy = p.sx(x), p.sy(y)
            fb.fill_rect(cx - 1, cy - 1, 3, 3, gfx.SERIES[0])
        x, y = pts[i]
        cx, cy = p.sx(x), p.sy(y)
        fb.rect(cx - 3, cy - 3, 7, 7, gfx.YELLOW)
        txt = "x=%s y=%s" % (fmt_fit(x, 10), fmt_fit(y, 10))
        if reg is not None:
            txt += "  " + _reg_text(reg)
        p.info(txt)
        gfx.show()
        k = hal.wait_key().nav()
        if k == RIGHT:
            i = (i + 1) % n
        elif k == LEFT:
            i = (i - 1) % n
        elif k in (ESC, ENTER):
            return


def histogram(xs, fs=None):
    try:
        pr = statlib._pairs(xs, fs)
    except Exception as e:
        ui.error(str(e))
        return
    if not pr:
        ui.error("No data")
        return
    lo = min(x for x, _ in pr)
    hi = max(x for x, _ in pr)
    n = sum(dec.f(f) for _, f in pr)
    k = int(math.ceil(math.log(max(n, 1)) / math.log(2))) + 1
    k = max(1, min(20, k))
    w = bcd.rsig((hi - lo) / k, 3) if hi > lo else D(1)
    s = ui.input_line("Bin width", fmt(w), prompt=T("start=%s") % fmt(lo))
    if s is None:
        return
    try:
        w = evaluate(s)
        if not isreal(w) or w <= 0:
            raise ValueError
        w = num(w)
        k = max(1, int(bcd.ceil((hi - lo) / w)))
    except Exception:
        ui.error("Invalid width")
        return
    if lo + k * w <= hi:
        k += 1
    if k > 120:
        ui.error("Too many bins")
        return
    cnt = [ZERO] * k
    for x, f in pr:
        b = int(bcd.floor((x - lo) / w))
        if b >= k:
            b = k - 1
        cnt[b] = cnt[b] + f
    p = _Plot(lo, lo + k * w, 0, max(cnt))
    p.set_y0(0)
    i = 0
    while True:
        p.frame("Histogram")
        fb = gfx.fb()
        for b in range(k):
            x0 = p.sx(lo + b * w)
            x1 = p.sx(lo + (b + 1) * w)
            y = p.sy(cnt[b])
            yb = p.sy(0)
            col = gfx.YELLOW if b == i else gfx.SERIES[1]
            fb.fill_rect(x0, y, max(1, x1 - x0), yb - y, col)
            fb.rect(x0, y, max(1, x1 - x0 + 1), yb - y + 1, gfx.BG)
        p.info("[%s, %s)  n=%s" % (fmt_fit(lo + i * w, 9), fmt_fit(lo + (i + 1) * w, 9), fmt(cnt[i])))
        gfx.show()
        kk = hal.wait_key().nav()
        if kk == RIGHT:
            i = (i + 1) % k
        elif kk == LEFT:
            i = (i - 1) % k
        elif kk in (ESC, ENTER):
            return


def boxplot(d):
    data = [(NAMES[j], d.L[j]) for j in range(3) if d.L[j]]
    if not data:
        ui.error("No data")
        return
    boxes = []
    for name, xs in data:
        try:
            boxes.append((name, statlib.box_stats(xs)))
        except Exception as e:
            ui.error(str(e))
            return
    lo = min(b[1][0] for b in boxes)
    hi = max(b[1][4] for b in boxes)
    p = _Plot(lo, hi, 0, 1)
    i = 0
    nb = len(boxes)
    while True:
        p.frame("Box plot")
        fb = gfx.fb()
        f = gfx.font("small")
        bh = min(24, (p.H - 6) // nb - 6)
        for j, (name, (mn, q1, md, q3, mx)) in enumerate(boxes):
            yc = p.T + 6 + j * (p.H - 6) // nb + bh // 2 + 3
            col = gfx.SERIES[j]
            fb.hline(p.sx(mn), yc, p.sx(q1) - p.sx(mn), col)
            fb.hline(p.sx(q3), yc, p.sx(mx) - p.sx(q3), col)
            fb.vline(p.sx(mn), yc - bh // 4, bh // 2, col)
            fb.vline(p.sx(mx), yc - bh // 4, bh // 2, col)
            fb.rect(p.sx(q1), yc - bh // 2, max(1, p.sx(q3) - p.sx(q1) + 1), bh, gfx.YELLOW if j == i else col)
            fb.vline(p.sx(md), yc - bh // 2, bh, gfx.FG)
            f.text(name, ui.W - 14, yc - bh // 2 - 1, col)
        mn, q1, md, q3, mx = boxes[i][1]
        p.info("%s %s|%s|%s|%s|%s" % (boxes[i][0], fmt_fit(mn, 6), fmt_fit(q1, 6), fmt_fit(md, 6),
                                       fmt_fit(q3, 6), fmt_fit(mx, 6)))
        gfx.show()
        kk = hal.wait_key().nav()
        if kk in (DOWN, RIGHT):
            i = (i + 1) % nb
        elif kk in (UP, LEFT):
            i = (i - 1) % nb
        elif kk in (ESC, ENTER):
            return


def graph_menu(d):
    i = ui.menu("Graph", ["Scatter plot", "Scatter + regression", "Histogram", "Box plot (all lists)"])
    if i is None:
        return
    if i == 0:
        x = _pick("Scatter: X list")
        if x < 0:
            return
        y = _pick("Scatter: Y list", sel=min(2, x + 1))
        if y < 0:
            return
        scatter(d.L[x], d.L[y])
    elif i == 1:
        regression(d, plot_after=True)
    elif i == 2:
        x = _pick("Histogram: data list")
        if x < 0:
            return
        f = _pick("Histogram: frequency", True)
        if f == -2:
            return
        histogram(d.L[x], d.L[f] if f >= 0 else None)
    else:
        boxplot(d)


# ---- distributions -----------------------------------------------------------
def _evalx(t):
    """Evaluate a field; '∞' / '-∞' give float infinities (bounds only)."""
    s = t.strip().replace("−", "-")
    if s in ("∞", "+∞"):
        return math.inf
    if s == "-∞":
        return -math.inf
    v = evaluate(t)
    if not isreal(v):
        raise ValueError("Real numbers only")
    return v


_DISTS = (
    ("Normal pdf", [["x", "0"], ["μ", "0"], ["σ", "1"]]),
    ("Normal cdf", [["Lower", "-1"], ["Upper", "1"], ["μ", "0"], ["σ", "1"]]),
    ("Inverse normal", [["Area", "0.95"], ["μ", "0"], ["σ", "1"], ["Tail L/R/C", "L"]]),
    ("Binomial pdf", [["x", "3"], ["n", "10"], ["p", "0.5"]]),
    ("Binomial cdf", [["x", "3"], ["n", "10"], ["p", "0.5"]]),
    ("Poisson pdf", [["x", "2"], ["λ", "3"]]),
    ("Poisson cdf", [["x", "2"], ["λ", "3"]]),
)


def distributions():
    sel = 0
    while True:
        i = ui.menu("Distributions", [n for n, _ in _DISTS], sel)
        if i is None:
            return
        sel = i
        name, fields = _DISTS[i]
        while True:
            r = form(name, fields, submit="Calc")
            if r is not True:
                break
            try:
                if i == 2:
                    vals = [evaluate(t) for _, t in fields[:3]]
                    tail = {"L": "left", "R": "right", "C": "center"}.get(fields[3][1].strip()[:1].upper(), "left")
                    res = statlib.inv_norm(vals[0], vals[1], vals[2], tail)
                    if tail == "center":
                        rows = [("x1", res[0]), ("x2", res[1])]
                    else:
                        rows = [("x", res)]
                else:
                    vals = [_evalx(t) for _, t in fields]
                    if i == 0:
                        rows = [("p(x)", statlib.norm_pdf(*vals))]
                    elif i == 1:
                        p = statlib.norm_cdf(*vals)
                        rows = [("P", p)]
                        for lab, v in (("z low", vals[0]), ("z up", vals[1])):
                            if not isinstance(v, float):  # not ±∞
                                rows.append((lab, (v - vals[2]) / vals[3]))
                    elif i == 3:
                        rows = [("P(X=x)", statlib.binom_pdf(*vals))]
                    elif i == 4:
                        rows = [("P(X≤x)", statlib.binom_cdf(*vals))]
                    elif i == 5:
                        rows = [("P(X=x)", statlib.poisson_pdf(*vals))]
                    else:
                        rows = [("P(X≤x)", statlib.poisson_cdf(*vals))]
            except Exception as e:
                ui.error(str(e))
                continue
            result_list(name, rows)


# ---- list operations -------------------------------------------------------------
def list_ops(d, col):
    nm = NAMES[col]
    i = ui.menu(T("List %s") % nm, [T("Sort ascending"), T("Sort descending"), T("Clear %s") % nm,
                                    T("Clear all lists"), T("Fill sequence..."), T("Copy %s to...") % nm])
    if i is None:
        return
    l = d.L[col]
    if i == 0:
        l.sort()
    elif i == 1:
        l.sort(reverse=True)
    elif i == 2:
        if ui.confirm(T("Clear %s?") % NAMES[col]):
            del l[:]
    elif i == 3:
        if ui.confirm("Clear all lists?"):
            for x in d.L:
                del x[:]
    elif i == 4:
        fields = [["Expr in x", "x"], ["x start", "1"], ["x end", "10"], ["step", "1"]]
        if form(T("Fill %s") % NAMES[col], fields, submit="Fill") is not True:
            return
        try:
            from nc import state

            f = state.ctx().function(fields[0][1])
            a, b, s = [evaluate(t) for _, t in fields[1:]]
            if s == 0 or (b - a) / s > 999:
                raise ValueError("Too many items")
            out = []
            k = 0
            while True:
                x = a + k * s
                if (s > 0 and x > b) or (s < 0 and x < b):
                    break
                v = f(x)
                if not isreal(v):
                    raise ValueError("Real numbers only")
                out.append(num(v))
                k += 1
            l[:] = out
        except Exception as e:
            ui.error(str(e))
    elif i == 5:
        j = _pick(T("Copy %s to") % NAMES[col])
        if j >= 0 and j != col:
            d.L[j][:] = l[:]
    d.save()


def run():
    d = _Lists()

    def fkey(fk, g):
        if fk == 0:
            i = ui.menu("Statistics", ["1-Var stats", "2-Var stats", "Regression"])
            if i == 0:
                one_var(d)
            elif i == 1:
                two_var(d)
            elif i == 2:
                regression(d)
        elif fk == 1:
            graph_menu(d)
        elif fk == 2:
            distributions()
        elif fk == 3:
            l = d.L[g.c]
            if g.r <= len(l):
                l.insert(g.r, ZERO)
        elif fk == 4:
            d.set(g.r, g.c, None)
        elif fk == 5:
            list_ops(d, g.c)
        return None

    g = Grid("Stats", d, colw=(ui.W - 22) // 3, labelw=22,
             keys=["Stats", "Graph", "Dist", "Ins", "Del", "List"], on_fkey=fkey)
    try:
        g.run()
    finally:
        d.save()
