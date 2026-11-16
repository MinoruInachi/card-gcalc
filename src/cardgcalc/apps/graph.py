# Graph: function plotter (y=f(x), polar r=f(θ), parametric x(t),y(t)).
#
# Function list (Y=) screen
#   ; .  select        Enter / type   edit          Space  on/off
#   F1 On/Off  F2 Type  F3 View  F4 Zoom  F5 Table  F6 Draw     BS clear
# Graph screen
#   arrows pan   + / -  zoom in/out   F1 Trace  F2 Zoom  F3 View
#   F4 Analysis   F5 Y=  F6 Auto-fit   ` back
# Trace
#   ← →  move (fn+shift: ×10)   ↑ ↓  next function   digit: go to x
#   Enter  centre view on cursor   ` leave trace
# Analysis: Root, Min, Max, Intersect, y at x, x at y, dy/dx, ∫dx
#   ← → cycle through solutions in view
#
# Numbers (view window, trace x, Analysis results) are decimal (bcd.D); they
# are converted to float only to map them to pixels.
import gc
import math
import sys
from array import array
import bcd
from bcd import D
from cardgcalc import hal, gfx, ui, funcs, settings, state
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL, SHIFT, OPT, ALT, CTRL, FN
from cardgcalc.calc import numfmt
from cardgcalc.calc import fn as F
from cardgcalc.calc.expr import CalcError
from cardgcalc.i18n import T

ZERO = D(0)
_tof = bcd.tof

PW = hal.W
PY0 = ui.TOP
PH = ui.BOT - ui.TOP
UNDEF = -32768
_CLAMP = 30000


def _fmt(v, sig=10):
    """Value with at most sig significant digits (plain notation when it
    fits, otherwise the calculator format)."""
    if v is None:
        return T("undef")
    if isinstance(v, D) and sig < 10:
        if v == 0 or (_E4 <= abs(v) < bcd.pow10(sig)):
            return numfmt.fmt(bcd.rsig(v, sig))
    return numfmt.fmt(v)


_E4 = D("1e-4")
_E9 = D("1e-9")


def _lab(v, span):
    """Short axis label: 4 significant digits, E notation outside 1e-4..1e4."""
    if abs(v) < span * _E9:
        return "0"
    r = bcd.rsig(v, 4)
    neg, c, e = bcd.parts(r)
    x = e + 14  # exponent of the leading digit
    if -4 <= x < 4:
        return numfmt.fmt(r)
    m = ("%015d" % c).rstrip("0")
    m = m[0] + ("." + m[1:] if len(m) > 1 else "")
    return "%s%sE%d" % ("-" if neg else "", m, x)


def _nice(span, target):
    """1, 2 or 5 times a power of ten, about span/target."""
    if span <= 0:
        return D(1)
    raw = span / target
    mag = bcd.pow10(bcd.floor(bcd.log10(raw)))
    for m in (1, 2, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def _darken(c, k=3):
    r, g, b = hal.unrgb(c)
    return hal.rgb(r // k, g // k, b // k)


def _raising(g):
    def h(x):
        v = g(x)
        if v is None:
            raise ValueError
        return v

    return h


class Plot:
    """View-window mapping, compiled functions and the pixel cache."""

    def __init__(self):
        self.v = funcs.view()
        self.fns = {}
        self.cache = {}
        self.errors = []
        self._key = None

    # ---- mapping ---------------------------------------------------------
    def _map(self):
        """Float mapping constants for the current window (recomputed when
        one of the window values is replaced)."""
        v = self.v
        a, b, c, d = v["xmin"], v["xmax"], v["ymin"], v["ymax"]
        k = self._key
        if k is None or k[0] is not a or k[1] is not b or k[2] is not c or k[3] is not d:
            self._key = (a, b, c, d)
            fa, fb, fc, fd = _tof(a), _tof(b), _tof(c), _tof(d)
            self._fl = (fa, (PW - 1) / (fb - fa), fd, (PH - 1) / (fd - fc))
            self._span = b - a
        return self._fl

    def x_of(self, c):
        """x (decimal) of pixel column c."""
        self._map()
        return self.v["xmin"] + self._span * c / (PW - 1)

    def px(self, x):
        m = self._map()
        return (_tof(x) - m[0]) * m[1]

    def py(self, y):
        m = self._map()
        return PY0 + (m[2] - _tof(y)) * m[3]

    def ipy(self, y):
        p = self.py(y)
        if p > _CLAMP:
            return _CLAMP
        if p < -_CLAMP:
            return -_CLAMP
        return int(p + 0.5) if p >= 0 else -int(-p + 0.5)

    def ipx(self, x):
        p = self.px(x)
        if p > _CLAMP:
            return _CLAMP
        if p < -_CLAMP:
            return -_CLAMP
        return int(p + 0.5) if p >= 0 else -int(-p + 0.5)

    # ---- compile / compute ---------------------------------------------------
    def compile_all(self):
        self.fns = {}
        self.errors = []
        for i in funcs.active():
            try:
                f = funcs.compile(i)
                if isinstance(f, tuple):
                    self.fns[i] = (funcs.safe(f[0]), funcs.safe(f[1]))
                else:
                    self.fns[i] = funcs.safe(f)
            except Exception as e:
                self.errors.append("%s: %s" % (funcs.label(i), T(str(e))))

    def order(self):
        return sorted(self.fns)

    def kind(self, i):
        return funcs.funcs()[i]["type"]

    def t_values(self):
        v = self.v
        t0, t1, st = v["tmin"], v["tmax"], v["tstep"]
        if st <= 0 or t1 <= t0:
            return t0, ZERO, 1
        n = int(bcd.floor((t1 - t0) / st + _E9)) + 1
        if n > 720:
            n = 720
            st = (t1 - t0) / (n - 1)
        return t0, st, n

    def point(self, i, t):
        """(x, y) of a polar/param function at parameter t (or None)."""
        f = self.fns[i]
        if self.kind(i) == "r":
            r = f(t)
            if r is None:
                return None
            try:
                return funcs.polar(r, t)
            except Exception:
                return None
        x = f[0](t)
        y = f[1](t)
        if x is None or y is None:
            return None
        return x, y

    def compute(self):
        self.cache = {}
        for i in self.order():
            gc.collect()
            if self.kind(i) == "y":
                f = self.fns[i]
                arr = array("h", bytes(2 * PW))
                for c in range(PW):
                    y = f(self.x_of(c))
                    arr[c] = UNDEF if y is None else self.ipy(y)
                self.cache[i] = arr
            else:
                t0, st, n = self.t_values()
                arr = array("h", bytes(4 * n))
                for k in range(n):
                    p = self.point(i, t0 + k * st)
                    if p is None:
                        arr[2 * k] = UNDEF
                    else:
                        arr[2 * k] = self.ipx(p[0])
                        arr[2 * k + 1] = self.ipy(p[1])
                self.cache[i] = arr

    def continuous(self, f, c):
        """Is the y=f(x) curve continuous between columns c-1 and c?"""
        a = self.x_of(c - 1)
        b = self.x_of(c)
        va = f(a)
        vb = f(b)
        vm = f((a + b) / 2)
        if va is None or vb is None or vm is None:
            return False
        lo = min(va, vb)
        hi = max(va, vb)
        tol = (hi - lo) * 0.05
        return lo - tol <= vm <= hi + tol

    # ---- view changes -------------------------------------------------------
    def zoom(self, k, cx=None, cy=None):
        v = self.v
        if cx is None:
            cx = (v["xmin"] + v["xmax"]) / 2
        if cy is None:
            cy = (v["ymin"] + v["ymax"]) / 2
        hx = (v["xmax"] - v["xmin"]) / 2 * k
        hy = (v["ymax"] - v["ymin"]) / 2 * k
        v["xmin"], v["xmax"] = cx - hx, cx + hx
        v["ymin"], v["ymax"] = cy - hy, cy + hy

    def pan(self, dx, dy):
        v = self.v
        sx = (v["xmax"] - v["xmin"]) * dx
        sy = (v["ymax"] - v["ymin"]) * dy
        v["xmin"] += sx
        v["xmax"] += sx
        v["ymin"] += sy
        v["ymax"] += sy

    def set_standard(self):
        self.v.update({"xmin": D(-10), "xmax": D(10), "ymin": D(-5), "ymax": D(5), "xscl": D(1), "yscl": D(1)})

    def set_trig(self):
        if settings.get("angle") == "deg":
            self.v.update({"xmin": D(-360), "xmax": D(360), "xscl": D(90)})
        elif settings.get("angle") == "grad":
            self.v.update({"xmin": D(-400), "xmax": D(400), "xscl": D(100)})
        else:
            self.v.update({"xmin": -2 * bcd.pi, "xmax": 2 * bcd.pi, "xscl": bcd.pi / 2})
        self.v.update({"ymin": D("-1.6"), "ymax": D("1.6"), "yscl": D("0.5")})
        self.v.update(funcs.default_t())

    def set_integer(self):
        v = self.v
        cx = bcd.rnd((v["xmin"] + v["xmax"]) / 2)
        cy = bcd.rnd((v["ymin"] + v["ymax"]) / 2)
        v.update({"xmin": cx - 120, "xmax": cx + 119, "ymin": cy - 55,
                  "ymax": cy + 56, "xscl": D(10), "yscl": D(10)})

    def set_square(self):
        v = self.v
        cy = (v["ymin"] + v["ymax"]) / 2
        hy = (v["xmax"] - v["xmin"]) * (PH - 1) / (PW - 1) / 2
        v["ymin"], v["ymax"] = cy - hy, cy + hy

    def auto_fit(self):
        ys = []
        xs = []
        for i in self.order():
            if self.kind(i) == "y":
                f = self.fns[i]
                for c in range(0, PW, 2):
                    y = f(self.x_of(c))
                    if y is not None:
                        ys.append(y)
        pts_x = not ys
        if pts_x:
            for i in self.order():
                if self.kind(i) != "y":
                    t0, st, n = self.t_values()
                    for k in range(n):
                        p = self.point(i, t0 + k * st)
                        if p:
                            xs.append(p[0])
                            ys.append(p[1])
        if not ys:
            return False
        v = self.v
        lo, hi = _robust(ys)
        v["ymin"], v["ymax"] = lo, hi
        v["yscl"] = _nice(hi - lo, 8)
        if pts_x and xs:
            lo, hi = _robust(xs)
            v["xmin"], v["xmax"] = lo, hi
            # curves: keep a square aspect ratio
            ux = (hi - lo) / (PW - 1)
            uy = (v["ymax"] - v["ymin"]) / (PH - 1)
            u = max(ux, uy)
            cx = (v["xmin"] + v["xmax"]) / 2
            cy = (v["ymin"] + v["ymax"]) / 2
            v["xmin"], v["xmax"] = cx - u * (PW - 1) / 2, cx + u * (PW - 1) / 2
            v["ymin"], v["ymax"] = cy - u * (PH - 1) / 2, cy + u * (PH - 1) / 2
            v["xscl"] = _nice(v["xmax"] - v["xmin"], 8)
            v["yscl"] = v["xscl"]
        return True


def _robust(vals):
    vals.sort()
    n = len(vals)
    lo, hi = vals[0], vals[-1]
    lo2 = vals[n * 3 // 100]
    hi2 = vals[min(n - 1, n * 97 // 100)]
    if hi2 - lo2 > 0 and (hi - lo) > 20 * (hi2 - lo2):
        lo, hi = lo2, hi2
    if hi - lo < _E12:
        lo -= 1
        hi += 1
    m = (hi - lo) * _P08
    return lo - m, hi + m


_E12 = D("1e-12")
_P08 = D("0.08")


# ---------------------------------------------------------------------------
# Graph screen
# ---------------------------------------------------------------------------
class GraphView:
    def __init__(self):
        self.p = Plot()
        self.mode = "view"  # view | trace | solve
        self.tr = 0  # index into p.order()
        self.tx = ZERO  # trace x (y functions)
        self.tk = 0  # trace step (polar / param)
        self.info = None
        self.shade = None
        self.sols = []
        self.si = 0
        self.dirty = True

    # ---- drawing ---------------------------------------------------------------
    def draw_grid(self, fb):
        p = self.p
        v = p.v
        xr = v["xmax"] - v["xmin"]
        yr = v["ymax"] - v["ymin"]
        f = gfx.font("small")
        # grid lines
        for scl, rng, lo, vert in ((v["xscl"], xr, v["xmin"], True), (v["yscl"], yr, v["ymin"], False)):
            if scl <= 0:
                continue
            px_per = scl * ((PW - 1) / xr if vert else (PH - 1) / yr)
            if px_per < 5 or rng / scl > 200:
                continue
            k = bcd.ceil(lo / scl)
            while True:
                val = k * scl
                if val > lo + rng:
                    break
                if vert:
                    fb.vline(p.ipx(val), PY0, PH, gfx.GRID)
                else:
                    fb.hline(0, p.ipy(val), PW, gfx.GRID)
                k += 1
        # axes
        ax = p.ipx(0) if v["xmin"] <= 0 <= v["xmax"] else None
        ay = p.ipy(0) if v["ymin"] <= 0 <= v["ymax"] else None
        if ay is not None:
            fb.hline(0, ay, PW, gfx.AXIS)
        if ax is not None:
            fb.vline(ax, PY0, PH, gfx.AXIS)
        # ticks + labels
        lx = _nice(xr, 5)
        ly = _nice(yr, 4)
        base_y = ay if ay is not None else (PY0 + PH - 10)
        k = bcd.ceil(v["xmin"] / lx)
        while k * lx <= v["xmax"]:
            val = k * lx
            k += 1
            if abs(val) < xr * _E9:
                continue
            x = p.ipx(val)
            fb.vline(x, base_y - 2, 5, gfx.AXIS)
            s = _lab(val, xr)
            tw = f.width(s)
            ty = base_y + 4
            if ty + f.h > PY0 + PH:
                ty = base_y - 4 - f.h
            tx = min(max(0, x - tw // 2), PW - tw)
            f.text(s, tx, ty, gfx.DIM)
        base_x = ax if ax is not None else 0
        k = bcd.ceil(v["ymin"] / ly)
        while k * ly <= v["ymax"]:
            val = k * ly
            k += 1
            if abs(val) < yr * _E9:
                continue
            y = p.ipy(val)
            fb.hline(base_x - 2, y, 5, gfx.AXIS)
            s = _lab(val, yr)
            tw = f.width(s)
            tx = base_x + 4
            if tx + tw > PW:
                tx = base_x - 4 - tw
            ty = min(max(PY0, y - f.h // 2), PY0 + PH - f.h)
            f.text(s, tx, ty, gfx.DIM)

    def draw_shade(self, fb):
        if not self.shade:
            return
        i, a, b = self.shade
        p = self.p
        arr = p.cache.get(i)
        if arr is None:
            return
        col = _darken(gfx.SERIES[i % 6], 2)
        y0 = p.ipy(0)
        y0 = max(PY0, min(PY0 + PH - 1, y0))
        c0 = max(0, int(math.ceil(p.px(min(a, b)))))
        c1 = min(PW - 1, int(p.px(max(a, b))))
        for c in range(c0, c1 + 1):
            y = arr[c]
            if y == UNDEF:
                continue
            y = max(PY0, min(PY0 + PH - 1, y))
            if y < y0:
                fb.vline(c, y, y0 - y + 1, col)
            else:
                fb.vline(c, y0, y - y0 + 1, col)

    def draw_curves(self, fb):
        p = self.p
        for i in p.order():
            arr = p.cache.get(i)
            if arr is None:
                continue
            col = gfx.SERIES[i % 6]
            if p.kind(i) == "y":
                f = p.fns[i]
                prev = arr[0]
                for c in range(1, PW):
                    y = arr[c]
                    if y != UNDEF and prev != UNDEF:
                        d = y - prev
                        if (d > PH or d < -PH) and not p.continuous(f, c):
                            prev = y
                            continue
                        _tline(fb, c - 1, prev, c, y, col)
                    elif y != UNDEF and (c == PW - 1 or arr[c + 1] == UNDEF):
                        fb.pixel(c, y, col)
                    prev = y
            else:
                n = len(arr) // 2
                for k in range(1, n):
                    x0 = arr[2 * k - 2]
                    x1 = arr[2 * k]
                    if x0 == UNDEF or x1 == UNDEF:
                        continue
                    y0 = arr[2 * k - 1]
                    y1 = arr[2 * k + 1]
                    if abs(x1 - x0) > PW or abs(y1 - y0) > PH:
                        continue
                    _tline(fb, x0, y0, x1, y1, col)

    def draw_cursor(self, fb):
        p = self.p
        order = p.order()
        if self.mode == "view" or not order:
            return
        i = order[self.tr % len(order)]
        pt = self.cursor_point(i)
        if pt is None:
            return
        x, y = pt
        cx = p.ipx(x)
        cy = p.ipy(y)
        if cy < PY0:
            cy = PY0
        if cy > PY0 + PH - 1:
            cy = PY0 + PH - 1
        col = gfx.WHITE
        fb.hline(cx - 5, cy, 4, col)
        fb.hline(cx + 2, cy, 4, col)
        fb.vline(cx, cy - 5, 4, col)
        fb.vline(cx, cy + 2, 4, col)
        fb.rect(cx - 1, cy - 1, 3, 3, gfx.SERIES[i % 6])

    def cursor_point(self, i):
        p = self.p
        if p.kind(i) == "y":
            y = p.fns[i](self.tx)
            if y is None:
                return None
            return self.tx, y
        t0, st, n = p.t_values()
        return p.point(i, t0 + self.tk * st)

    def trace_text(self):
        p = self.p
        order = p.order()
        if not order:
            return None
        i = order[self.tr % len(order)]
        if p.kind(i) == "y":
            y = p.fns[i](self.tx)
            return "%s x=%s y=%s" % (funcs.label(i), _fmt(self.tx, 7), _fmt(y, 7))
        t0, st, n = p.t_values()
        t = t0 + self.tk * st
        pt = p.point(i, t)
        tn = "θ" if p.kind(i) == "r" else "t"
        if pt is None:
            return "%s %s=%s %s" % (funcs.label(i), tn, _fmt(t, 5), T("undef"))
        return "%s=%s x=%s y=%s" % (tn, _fmt(t, 5), _fmt(pt[0], 6), _fmt(pt[1], 6))

    def draw(self):
        if self.dirty:
            ui.busy("Plotting...")
            self.p.compute()
            self.dirty = False
        fb = gfx.fb()
        fb.fill_rect(0, PY0, PW, PH, gfx.BG)
        self.draw_grid(fb)
        self.draw_shade(fb)
        self.draw_curves(fb)
        self.draw_cursor(fb)
        # overlays
        ui.status_bar("Graph")
        order = self.p.order()
        f = gfx.font("small")
        if self.mode != "view" and order:
            i = order[self.tr % len(order)]
            s = f.clip(funcs.describe(i), PW - 4)
            fb.fill_rect(0, PY0, f.width(s) + 4, f.h + 2, gfx.BG)
            f.text(s, 2, PY0 + 1, gfx.SERIES[i % 6])
        info = self.info
        if info is None and self.mode == "trace":
            info = self.trace_text()
        if info:
            fn_ = gfx.font("normal")
            y = PY0 + PH - 12
            fb.fill_rect(0, y, PW, 12, gfx.PANEL)
            fb.hline(0, y, PW, gfx.PANEL2)
            fn_.text(fn_.clip(info, PW - 4), 2, y + 1, gfx.FG)
        ui.softkeys(["Trace", "Zoom", "View", "Analyze", "Y=", "Auto"], 0 if self.mode != "view" else None)
        gfx.show()

    # ---- trace ------------------------------------------------------------------
    def start_trace(self):
        order = self.p.order()
        if not order:
            return
        self.mode = "trace"
        v = self.p.v
        if not (v["xmin"] <= self.tx <= v["xmax"]):
            self.tx = self.p.x_of(PW // 2)
        else:
            self.tx = self.p.x_of(int(self.p.px(self.tx) + 0.5))

    def trace_move(self, d):
        p = self.p
        order = p.order()
        i = order[self.tr % len(order)]
        if p.kind(i) == "y":
            c = int(p.px(self.tx) + 0.5) + d
            if c < 0 or c > PW - 1:
                p.pan(-0.25 if c < 0 else 0.25, 0)
                self.dirty = True
                c = int(p.px(self.tx) + 0.5) + d
            self.tx = p.x_of(c)
        else:
            t0, st, n = p.t_values()
            self.tk = max(0, min(n - 1, self.tk + d))

    def goto_x(self, x):
        v = self.p.v
        self.tx = x
        if not (v["xmin"] <= x <= v["xmax"]):
            hx = (v["xmax"] - v["xmin"]) / 2
            v["xmin"], v["xmax"] = x - hx, x + hx
            self.dirty = True

    def trace_key(self, k):
        kk = k.nav()
        p = self.p
        order = p.order()
        big = 10 if (k.mods & SHIFT) else 1
        if kk == LEFT:
            self.trace_move(-big)
        elif kk == RIGHT:
            self.trace_move(big)
        elif kk == UP:
            self.tr = (self.tr - 1) % len(order)
            self._sync_t()
        elif kk == DOWN:
            self.tr = (self.tr + 1) % len(order)
            self._sync_t()
        elif kk == ENTER:
            pt = self.cursor_point(order[self.tr % len(order)])
            if pt:
                self.p.zoom(1.0, pt[0], pt[1])
                self.dirty = True
        elif kk == ESC:
            self.mode = "view"
        elif len(kk) == 1 and (kk.isdigit() or kk == "-"):
            i = order[self.tr % len(order)]
            if p.kind(i) == "y":
                x = self._ask_num("Go to x", kk)
                if x is not None:
                    self.goto_x(x)
            else:
                t = self._ask_num("Go to t", kk)
                if t is not None:
                    t0, st, n = p.t_values()
                    self.tk = max(0, min(n - 1, int(bcd.rnd((t - t0) / st)))) if st else 0
        else:
            return k
        return None

    def _sync_t(self):
        p = self.p
        order = p.order()
        i = order[self.tr % len(order)]
        if p.kind(i) != "y":
            t0, st, n = p.t_values()
            self.tk = min(self.tk, n - 1)

    def _ask_num(self, title, initial=""):
        ctx = state.ctx()
        txt = initial
        while True:
            s = ui.input_line(title, txt, typed=True)
            if s is None:
                return None
            try:
                v = funcs.real(ui.evaluate(s, ctx))
                if v is None:
                    raise CalcError("Non-real error")
                return v
            except Exception as e:
                ui.error(T(str(e)))
                txt = s

    # ---- Analysis -------------------------------------------------------------------
    def current_y(self):
        p = self.p
        order = p.order()
        if not order:
            return None
        i = order[self.tr % len(order)]
        if p.kind(i) != "y":
            ui.message("Analysis", "Only for y=f(x) functions")
            return None
        return i

    def column_values(self, g):
        p = self.p
        return [g(p.x_of(c)) for c in range(PW)]

    def roots_of(self, g):
        p = self.p
        vals = self.column_values(g)
        h = _raising(g)
        out = []
        for c in range(PW - 1):
            a = vals[c]
            b = vals[c + 1]
            if a is None or b is None:
                continue
            x0 = p.x_of(c)
            x1 = p.x_of(c + 1)
            if a == 0:
                out.append(x0)
            elif (a < 0) != (b < 0) and b != 0:
                try:
                    r = F.bracket_root(h, x0, x1)
                except Exception:
                    r = None
                if r is not None:
                    # reject sign changes across a pole / jump
                    gr = g(r)
                    if gr is not None and abs(gr) <= _E6 * max(1, abs(a), abs(b)):
                        out.append(r)
        # tangent roots (touching zero)
        for c in range(1, PW - 1):
            a, m, b = vals[c - 1], vals[c], vals[c + 1]
            if a is None or m is None or b is None or m == 0:
                continue
            if (a > 0) == (m > 0) == (b > 0) and abs(m) <= abs(a) and abs(m) <= abs(b):
                try:
                    x, fx = F.minimize(lambda t: abs(h(t)), p.x_of(c - 1), p.x_of(c + 1))
                except Exception:
                    continue
                span = p.v["ymax"] - p.v["ymin"]
                if abs(fx) < _E9 * max(1, span):
                    out.append(x)
        return _dedupe(out, p)

    def extrema_of(self, g, find_max):
        p = self.p
        vals = self.column_values(g)
        h = _raising(g)
        s = -1 if find_max else 1
        out = []
        for c in range(1, PW - 1):
            a, m, b = vals[c - 1], vals[c], vals[c + 1]
            if a is None or m is None or b is None:
                continue
            a, m, b = s * a, s * m, s * b
            if m <= a and m <= b and not (m == a == b):
                try:
                    x, fx = F.minimize(lambda t: s * h(t), p.x_of(c - 1), p.x_of(c + 1))
                except Exception:
                    continue
                out.append(x)
        return _dedupe(out, p)

    def gsolve(self):
        i = self.current_y()
        if i is None:
            return
        items = ["Root", "Min", "Max", "Intersect", "y at x", "x at y", "dy/dx", "∫dx"]
        sel = ui.menu(T("Analysis %s") % funcs.label(i), items)
        if sel is None:
            return
        p = self.p
        f = p.fns[i]
        self.shade = None
        name = T(items[sel])
        if sel in (0, 1, 2, 3, 5):
            ui.busy("Solving...")
            if sel == 0:
                xs = self.roots_of(f)
                g = f
            elif sel in (1, 2):
                xs = self.extrema_of(f, sel == 2)
                g = f
            elif sel == 3:
                j = self.pick_other(i)
                if j is None:
                    return
                fj = p.fns[j]

                def g(x):
                    a = f(x)
                    b = fj(x)
                    if a is None or b is None:
                        return None
                    return a - b

                xs = self.roots_of(g)
                name = T("Isect %s,%s") % (funcs.label(i), funcs.label(j))
            else:
                y = self._ask_num("x at y: y =")
                if y is None:
                    return

                def g(x):
                    a = f(x)
                    return None if a is None else a - y

                xs = self.roots_of(g)
            if not xs:
                self.info = T("%s: none in view") % name
                self.mode = "trace"
                return
            self.sols = [(x, name) for x in xs]
            # start with the solution nearest to the cursor
            tx = self.tx
            self.si = 0
            for k in range(len(xs)):
                if abs(xs[k] - tx) < abs(xs[self.si] - tx):
                    self.si = k
            self.mode = "solve"
            self._show_sol()
        elif sel == 4:
            x = self._ask_num("y at x: x =")
            if x is None:
                return
            self.goto_x(x)
            self.mode = "trace"
            self.info = "y=%s" % _fmt(f(x))
        elif sel == 6:
            if self.mode == "view":
                self.start_trace()
            x = self.tx
            try:
                d = F.deriv(_raising(f), x)
                self.info = "x=%s dy/dx=%s" % (_fmt(x, 6), _fmt(F.clean(d), 8))
            except Exception:
                self.info = T("dy/dx undefined at x=%s") % _fmt(x, 6)
            self.mode = "trace"
        elif sel == 7:
            a = self._ask_num("∫dx lower bound")
            if a is None:
                return
            b = self._ask_num("∫dx upper bound")
            if b is None:
                return
            ui.busy("Integrating...")
            try:
                val = F.integ(_raising(f), a, b)
                self.info = "∫%s..%s =%s" % (_fmt(a, 5), _fmt(b, 5), _fmt(F.clean(val)))
                self.shade = (i, a, b)
            except Exception:
                self.info = "∫: " + T("Math error")
            self.mode = "trace"
            self.tx = b

    def _show_sol(self):
        x, name = self.sols[self.si]
        p = self.p
        order = p.order()
        f = p.fns[order[self.tr % len(order)]]
        self.tx = x
        y = f(x)
        n = len(self.sols)
        tag = "%s %d/%d" % (name, self.si + 1, n) if n > 1 else name
        self.info = "%s x=%s y=%s" % (tag, _fmt(x, 8), _fmt(F.clean(y) if y is not None else None, 8))

    def pick_other(self, i):
        others = [j for j in self.p.order() if j != i and self.p.kind(j) == "y"]
        if not others:
            ui.message("Intersect", "Need two y=f(x) functions")
            return None
        if len(others) == 1:
            return others[0]
        sel = ui.menu("Intersect with", [funcs.describe(j) for j in others])
        return None if sel is None else others[sel]

    # ---- menus ----------------------------------------------------------------
    def zoom_menu(self):
        items = ["Zoom in", "Zoom out", "Standard", "Trig", "Integer", "Square", "Auto fit"]
        sel = ui.menu("Zoom", items)
        if sel is None:
            return False
        cx = cy = None
        if self.mode != "view":
            pt = self.cursor_point(self.p.order()[self.tr % len(self.p.order())])
            if pt:
                cx, cy = pt
        p = self.p
        if sel == 0:
            p.zoom(0.5, cx, cy)
        elif sel == 1:
            p.zoom(2.0, cx, cy)
        elif sel == 2:
            p.set_standard()
        elif sel == 3:
            p.set_trig()
        elif sel == 4:
            p.set_integer()
        elif sel == 5:
            p.set_square()
        elif sel == 6:
            ui.busy("Fitting...")
            p.auto_fit()
        self.dirty = True
        self.shade = None
        return True

    def run(self):
        """Returns when the user leaves the graph (to the Y= list)."""
        p = self.p
        p.compile_all()
        if p.errors:
            ui.message("Graph", p.errors[:4])
        if not p.order():
            ui.message("Graph", "No function selected.\nSelect one with F1 in Y=.")
            return
        while True:
            self.draw()
            k = hal.wait_key()
            if self.mode == "solve":
                kk = k.nav()
                if kk in (LEFT, RIGHT) and len(self.sols) > 1:
                    self.si = (self.si + (1 if kk == RIGHT else -1)) % len(self.sols)
                    self._show_sol()
                    continue
                self.mode = "trace"
                self.sols = []
                if kk == ESC:
                    self.info = None
                    continue
            if self.mode == "trace":
                self.info = None if ui.fkey(k) is None else self.info
                k = self.trace_key(k)
                if k is None:
                    continue
                self.info = None
            fk = ui.fkey(k)
            kk = k.nav()
            if fk == 0:
                if self.mode == "trace":
                    self.mode = "view"
                else:
                    self.start_trace()
            elif fk == 1:
                self.zoom_menu()
            elif fk == 2:
                edit_view()
                self.dirty = True
            elif fk == 3:
                self.gsolve()
            elif fk == 4 or kk == ESC:
                return
            elif fk == 5:
                ui.busy("Fitting...")
                p.auto_fit()
                self.dirty = True
            elif kk == LEFT:
                p.pan(-0.125, 0)
                self.dirty = True
            elif kk == RIGHT:
                p.pan(0.125, 0)
                self.dirty = True
            elif kk == UP:
                p.pan(0, 0.125)
                self.dirty = True
            elif kk == DOWN:
                p.pan(0, -0.125)
                self.dirty = True
            elif kk in ("+", "="):
                p.zoom(0.5)
                self.dirty = True
            elif kk in ("-", "_"):
                p.zoom(2.0)
                self.dirty = True


_E6 = D("1e-6")


def _dedupe(xs, p):
    xs.sort()
    tol = (p.v["xmax"] - p.v["xmin"]) * _E6
    out = []
    for x in xs:
        x = F.clean(x)
        if abs(x) < tol / 100:
            x = ZERO
        if not out or abs(x - out[-1]) > tol:
            out.append(x)
    return out


def _tline(fb, x0, y0, x1, y1, c):
    fb.line(x0, y0, x1, y1, c)
    dy = y1 - y0
    dx = x1 - x0
    if (dy if dy > 0 else -dy) <= (dx if dx > 0 else -dx):
        fb.line(x0, y0 + 1, x1, y1 + 1, c)
    else:
        fb.line(x0 + 1, y0, x1 + 1, y1, c)


# ---------------------------------------------------------------------------
# View window editor
# ---------------------------------------------------------------------------
_VIEW_KEYS = ("xmin", "xmax", "xscl", "ymin", "ymax", "yscl", "tmin", "tmax", "tstep")
_VIEW_NAMES = ("Xmin", "Xmax", "Xscale", "Ymin", "Ymax", "Yscale", "Tmin/θmin", "Tmax/θmax", "Tstep/θstep")


def edit_view():
    v = funcs.view()
    sel = 0
    while True:
        items = [(_VIEW_NAMES[i], _fmt(v[k], 8)) for i, k in enumerate(_VIEW_KEYS)]
        items.append(("Reset to default", ""))
        sel = ui.menu("View window", items, sel)
        if sel is None:
            break
        if sel == len(_VIEW_KEYS):
            v.update(funcs.default_view())
            continue
        key = _VIEW_KEYS[sel]
        val = ui.input_number(T("%s (now %s)") % (T(_VIEW_NAMES[sel]), _fmt(v[key], 8)), None)
        if val is None or not isinstance(val, D):
            continue
        old = v[key]
        v[key] = val
        if v["xmin"] >= v["xmax"] or v["ymin"] >= v["ymax"] or v["tmin"] >= v["tmax"] or \
                v["tstep"] <= 0 or v["xscl"] < 0 or v["yscl"] < 0:
            v[key] = old
            ui.error("Invalid range")
    funcs.save()


# ---------------------------------------------------------------------------
# Y= function list
# ---------------------------------------------------------------------------
ROWH = 18


class FuncList:
    def __init__(self, can_draw=True):
        self.sel = 0
        self.editing = None  # LineEdit while editing
        self.can_draw = can_draw

    def draw(self):
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("Graph: Y=" if self.can_draw else "Functions")
        fs = funcs.funcs()
        fnt = gfx.font("normal")
        for i in range(funcs.N):
            y = ui.TOP + 2 + i * ROWH
            f = fs[i]
            col = gfx.SERIES[i % 6]
            if i == self.sel:
                fb.fill_rect(0, y - 1, ui.W, ROWH, gfx.PANEL2 if self.editing else gfx.SEL)
            # enabled box
            fb.rect(3, y + 3, 9, 9, col)
            if f["enabled"]:
                fb.fill_rect(5, y + 5, 5, 5, col)
            lab = funcs.label(i) + "="
            if f["type"] == "param":
                lab = "X%d=" % (i + 1)
            x = fnt.text(lab, 15, y + 3, col)
            w = ui.W - x - 2
            if self.editing is not None and i == self.sel:
                self.editing.draw(x, y + 3, w, bg=gfx.PANEL2)
                continue
            if f["type"] == "param":
                s = "%s  Y%d=%s" % (f["expr"], i + 1, f["expr2"])
            else:
                s = f["expr"]
            fnt.text(fnt.clip(s, w), x, y + 3, gfx.FG if f["enabled"] else gfx.DIM)
        if self.editing is None:
            labels = ["On/Off", "Type", "View", "Zoom", "Table" if self.can_draw else "", "Draw" if self.can_draw else ""]
            ui.softkeys(labels)
        else:
            fb.fill_rect(0, ui.BOT, ui.W, ui.H - ui.BOT, gfx.BG)
            gfx.font("small").text(T("Enter:OK  `:cancel  opt/alt:math  fn+h:keys"), 2, ui.BOT + 2, gfx.DIM)
        gfx.show()

    def validate(self, i):
        try:
            funcs.compile(i)
            return True
        except Exception as e:
            ui.error("%s: %s" % (funcs.label(i), T(str(e))))
            return False

    def edit(self, initial_key=None):
        i = self.sel
        f = funcs.funcs()[i]
        if f["type"] == "param":
            # two dialogs: X(t) then Y(t).  A key that started the edit
            # replaces X(t) and stays in the field.
            if initial_key is not None:
                ed = ui.LineEdit("", math=True)
                ed.handle(initial_key)
                sx = ui.input_line("X%d(t) =" % (i + 1), ed.text, typed=True)
            else:
                sx = ui.input_line("X%d(t) =" % (i + 1), f["expr"])
            if sx is None:
                return
            sy = ui.input_line("Y%d(t) =" % (i + 1), f["expr2"])
            if sy is None:
                return
            old = (f["expr"], f["expr2"])
            f["expr"], f["expr2"] = sx, sy
            if (sx.strip() or sy.strip()) and not self.validate(i):
                f["expr"], f["expr2"] = old
                return
            f["enabled"] = True
            funcs.save()
            return
        ed = ui.LineEdit(f["expr"], math=True, font="normal")
        self.editing = ed
        if initial_key is not None:
            ed.set("")
            ed.handle(initial_key)
        try:
            while True:
                self.draw()
                k = hal.wait_key()
                if k.base == "h" and k.mods & FN:
                    ui.show_keymap_help()
                    continue
                r = ed.handle(k)
                if r == "esc":
                    return
                if r == "enter" or (r is not None and r.key in (UP, DOWN)):
                    old = f["expr"]
                    f["expr"] = ed.text.strip()
                    if f["expr"] and not self.validate(i):
                        f["expr"] = old
                        continue
                    if f["expr"] != old:
                        f["enabled"] = True
                    funcs.save()
                    if r != "enter":
                        self.sel = (self.sel + (1 if r.key == DOWN else -1)) % funcs.N
                    return
        finally:
            self.editing = None

    def run(self):
        """Returns 'draw' when the user asks to draw, None on Esc."""
        while True:
            self.draw()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            fs = funcs.funcs()
            f = fs[self.sel]
            if fk == 0 or kk == " ":
                f["enabled"] = not f["enabled"]
                funcs.save()
            elif fk == 1:
                t = funcs.TYPES
                f["type"] = t[(t.index(f["type"]) + 1) % len(t)]
                funcs.save()
            elif fk == 2:
                edit_view()
            elif fk == 3:
                g = GraphView()
                g.p.compile_all()
                if g.zoom_menu():
                    funcs.save()
                    if self.can_draw:
                        return "draw"
            elif fk == 4:
                if not self.can_draw:
                    return None
                _run_table()
            elif fk == 5 and self.can_draw:
                return "draw"
            elif kk == UP:
                self.sel = (self.sel - 1) % funcs.N
            elif kk == DOWN:
                self.sel = (self.sel + 1) % funcs.N
            elif kk == ENTER or kk == RIGHT:
                self.edit()
            elif kk in (BS, DEL):
                if funcs.is_set(self.sel) and ui.confirm(T("Clear %s?") % funcs.label(self.sel)):
                    f["expr"] = ""
                    f["expr2"] = ""
                    funcs.save()
            elif kk == ESC or kk == LEFT:
                return None
            elif k.base == "h" and k.mods & FN:
                ui.show_keymap_help()
            elif (k.mods & (OPT | ALT)) or (len(k.key) == 1 and not (k.mods & (CTRL | FN))):
                self.edit(k)


def _run_table():
    loaded = "cardgcalc.apps.table" in sys.modules
    try:
        import cardgcalc.apps.table as t

        t.run(from_graph=True)
    finally:
        if not loaded:
            sys.modules.pop("cardgcalc.apps.table", None)
        gc.collect()


def run():
    lst = FuncList()
    try:
        while True:
            r = lst.run()
            if r != "draw":
                break
            g = GraphView()
            g.run()
            del g
            funcs.save()
            gc.collect()
    finally:
        funcs.save()
