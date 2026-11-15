# 3D Graph.
#
# Up to three graphs Z1..Z3, each one of
#   Z=        z = f(x, y)
#   Param     X(s,t), Y(s,t), Z(s,t)
#   Line      point + direction vector, or two points
#   Plane     aX+bY+cZ=d, point + two vectors, or three points
#   Sphere    centre + radius, or X²+Y²+Z²+aX+bY+cZ+d=0
#   Cylinder  radius, Z range, centre (axis parallel to Z)
#   Cone      base radius, base Z, apex Z, centre
#   Rot X/Y   solid of revolution of y=f(x) about the X / Y axis
#
# Graph screen: arrows rotate, F1 Trace, F2 Zoom (in, out, view along X/Y/Z,
# original), F3 Windowdow, F4 Analysis (cross section, intersection,
# relation), F5 auto rotation, F6 back to the list.
#
# Coordinates, trace values and Analysis results are decimal (bcd.D); the
# meshes are kept as single-precision float arrays only for drawing.
import gc
import math
from array import array
import bcd
from bcd import D
from nc import hal, gfx, ui, storage, state
from nc.i18n import T
from nc.hal import rgb, UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL
from nc.calc import numfmt, dec
from nc.calc.dec import DC

N = 3
TYPES = ("z", "param", "line", "plane", "sphere", "cyl", "cone", "rotx", "roty")
TYPE_NAMES = ("Z=", "Param", "Line", "Plane", "Sphere", "Cylinder", "Cone", "Rot X", "Rot Y")
TEMPLATES = ("line", "plane", "sphere", "cyl", "cone")

_P3 = (("x0", "X0"), ("y0", "Y0"), ("z0", "Z0"))
FORMS = {
    "line": (
        ("pv", "Point & vector", _P3 + (("l", "Vector l"), ("m", "Vector m"), ("n", "Vector n"))),
        ("pts", "Two points", (("x1", "X1"), ("y1", "Y1"), ("z1", "Z1"), ("x2", "X2"), ("y2", "Y2"), ("z2", "Z2"))),
    ),
    "plane": (
        ("eq", "aX+bY+cZ=d", (("a", "a"), ("b", "b"), ("c", "c"), ("d", "d"))),
        ("vec", "Point & 2 vectors", _P3 + (("u1", "u1"), ("u2", "u2"), ("u3", "u3"),
                                           ("v1", "v1"), ("v2", "v2"), ("v3", "v3"))),
        ("pts", "Three points", (("x1", "X1"), ("y1", "Y1"), ("z1", "Z1"), ("x2", "X2"), ("y2", "Y2"),
                                 ("z2", "Z2"), ("x3", "X3"), ("y3", "Y3"), ("z3", "Z3"))),
    ),
    "sphere": (
        ("fac", "(X-a)²+(Y-b)²+(Z-c)²=r²", (("a", "a"), ("b", "b"), ("c", "c"), ("r", "r"))),
        ("exp", "X²+Y²+Z²+aX+bY+cZ+d=0", (("a", "a"), ("b", "b"), ("c", "c"), ("d", "d"))),
    ),
    "cyl": (("std", "Cylinder", (("r", "Radius"), ("h0", "Zmin"), ("h1", "Zmax"),
                                 ("a", "Center X"), ("b", "Center Y"))),),
    "cone": (("std", "Cone", (("r", "Radius"), ("h0", "Base Z"), ("h1", "Apex Z"),
                              ("a", "Center X"), ("b", "Center Y"))),),
}
DEFAULTS = {
    "line": {"x0": 0, "y0": 0, "z0": 0, "l": 1, "m": 1, "n": 1,
             "x1": -2, "y1": -2, "z1": -2, "x2": 2, "y2": 2, "z2": 2},
    "plane": {"a": 1, "b": 1, "c": 1, "d": 1, "x0": 0, "y0": 0, "z0": 0, "u1": 1, "u2": 0, "u3": 0,
              "v1": 0, "v2": 1, "v3": 0, "x1": 1, "y1": 0, "z1": 0, "x2": 0, "y2": 1, "z2": 0,
              "x3": 0, "y3": 0, "z3": 1},
    "sphere": {"a": 0, "b": 0, "c": 0, "r": 2, "d": -4},
    "cyl": {"r": 1, "h0": -2, "h1": 2, "a": 0, "b": 0},
    "cone": {"r": 2, "h0": -2, "h1": 2, "a": 0, "b": 0},
}

# colours: (name, rgb)
COLORS = (("Blue", (80, 160, 255)), ("Red", (255, 90, 90)), ("Green", (90, 210, 120)),
          ("Magenta", (230, 100, 220)), ("Cyan", (80, 220, 230)), ("Yellow", (255, 220, 60)),
          ("Orange", (255, 150, 40)), ("White", (230, 230, 235)))

VIEW_KEYS = ("xmin", "xmax", "xgrid", "ymin", "ymax", "ygrid", "zmin", "zmax",
             "smin", "smax", "sgrid", "tmin", "tmax", "tgrid", "theta", "phi")
VIEW_NAMES = ("Xmin", "Xmax", "Xgrid", "Ymin", "Ymax", "Ygrid", "Zmin", "Zmax",
              "Smin", "Smax", "Sgrid", "Tmin", "Tmax", "Tgrid", "Angle θ", "Angle φ")
THETA0 = 40
PHI0 = 65


def default_view():
    return {"xmin": D(-3), "xmax": D(3), "xgrid": D(20), "ymin": D(-3), "ymax": D(3), "ygrid": D(20),
            "zmin": D(-3), "zmax": D(3), "smin": D(0), "smax": bcd.pi, "sgrid": D(20),
            "tmin": D(0), "tmax": 2 * bcd.pi, "tgrid": D(24), "theta": D(THETA0), "phi": D(PHI0)}


def _new_graph(i):
    return {"type": "z", "on": True, "col": i, "expr": "", "ex": "", "ey": "", "ez": "", "form": "", "v": {}}


_data = None


def data():
    global _data
    if _data is None:
        d = storage.load_json("graph3d.json", None)
        base = {"graphs": [_new_graph(i) for i in range(N)], "view": default_view(),
                "setup": {"label": True, "axes": True, "box": True, "mesh": True}}
        if isinstance(d, dict):
            gs = d.get("graphs")
            if isinstance(gs, list):
                for i in range(min(N, len(gs))):
                    if isinstance(gs[i], dict):
                        base["graphs"][i].update(gs[i])
            for k in ("view", "setup"):
                if isinstance(d.get(k), dict):
                    base[k].update(d[k])
        v = base["view"]
        for k in VIEW_KEYS:
            v[k] = dec.num(v[k]) if isinstance(v[k], (int, float, D)) else default_view()[k]
        _data = base
    return _data


def save():
    if _data is not None:
        storage.save_json("graph3d.json", _data)


def _vals(g):
    """Template values of graph g (defaults filled in) as D."""
    out = {}
    dv = DEFAULTS.get(g["type"], {})
    for k, x in dv.items():
        out[k] = dec.num(g["v"].get(k, x))
    return out


def _fmt(v, sig=7):
    if v is None:
        return "?"
    if isinstance(v, D):
        s = numfmt.fmt_real(bcd.rsig(v, sig))
        return s
    return numfmt.fmt(v)


def describe(i):
    """One-line description of graph i for the list."""
    g = data()["graphs"][i]
    t = g["type"]
    if t == "z":
        return "Z=" + g["expr"]
    if t == "param":
        return "X=%s, Y=%s, Z=%s" % (g["ex"], g["ey"], g["ez"])
    if t in ("rotx", "roty"):
        return "%s: y=%s" % (T(TYPE_NAMES[TYPES.index(t)]), g["expr"])
    v = _vals(g)
    f = lambda k: _fmt(v[k], 5)
    form = g["form"] or FORMS[t][0][0]
    if t == "line":
        if form == "pts":
            return T("Line") + " (%s,%s,%s)-(%s,%s,%s)" % tuple(f(k) for k in ("x1", "y1", "z1", "x2", "y2", "z2"))
        return T("Line") + " (%s,%s,%s)+t(%s,%s,%s)" % tuple(f(k) for k in ("x0", "y0", "z0", "l", "m", "n"))
    if t == "plane":
        if form == "vec":
            return T("Plane") + " (%s,%s,%s)+s(%s,%s,%s)+t(%s,%s,%s)" % tuple(
                f(k) for k in ("x0", "y0", "z0", "u1", "u2", "u3", "v1", "v2", "v3"))
        if form == "pts":
            return T("Plane") + " (%s,%s,%s),(%s,%s,%s),(%s,%s,%s)" % tuple(
                f(k) for k in ("x1", "y1", "z1", "x2", "y2", "z2", "x3", "y3", "z3"))
        return T("Plane") + " %sX+%sY+%sZ=%s" % (f("a"), f("b"), f("c"), f("d"))
    if t == "sphere":
        if form == "exp":
            return T("Sphere") + " X²+Y²+Z²+%sX+%sY+%sZ+%s=0" % (f("a"), f("b"), f("c"), f("d"))
        return T("Sphere") + " C(%s,%s,%s) r=%s" % (f("a"), f("b"), f("c"), f("r"))
    name = T("Cylinder") if t == "cyl" else T("Cone")
    return name + " r=%s Z:%s~%s C(%s,%s)" % (f("r"), f("h0"), f("h1"), f("a"), f("b"))


# ---------------------------------------------------------------------------
# Decimal vector helpers (analysis)
# ---------------------------------------------------------------------------
def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _scale(*vs):
    s = D(0)
    for v in vs:
        for c in v:
            if abs(c) > s:
                s = abs(c)
    return s if s != 0 else D(1)


_TOL = D("1e-12")


def is0(x, scale=None):
    return abs(x) <= _TOL * (scale if scale is not None else D(1))


def v_is0(v, scale):
    return is0(v[0], scale) and is0(v[1], scale) and is0(v[2], scale)


class InvalidSetting(Exception):
    pass


def geometry(g):
    """Decimal geometry of a template graph:
    ('line', P, V) | ('plane', N, d) [N·X = d] | ('sphere', C, r) |
    ('cyl', r, h0, h1, a, b) | ('cone', r, h0, h1, a, b)."""
    t = g["type"]
    v = _vals(g)
    form = g["form"] or FORMS[t][0][0]
    if t == "line":
        if form == "pts":
            P = (v["x1"], v["y1"], v["z1"])
            Q = (v["x2"], v["y2"], v["z2"])
            V = v_sub(Q, P)
        else:
            P = (v["x0"], v["y0"], v["z0"])
            V = (v["l"], v["m"], v["n"])
        if V == (0, 0, 0):
            raise InvalidSetting
        return ("line", P, V)
    if t == "plane":
        if form == "vec":
            P = (v["x0"], v["y0"], v["z0"])
            Nv = cross((v["u1"], v["u2"], v["u3"]), (v["v1"], v["v2"], v["v3"]))
        elif form == "pts":
            P = (v["x1"], v["y1"], v["z1"])
            Nv = cross(v_sub((v["x2"], v["y2"], v["z2"]), P), v_sub((v["x3"], v["y3"], v["z3"]), P))
        else:
            Nv = (v["a"], v["b"], v["c"])
            if Nv == (0, 0, 0):
                raise InvalidSetting
            return ("plane", Nv, v["d"])
        if Nv == (0, 0, 0):
            raise InvalidSetting
        return ("plane", Nv, dot(Nv, P))
    if t == "sphere":
        if form == "exp":
            C = (-v["a"] / 2, -v["b"] / 2, -v["c"] / 2)
            r2 = dot(C, C) - v["d"]
            if r2 <= 0:
                raise InvalidSetting
            return ("sphere", C, bcd.sqrt(r2))
        if v["r"] <= 0:
            raise InvalidSetting
        return ("sphere", (v["a"], v["b"], v["c"]), v["r"])
    if v["r"] <= 0 or v["h0"] == v["h1"]:
        raise InvalidSetting
    return (t, v["r"], v["h0"], v["h1"], v["a"], v["b"])


# ---------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------
NAN = float("nan")
RING = 24  # segments around spheres, cylinders, cones and solids of revolution


class Box:
    """World <-> normalised cube [-1, 1]^3 (float, drawing only)."""

    def __init__(self, v):
        self.lo = (v["xmin"], v["ymin"], v["zmin"])
        self.hi = (v["xmax"], v["ymax"], v["zmax"])
        f = dec.f
        self.m = [(f(self.lo[k]) + f(self.hi[k])) / 2 for k in range(3)]
        self.h = [(f(self.hi[k]) - f(self.lo[k])) / 2 for k in range(3)]

    def n(self, x, y, z):
        return ((x - self.m[0]) / self.h[0], (y - self.m[1]) / self.h[1], (z - self.m[2]) / self.h[2])

    def inside(self, p, eps=1e-6):
        return -1 - eps <= p[0] <= 1 + eps and -1 - eps <= p[1] <= 1 + eps and -1 - eps <= p[2] <= 1 + eps


class Mesh:
    """A surface (nu x nv quads) or a polyline (nv = 0), normalised coords."""

    def __init__(self, gi, nu, nv):
        self.gi = gi
        self.nu = nu
        self.nv = nv
        cols = nv + 1
        self.cols = cols
        self.pts = array("f", [NAN] * (3 * (nu + 1) * cols))
        self.node_d = None  # (i, j) -> (X, Y, Z) decimal, or None
        self.geo = None  # template geometry (decimal)

    def set(self, i, j, p):
        k = 3 * (i * self.cols + j)
        a = self.pts
        for q in range(3):
            v = p[q]
            a[k + q] = 1e6 if v > 1e6 else (-1e6 if v < -1e6 else v)

    def valid(self, n):
        return self.pts[3 * n] == self.pts[3 * n]

    def finish(self):
        """Outcodes (which faces of the box a node is outside of) and normals."""
        n = (self.nu + 1) * self.cols
        cd = array("B", [0] * n)
        a = self.pts
        e = 1.000001
        for k in range(n):
            x = a[3 * k]
            if x != x:
                cd[k] = 128
                continue
            y = a[3 * k + 1]
            z = a[3 * k + 2]
            c = 0
            if x < -e:
                c |= 1
            elif x > e:
                c |= 2
            if y < -e:
                c |= 4
            elif y > e:
                c |= 8
            if z < -e:
                c |= 16
            elif z > e:
                c |= 32
            cd[k] = c
        self.code = cd
        self.normals()

    def normals(self):
        """Per-quad unit normals (for shading)."""
        if self.nv == 0:
            return
        nq = self.nu * self.nv
        nr = array("f", [0.0] * (3 * nq))
        a = self.pts
        cols = self.cols
        for i in range(self.nu):
            for j in range(self.nv):
                n0 = 3 * (i * cols + j)
                n1 = n0 + 3 * cols
                n2 = n1 + 3
                n3 = n0 + 3
                if a[n0] != a[n0] or a[n1] != a[n1] or a[n2] != a[n2] or a[n3] != a[n3]:
                    continue
                ax = a[n2] - a[n0]
                ay = a[n2 + 1] - a[n0 + 1]
                az = a[n2 + 2] - a[n0 + 2]
                bx = a[n3] - a[n1]
                by = a[n3 + 1] - a[n1 + 1]
                bz = a[n3 + 2] - a[n1 + 2]
                nx = ay * bz - az * by
                ny = az * bx - ax * bz
                nz = ax * by - ay * bx
                ln = math.sqrt(nx * nx + ny * ny + nz * nz)
                q = 3 * (i * self.nv + j)
                if ln > 0:
                    nr[q] = nx / ln
                    nr[q + 1] = ny / ln
                    nr[q + 2] = nz / ln
        self.nrm = nr


def _real(v):
    if isinstance(v, D):
        return v
    if isinstance(v, int) and not isinstance(v, bool):
        return D(v)
    if isinstance(v, DC):
        if v.imag == 0:
            return v.real
    return None


def _call(f, *a):
    try:
        return _real(f(*a))
    except Exception:
        return None


def _grid(lo, hi, n):
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


def _gridn(x):
    return max(2, min(50, int(x)))


def build(gi, box, view, ctx):
    """Mesh of graph gi (raises InvalidSetting / CalcError for bad input)."""
    g = data()["graphs"][gi]
    t = g["type"]
    f = dec.f
    lo, hi = box.lo, box.hi

    def put(m, i, j, X, Y, Z):
        if X is None or Y is None or Z is None:
            return
        m.set(i, j, box.n(f(X), f(Y), f(Z)))

    if t == "z":
        fn = ctx.function2(g["expr"], "x", "y")
        nu = _gridn(view["xgrid"])
        nv = _gridn(view["ygrid"])
        xs = _grid(lo[0], hi[0], nu)
        ys = _grid(lo[1], hi[1], nv)
        m = Mesh(gi, nu, nv)
        for i in range(nu + 1):
            for j in range(nv + 1):
                put(m, i, j, xs[i], ys[j], _call(fn, xs[i], ys[j]))
            gc.collect() if i % 8 == 7 else None

        def node(i, j):
            return xs[i], ys[j], _call(fn, xs[i], ys[j])

        m.node_d = node
        m.fn = fn
    elif t == "param":
        fx = ctx.function2(g["ex"], "s", "t")
        fy = ctx.function2(g["ey"], "s", "t")
        fz = ctx.function2(g["ez"], "s", "t")
        nu = _gridn(view["sgrid"])
        nv = _gridn(view["tgrid"])
        ss = _grid(view["smin"], view["smax"], nu)
        ts = _grid(view["tmin"], view["tmax"], nv)
        m = Mesh(gi, nu, nv)

        def node(i, j):
            s, tt = ss[i], ts[j]
            return _call(fx, s, tt), _call(fy, s, tt), _call(fz, s, tt)

        for i in range(nu + 1):
            for j in range(nv + 1):
                put(m, i, j, *node(i, j))
        m.node_d = node
        m.st = (ss, ts)
        m.fns = (fx, fy, fz)
    elif t in ("rotx", "roty"):
        fn = ctx.function(g["expr"], "x")
        nu = _gridn(view["xgrid"])
        xs = _grid(lo[0], hi[0], nu)
        m = Mesh(gi, nu, RING)
        ang = [2 * bcd.pi * j / RING for j in range(RING + 1)]
        ca = [bcd.cos(a) for a in ang]
        sa = [bcd.sin(a) for a in ang]

        def node(i, j):
            x = xs[i]
            y = _call(fn, x)
            if y is None:
                return None, None, None
            if t == "rotx":
                return x, y * ca[j], y * sa[j]
            return x * ca[j], y, x * sa[j]

        for i in range(nu + 1):
            for j in range(RING + 1):
                put(m, i, j, *node(i, j))
        m.node_d = node
    else:
        geo = geometry(g)
        m = _template_mesh(gi, geo, box)
        m.geo = geo
    m.finish()
    return m


def _template_mesh(gi, geo, box):
    f = dec.f
    k = geo[0]
    if k == "line":
        P, V = geo[1], geo[2]
        # clip P + tV to the box (slab method, float)
        p = [f(c) for c in P]
        v = [f(c) for c in V]
        t0, t1 = -1e30, 1e30
        for a in range(3):
            lo = f(box.lo[a])
            hi = f(box.hi[a])
            if v[a] == 0:
                if not (lo <= p[a] <= hi):
                    t0, t1 = 1, 0
                continue
            ta = (lo - p[a]) / v[a]
            tb = (hi - p[a]) / v[a]
            if ta > tb:
                ta, tb = tb, ta
            t0 = max(t0, ta)
            t1 = min(t1, tb)
        n = 20
        m = Mesh(gi, n, 0)
        if t0 <= t1:
            ts = [D(t0 + (t1 - t0) * i / n) for i in range(n + 1)]

            def node(i, j=0):
                return v_add(P, v_mul(V, ts[i]))

            for i in range(n + 1):
                X, Y, Z = node(i)
                m.set(i, 0, box.n(f(X), f(Y), f(Z)))
            m.node_d = node
        return m
    if k == "plane":
        Nv, d = geo[1], geo[2]
        a = max(range(3), key=lambda q: abs(Nv[q]))
        u, w = [q for q in range(3) if q != a]
        n = 16
        us = _grid(box.lo[u], box.hi[u], n)
        ws = _grid(box.lo[w], box.hi[w], n)
        m = Mesh(gi, n, n)

        def node(i, j):
            p = [None, None, None]
            p[u] = us[i]
            p[w] = ws[j]
            p[a] = (d - Nv[u] * us[i] - Nv[w] * ws[j]) / Nv[a]
            return tuple(p)

        for i in range(n + 1):
            for j in range(n + 1):
                X, Y, Z = node(i, j)
                m.set(i, j, box.n(f(X), f(Y), f(Z)))
        m.node_d = node
        return m
    if k == "sphere":
        C, r = geo[1], geo[2]
        nu = 16
        th = [bcd.pi * i / nu for i in range(nu + 1)]
        ph = [2 * bcd.pi * j / RING for j in range(RING + 1)]
        st = [bcd.sin(x) for x in th]
        ct = [bcd.cos(x) for x in th]
        sp = [bcd.sin(x) for x in ph]
        cp = [bcd.cos(x) for x in ph]
        m = Mesh(gi, nu, RING)

        def node(i, j):
            return (C[0] + r * st[i] * cp[j], C[1] + r * st[i] * sp[j], C[2] + r * ct[i])

        for i in range(nu + 1):
            for j in range(RING + 1):
                X, Y, Z = node(i, j)
                m.set(i, j, box.n(f(X), f(Y), f(Z)))
        m.node_d = node
        return m
    # cylinder / cone: rows from the bottom centre up to the top
    r, h0, h1, a, b = geo[1], geo[2], geo[3], geo[4], geo[5]
    cone = k == "cone"
    rows = [(D(0), h0)]
    nr = 6
    for i in range(nr + 1):
        h = h0 + (h1 - h0) * i / nr
        rows.append((r * (nr - i) / nr if cone else r, h))
    if not cone:
        rows.append((D(0), h1))
    ph = [2 * bcd.pi * j / RING for j in range(RING + 1)]
    sp = [bcd.sin(x) for x in ph]
    cp = [bcd.cos(x) for x in ph]
    m = Mesh(gi, len(rows) - 1, RING)

    def node(i, j):
        rr, h = rows[i]
        return (a + rr * cp[j], b + rr * sp[j], h)

    for i in range(len(rows)):
        for j in range(RING + 1):
            X, Y, Z = node(i, j)
            m.set(i, j, box.n(f(X), f(Y), f(Z)))
    m.node_d = node
    return m


# ---------------------------------------------------------------------------
# Projection and drawing
# ---------------------------------------------------------------------------
GX0 = 0
GY0 = ui.TOP
GW = ui.W
GH = ui.BOT - ui.TOP
CX = GW // 2
CY = GY0 + GH // 2


def _shade(rgb3, k):
    return rgb(int(rgb3[0] * k), int(rgb3[1] * k), int(rgb3[2] * k))


class Camera:
    def __init__(self, theta, phi, zoom=1.0):
        self.set(theta, phi, zoom)

    def set(self, theta, phi, zoom):
        self.theta = theta
        self.phi = phi
        self.zoom = zoom
        th = math.radians(theta)
        ph = math.radians(phi)
        st, ct, sp, cp = math.sin(th), math.cos(th), math.sin(ph), math.cos(ph)
        self.d = (sp * ct, sp * st, cp)  # towards the viewer
        self.r = (-st, ct, 0.0)  # screen right
        self.u = (-cp * ct, -cp * st, sp)  # screen up
        self.s = GH / 2 / 1.78 * zoom
        # light from the viewer, a little from above and left
        lx = self.d[0] + 0.5 * self.u[0] - 0.3 * self.r[0]
        ly = self.d[1] + 0.5 * self.u[1] - 0.3 * self.r[1]
        lz = self.d[2] + 0.5 * self.u[2] - 0.3 * self.r[2]
        ln = math.sqrt(lx * lx + ly * ly + lz * lz)
        self.light = (lx / ln, ly / ln, lz / ln)

    def p(self, x, y, z):
        """(screen x, screen y, depth)"""
        r, u, d, s = self.r, self.u, self.d, self.s
        return (CX + int(s * (r[0] * x + r[1] * y)),
                CY - int(s * (u[0] * x + u[1] * y + u[2] * z)),
                d[0] * x + d[1] * y + d[2] * z)


def project(mesh, cam):
    n = (mesh.nu + 1) * mesh.cols
    sx = array("h", [0] * n)
    sy = array("h", [0] * n)
    dp = array("f", [0.0] * n)
    a = mesh.pts
    cd = mesh.code
    r0, r1 = cam.r[0], cam.r[1]
    u0, u1, u2 = cam.u
    d0, d1, d2 = cam.d
    s = cam.s
    for k in range(n):
        c = cd[k]
        if c & 128:
            continue
        x = a[3 * k]
        y = a[3 * k + 1]
        z = a[3 * k + 2]
        if c:
            x = -1.5 if x < -1.5 else (1.5 if x > 1.5 else x)
            y = -1.5 if y < -1.5 else (1.5 if y > 1.5 else y)
            z = -1.5 if z < -1.5 else (1.5 if z > 1.5 else z)
        else:
            sx[k] = CX + int(s * (r0 * x + r1 * y))
            sy[k] = CY - int(s * (u0 * x + u1 * y + u2 * z))
        dp[k] = d0 * x + d1 * y + d2 * z
    mesh.sx = sx
    mesh.sy = sy
    mesh.dp = dp


def _clip(poly):
    """Clip a 3D polygon (normalised coords) to the cube [-1, 1]^3."""
    for ax in range(3):
        for sg in (-1.0, 1.0):
            n = len(poly)
            if n == 0:
                return poly
            out = []
            for k in range(n):
                a = poly[k]
                b = poly[(k + 1) % n]
                da = sg * a[ax] - 1
                db = sg * b[ax] - 1
                if da <= 0:
                    out.append(a)
                if (da <= 0) != (db <= 0):
                    t = da / (da - db)
                    out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))
            poly = out
    return poly


_CORNERS = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
_EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8)
          if sum(1 for k in range(3) if _CORNERS[a][k] != _CORNERS[b][k]) == 1]


class Scene:
    """Meshes + camera; draws the graph area."""

    def __init__(self):
        self.meshes = []
        self.box = None
        self.cam = None
        self.overlay = None  # callable(fb) drawn on top

    def build(self, quiet=False):
        d = data()
        v = d["view"]
        self.box = Box(v)
        ctx = state.ctx()
        self.meshes = []
        gc.collect()
        errs = []
        for i in range(N):
            g = d["graphs"][i]
            if not g["on"] or not is_set(i):
                continue
            try:
                self.meshes.append(build(i, self.box, v, ctx))
            except InvalidSetting:
                errs.append("Z%d: %s" % (i + 1, T("Invalid setting")))
            except Exception as e:
                errs.append("Z%d: %s" % (i + 1, T(str(e) or "Error")))
            gc.collect()
        if errs and not quiet:
            ui.message("3D Graph", errs)

    def set_cam(self, theta, phi, zoom):
        if self.cam is None:
            self.cam = Camera(theta, phi, zoom)
        else:
            self.cam.set(theta, phi, zoom)

    def mesh_of(self, gi):
        for m in self.meshes:
            if m.gi == gi:
                return m
        return None

    def draw(self, fb, quick=False):
        cam = self.cam
        setup = data()["setup"]
        fb.fill_rect(GX0, GY0, GW, GH, gfx.BG)
        cpts = [cam.p(*c) for c in _CORNERS]
        near = max(range(8), key=lambda q: cpts[q][2])
        front = [e for e in _EDGES if near in e]
        if setup["box"]:
            for e in _EDGES:
                if e not in front:
                    a, b = cpts[e[0]], cpts[e[1]]
                    fb.line(a[0], a[1], b[0], b[1], gfx.GRID)
        org = self.box.n(0.0, 0.0, 0.0)
        oin = self.box.inside(org, 0)
        if setup["axes"] and oin:
            for k in range(3):
                p0 = list(org)
                p1 = list(org)
                p0[k] = -1.0
                p1[k] = 1.0
                a = cam.p(*p0)
                b = cam.p(*p1)
                fb.line(a[0], a[1], b[0], b[1], gfx.AXIS)
        # faces and line segments, far to near
        keys = []
        for oi, m in enumerate(self.meshes):
            project(m, cam)
            dp = m.dp
            cols = m.cols
            cd = m.code
            if m.nv == 0:
                for i in range(m.nu):
                    if cd[i] == 0 and cd[i + 1] == 0:
                        dq = int((dp[i] + dp[i + 1]) * 500) + 2000
                        keys.append((dq << 17) | (1 << 15) | (oi << 13) | i)
                continue
            for i in range(m.nu):
                b0 = i * cols
                for j in range(m.nv):
                    n0 = b0 + j
                    n1 = n0 + cols
                    c0, c1, c2, c3 = cd[n0], cd[n1], cd[n1 + 1], cd[n0 + 1]
                    if (c0 | c1 | c2 | c3) & 128 or (c0 & c1 & c2 & c3):
                        continue
                    dq = int((dp[n0] + dp[n1] + dp[n1 + 1] + dp[n0 + 1]) * 250) + 2000
                    part = 2 if (c0 | c1 | c2 | c3) else 0
                    keys.append((dq << 17) | (part << 15) | (oi << 13) | (i * m.nv + j))
        keys.sort()
        graphs = data()["graphs"]
        pal = []
        line = []
        for m in self.meshes:
            base = COLORS[graphs[m.gi]["col"] % len(COLORS)][1]
            pal.append([_shade(base, 0.28 + 0.72 * q / 7) for q in range(8)])
            line.append([_shade(base, (0.28 + 0.72 * q / 7) * 0.62) for q in range(8)])
        L = cam.light
        mesh_on = setup["mesh"] and not quick
        buf = array("h", [0] * 8)
        for key in keys:
            oi = (key >> 13) & 3
            m = self.meshes[oi]
            idx = key & 0x1FFF
            sx, sy = m.sx, m.sy
            kind = (key >> 15) & 3
            if kind == 1:
                c = pal[oi][7]
                fb.line(sx[idx], sy[idx], sx[idx + 1], sy[idx + 1], c)
                fb.line(sx[idx], sy[idx] + 1, sx[idx + 1], sy[idx + 1] + 1, c)
                continue
            i = idx // m.nv
            j = idx - i * m.nv
            n0 = i * m.cols + j
            n1 = n0 + m.cols
            nr = m.nrm
            q = 3 * idx
            sh = nr[q] * L[0] + nr[q + 1] * L[1] + nr[q + 2] * L[2]
            if sh < 0:
                sh = -sh
            lv = int(sh * 7.99)
            if kind == 2:
                pts = m.pts
                poly = _clip([(pts[3 * n], pts[3 * n + 1], pts[3 * n + 2]) for n in (n0, n1, n1 + 1, n0 + 1)])
                if len(poly) < 3:
                    continue
                pb = array("h", [0] * (2 * len(poly)))
                for q, p in enumerate(poly):
                    x, y, _ = cam.p(*p)
                    pb[2 * q] = x
                    pb[2 * q + 1] = y
                fb.poly(0, 0, pb, pal[oi][lv], True)
                if mesh_on:
                    fb.poly(0, 0, pb, line[oi][lv], False)
                continue
            buf[0] = sx[n0]
            buf[1] = sy[n0]
            buf[2] = sx[n1]
            buf[3] = sy[n1]
            buf[4] = sx[n1 + 1]
            buf[5] = sy[n1 + 1]
            buf[6] = sx[n0 + 1]
            buf[7] = sy[n0 + 1]
            fb.poly(0, 0, buf, pal[oi][lv], True)
            if mesh_on:
                fb.poly(0, 0, buf, line[oi][lv], False)
        if setup["box"]:
            for e in front:
                a, b = cpts[e[0]], cpts[e[1]]
                fb.line(a[0], a[1], b[0], b[1], gfx.DIM)
        if setup["label"]:
            fs = gfx.font("small")
            base = org if oin else (-1.0, -1.0, -1.0)
            for k, name in enumerate("XYZ"):
                p = list(base)
                p[k] = 1.18
                x, y, _ = cam.p(*p)
                fs.text(name, x - 2, y - 4, gfx.FG)
        if self.overlay:
            self.overlay(fb)


def is_set(i):
    g = data()["graphs"][i]
    t = g["type"]
    if t in ("z", "rotx", "roty"):
        return bool(g["expr"].strip())
    if t == "param":
        return bool(g["ex"].strip() and g["ey"].strip() and g["ez"].strip())
    return True


# ---------------------------------------------------------------------------
# Graph screen
# ---------------------------------------------------------------------------
class GraphScreen:
    def __init__(self):
        self.sc = Scene()
        v = data()["view"]
        self.zoom = 1.0
        self.theta = dec.f(v["theta"])
        self.phi = dec.f(v["phi"])
        self.info = None

    def cam(self):
        self.sc.set_cam(self.theta, self.phi, self.zoom)

    def paint(self, keys=None, quick=False):
        fb = gfx.fb()
        self.cam()
        self.sc.draw(fb, quick)
        ui.status_bar("3D Graph", "θ%d φ%d" % (round(self.theta), round(self.phi)))
        fb.fill_rect(0, ui.BOT, ui.W, ui.H - ui.BOT, gfx.BG)
        if self.info is not None:
            fs = gfx.font("small")
            fb.fill_rect(0, ui.BOT, ui.W, ui.H - ui.BOT, gfx.PANEL)
            fs.text(fs.clip(self.info, ui.W - 4), 2, ui.BOT + 2, gfx.YELLOW)
        else:
            ui.softkeys(keys or ["Trace", "Zoom", "Window", "Analyze", "Rotate", "List"])
        gfx.show()

    def save_angles(self):
        v = data()["view"]
        v["theta"] = D(round(self.theta))
        v["phi"] = D(round(self.phi))

    def rotate_key(self, kk):
        if kk == LEFT:
            self.theta -= 15
        elif kk == RIGHT:
            self.theta += 15
        elif kk == UP:
            self.phi -= 15
        elif kk == DOWN:
            self.phi += 15
        else:
            return False
        self.theta = (self.theta + 180) % 360 - 180
        self.phi = self.phi % 360
        return True

    def view_axis(self, k):
        self.theta, self.phi = ((0, 90), (90, 90), (-90, 0))[k]

    def original(self):
        self.theta, self.phi, self.zoom = float(THETA0), float(PHI0), 1.0

    def zoom_menu(self):
        k = ui.menu("Zoom", ["Zoom in", "Zoom out", "View along X", "View along Y", "View along Z",
                             "Original view"])
        if k == 0:
            self.zoom *= 1.5
        elif k == 1:
            self.zoom /= 1.5
        elif k in (2, 3, 4):
            self.view_axis(k - 2)
        elif k == 5:
            self.original()

    def auto_rotate(self):
        k = ui.menu("Rotate", ["Left → right", "Right → left", "Top → bottom", "Bottom → top"])
        if k is None:
            return
        step = 15
        for _ in range(2 * 360 // step):
            if k == 0:
                self.theta += step
            elif k == 1:
                self.theta -= step
            elif k == 2:
                self.phi += step
            else:
                self.phi -= step
            self.theta = (self.theta + 180) % 360 - 180
            self.phi %= 360
            self.paint(quick=True)
            if hal.keyboard.poll() is not None:
                break
        self.paint()

    # ---- trace ---------------------------------------------------------
    def trace(self):
        ms = [m for m in self.sc.meshes if m.node_d is not None]
        if not ms:
            ui.error("No graph")
            return
        mi = 0
        m = ms[0]
        i, j = m.nu // 2, (m.nv // 2 if m.nv else 0)
        custom = None
        while True:
            m = ms[mi]
            if custom is not None:
                X, Y, Z = custom
            else:
                X, Y, Z = m.node_d(i, j)
            gi = m.gi
            self.info = "Z%d  X=%s Y=%s Z=%s" % (gi + 1, _fmt(X), _fmt(Y), _fmt(Z))
            pt = None
            if X is not None and Y is not None and Z is not None:
                p = self.sc.box.n(dec.f(X), dec.f(Y), dec.f(Z))
                pt = self.sc.cam.p(*p) if self.sc.cam else None

            def ov(fb, pt=pt):
                if pt is None:
                    return
                x, y = pt[0], pt[1]
                fb.hline(x - 5, y, 11, gfx.YELLOW)
                fb.vline(x, y - 5, 11, gfx.YELLOW)
                fb.rect(x - 2, y - 2, 5, 5, gfx.WHITE)

            self.sc.overlay = ov
            self.paint()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            if kk == ESC or fk == 0:
                break
            if fk == 1:
                mi = (mi + 1) % len(ms)
                m = ms[mi]
                i, j, custom = m.nu // 2, (m.nv // 2 if m.nv else 0), None
                continue
            if fk == 2:
                mi = (mi - 1) % len(ms)
                m = ms[mi]
                i, j, custom = m.nu // 2, (m.nv // 2 if m.nv else 0), None
                continue
            if kk in (LEFT, RIGHT):
                custom = None
                i = max(0, min(m.nu, i + (1 if kk == RIGHT else -1)))
            elif kk in (UP, DOWN) and m.nv:
                custom = None
                j = max(0, min(m.nv, j + (1 if kk == UP else -1)))
            elif kk == ENTER or k.key in ("=", "x", "s"):
                custom = self._trace_input(m) or custom
        self.sc.overlay = None
        self.info = None

    def _trace_input(self, m):
        g = data()["graphs"][m.gi]
        ctx = state.ctx()
        if g["type"] == "z":
            x = ui.input_number("X =", None, ctx)
            if not isinstance(x, D):
                return None
            y = ui.input_number("Y =", None, ctx)
            if not isinstance(y, D):
                return None
            return x, y, _call(m.fn, x, y)
        if g["type"] == "param":
            s = ui.input_number("S =", None, ctx)
            if not isinstance(s, D):
                return None
            t = ui.input_number("T =", None, ctx)
            if not isinstance(t, D):
                return None
            fx, fy, fz = m.fns
            return _call(fx, s, t), _call(fy, s, t), _call(fz, s, t)
        return None

    # ---- Analysis -----------------------------------------------------------
    def gsolve(self):
        k = ui.menu("Analysis", ["Cross section", "Intersection", "Relation"])
        if k == 0:
            self.cross()
        elif k == 1:
            self.relations(True)
        elif k == 2:
            self.relations(False)

    def cross(self):
        a = ui.choose("Cross section", ["X = c", "Y = c", "Z = c"])
        if a is None:
            return
        v = data()["view"]
        lo = v[("xmin", "ymin", "zmin")[a]]
        hi = v[("xmax", "ymax", "zmax")[a]]
        c = D(0) if lo <= 0 <= hi else (lo + hi) / 2
        step = bcd.rsig((hi - lo) / 20, 2)
        name = "XYZ"[a]
        while True:
            cn = (dec.f(c) - self.sc.box.m[a]) / self.sc.box.h[a]
            segs, dots = self._section(a, cn)
            cam = self.sc.cam

            def ov(fb, segs=segs, dots=dots, cn=cn):
                self.cam()
                cam = self.sc.cam
                # outline of the cutting plane
                sq = ((-1, -1), (1, -1), (1, 1), (-1, 1))
                ps = []
                for u, w in sq:
                    p = [u, w]
                    p.insert(a, cn)
                    ps.append(cam.p(*p))
                for q in range(4):
                    p0, p1 = ps[q], ps[(q + 1) % 4]
                    fb.line(p0[0], p0[1], p1[0], p1[1], gfx.YELLOW)
                for s in segs:
                    p0 = cam.p(*s[0])
                    p1 = cam.p(*s[1])
                    fb.line(p0[0], p0[1], p1[0], p1[1], gfx.WHITE)
                    fb.line(p0[0] + 1, p0[1], p1[0] + 1, p1[1], gfx.WHITE)
                for d in dots:
                    p = cam.p(*d)
                    fb.fill_rect(p[0] - 2, p[1] - 2, 5, 5, gfx.WHITE)

            self.sc.overlay = ov
            self.info = None
            self.paint(["Up", "Down", "View X", "View Y", "View Z", "Orig"])
            fs = gfx.font("small")
            lab = "%s=%s" % (name, _fmt(c, 8))
            fb = gfx.fb()
            fb.fill_rect(2, GY0 + 2, fs.width(lab) + 4, 10, gfx.PANEL)
            fs.text(lab, 4, GY0 + 3, gfx.YELLOW)
            gfx.show()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            if kk == ESC:
                break
            if fk == 0:
                c = min(hi, c + step)
            elif fk == 1:
                c = max(lo, c - step)
            elif fk in (2, 3, 4):
                self.view_axis(fk - 2)
            elif fk == 5:
                self.original()
            elif kk == ENTER or (len(k.key) == 1 and (k.key.isdigit() or k.key in "-.")):
                x = ui.input_number("%s =" % name, c, state.ctx())
                if isinstance(x, D):
                    if lo <= x <= hi:
                        c = x
                    else:
                        ui.error("Out of range")
            elif self.rotate_key(kk):
                pass
        self.sc.overlay = None

    def _section(self, a, cn):
        """Segments where the meshes cross the plane coord[a] = cn (normalised)."""
        segs = []
        dots = []
        for m in self.sc.meshes:
            p = m.pts
            if m.nv == 0:
                for i in range(m.nu):
                    k0 = 3 * i
                    k1 = k0 + 3
                    if p[k0] != p[k0] or p[k1] != p[k1]:
                        continue
                    w0 = p[k0 + a] - cn
                    w1 = p[k1 + a] - cn
                    if w0 == 0 or w0 * w1 < 0:
                        t = w0 / (w0 - w1) if w0 != w1 else 0
                        dots.append(tuple(p[k0 + q] + (p[k1 + q] - p[k0 + q]) * t for q in range(3)))
                        break
                continue
            cols = m.cols
            for i in range(m.nu):
                for j in range(m.nv):
                    n0 = i * cols + j
                    quad = (n0, n0 + cols, n0 + cols + 1, n0 + 1)
                    ok = True
                    for n in quad:
                        if p[3 * n] != p[3 * n]:
                            ok = False
                            break
                    if not ok:
                        continue
                    for tri in ((quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])):
                        cut = []
                        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                            k0 = 3 * e[0]
                            k1 = 3 * e[1]
                            w0 = p[k0 + a] - cn
                            w1 = p[k1 + a] - cn
                            if (w0 < 0) != (w1 < 0):
                                t = w0 / (w0 - w1)
                                cut.append(tuple(p[k0 + q] + (p[k1 + q] - p[k0 + q]) * t for q in range(3)))
                        if len(cut) == 2 and self.sc.box.inside(cut[0], 0.01) and self.sc.box.inside(cut[1], 0.01):
                            segs.append(cut)
        return segs, dots

    def relations(self, intersect):
        objs = [m for m in self.sc.meshes if m.geo is not None and m.geo[0] in
                (("line", "plane", "sphere") if intersect else ("line", "plane"))]
        pairs = [(a, b) for ai, a in enumerate(objs) for b in objs[ai + 1:]]
        if not pairs:
            ui.error("Need two lines/planes" if not intersect else "Need two lines/planes/spheres")
            return
        pi = 0
        while True:
            a, b = pairs[pi]
            if intersect:
                lines, marks = intersection(a.geo, b.geo)
            else:
                lines, marks = [relation(a.geo, b.geo)], None
            head = "Z%d, Z%d" % (a.gi + 1, b.gi + 1)
            box = self.sc.box

            def ov(fb, marks=marks):
                if not marks:
                    return
                cam = self.sc.cam
                for mk in marks:
                    if mk[0] == "pt":
                        p = box.n(*[dec.f(c) for c in mk[1]])
                        if box.inside(p, 0.05):
                            x, y, _ = cam.p(*p)
                            fb.ellipse(x, y, 4, 4, gfx.WHITE, True)
                            fb.ellipse(x, y, 4, 4, gfx.BLACK, False)
                    elif mk[0] == "poly":
                        prev = None
                        for q in mk[1]:
                            p = box.n(*q)
                            cur = cam.p(*p) if box.inside(p, 0.02) else None
                            if prev and cur:
                                fb.line(prev[0], prev[1], cur[0], cur[1], gfx.WHITE)
                                fb.line(prev[0], prev[1] + 1, cur[0], cur[1] + 1, gfx.WHITE)
                            prev = cur

            self.sc.overlay = ov
            self.info = None
            self.paint(["Next", "Back", "", "", "", ""] if len(pairs) > 1 else [""] * 6)
            # result panel
            fs = gfx.font("small")
            fb = gfx.fb()
            rows = [head] + [T(x) for x in lines]
            h = 9 * len(rows) + 3
            y0 = ui.BOT - h
            fb.fill_rect(0, y0, ui.W, h, gfx.PANEL)
            fb.hline(0, y0, ui.W, gfx.DIM)
            for r, s in enumerate(rows):
                fs.text(fs.clip(s, ui.W - 4), 2, y0 + 2 + 9 * r, gfx.YELLOW if r == 0 else gfx.FG)
            gfx.show()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            if kk == ESC or kk == ENTER:
                break
            if fk == 0:
                pi = (pi + 1) % len(pairs)
            elif fk == 1:
                pi = (pi - 1) % len(pairs)
            elif self.rotate_key(kk):
                pass
        self.sc.overlay = None

    def run(self):
        self.sc.build()
        while True:
            self.paint()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            if fk == 0:
                self.trace()
            elif fk == 1:
                self.zoom_menu()
            elif fk == 2:
                if edit_view():
                    self.theta = dec.f(data()["view"]["theta"])
                    self.phi = dec.f(data()["view"]["phi"])
                    ui.busy("Drawing...")
                    self.sc.build()
            elif fk == 3:
                self.gsolve()
            elif fk == 4:
                self.auto_rotate()
            elif fk == 5 or kk == ESC:
                break
            elif k.key in ("+",) or (k.key == "=" and k.mods & hal.SHIFT):
                self.zoom *= 1.5
            elif k.key == "-":
                self.zoom /= 1.5
            elif self.rotate_key(kk):
                pass
        self.save_angles()
        save()


# ---------------------------------------------------------------------------
# Analysis (decimal)
# ---------------------------------------------------------------------------
def _pt(p):
    return "(%s, %s, %s)" % (_fmt(p[0], 10), _fmt(p[1], 10), _fmt(p[2], 10))


def _clean(v):
    return tuple(dec.num(x) if not isinstance(x, D) else _snap(x) for x in v)


def _snap(x):
    r = bcd.rnd(x)
    if r != x and abs(x - r) < D("1e-12") * max(D(1), abs(x)):
        return r
    if abs(x) < D("1e-13"):
        return D(0)
    return x


def _line_poly(P, V, box):
    """Float sample points of a line clipped to the box (for drawing)."""
    out = []
    span = max(dec.f(box.hi[k]) - dec.f(box.lo[k]) for k in range(3))
    vf = [dec.f(c) for c in V]
    ln = math.sqrt(sum(c * c for c in vf)) or 1
    pf = [dec.f(c) for c in P]
    for i in range(41):
        t = (i - 20) / 20 * span * 1.8 / ln
        out.append(tuple(pf[k] + vf[k] * t for k in range(3)))
    return out


def intersection(ga, gb):
    """Text lines and marks for the intersection of two templates."""
    ka, kb = ga[0], gb[0]
    if ka > kb:  # order: line < plane < sphere
        ga, gb = gb, ga
        ka, kb = kb, ka
    v = data()["view"]
    box = Box(v)
    if ka == "line" and kb == "line":
        P1, V1 = ga[1], ga[2]
        P2, V2 = gb[1], gb[2]
        w = v_sub(P2, P1)
        c = cross(V1, V2)
        sc = _scale(P1, V1, P2, V2)
        if v_is0(c, sc * sc):
            if v_is0(cross(w, V1), sc * sc):
                return ["Infinite (same line)"], [("poly", _line_poly(P1, V1, box))]
            return ["Not found"], []
        if not is0(dot(w, c), sc * sc * sc):
            return ["Not found"], []
        t = dot(cross(w, V2), c) / dot(c, c)
        X = _clean(v_add(P1, v_mul(V1, t)))
        return ["Point: " + _pt(X)], [("pt", X)]
    if ka == "line" and kb == "plane":
        P, V = ga[1], ga[2]
        Nv, d = gb[1], gb[2]
        den = dot(Nv, V)
        sc = _scale(P, V, Nv) + abs(d)
        if is0(den, sc * sc):
            if is0(dot(Nv, P) - d, sc * sc):
                return ["Infinite (on the plane)"], [("poly", _line_poly(P, V, box))]
            return ["Not found"], []
        t = (d - dot(Nv, P)) / den
        X = _clean(v_add(P, v_mul(V, t)))
        return ["Point: " + _pt(X)], [("pt", X)]
    if ka == "plane" and kb == "plane":
        N1, d1 = ga[1], ga[2]
        N2, d2 = gb[1], gb[2]
        dr = cross(N1, N2)
        sc = _scale(N1, N2)
        if v_is0(dr, sc * sc):
            # parallel: same plane if d's are in the same ratio
            k = 0 if not is0(N1[0], sc) else (1 if not is0(N1[1], sc) else 2)
            if is0(d1 * N2[k] - d2 * N1[k], (sc + abs(d1) + abs(d2)) * sc):
                return ["Infinite (same plane)"], []
            return ["Not found"], []
        n11, n22, n12 = dot(N1, N1), dot(N2, N2), dot(N1, N2)
        den = n11 * n22 - n12 * n12
        c1 = (d1 * n22 - d2 * n12) / den
        c2 = (d2 * n11 - d1 * n12) / den
        P = _clean(v_add(v_mul(N1, c1), v_mul(N2, c2)))
        dr = _clean(dr)
        return ["Line: " + _pt(P) + "+t" + _pt(dr)], [("poly", _line_poly(P, dr, box))]
    if ka == "line" and kb == "sphere":
        P, V = ga[1], ga[2]
        C, r = gb[1], gb[2]
        w = v_sub(P, C)
        a2 = dot(V, V)
        b2 = 2 * dot(V, w)
        c2 = dot(w, w) - r * r
        disc = b2 * b2 - 4 * a2 * c2
        sc = (b2 * b2 + abs(4 * a2 * c2)) or D(1)
        if disc < 0 and not is0(disc, sc):
            return ["Not found"], []
        if is0(disc, sc):
            X = _clean(v_add(P, v_mul(V, -b2 / (2 * a2))))
            return ["Point: " + _pt(X)], [("pt", X)]
        sq = bcd.sqrt(disc)
        X1 = _clean(v_add(P, v_mul(V, (-b2 - sq) / (2 * a2))))
        X2 = _clean(v_add(P, v_mul(V, (-b2 + sq) / (2 * a2))))
        return ["Point: " + _pt(X1), "Point: " + _pt(X2)], [("pt", X1), ("pt", X2)]
    if ka == "plane" and kb == "sphere":
        Nv, d = ga[1], ga[2]
        C, r = gb[1], gb[2]
        nn = bcd.sqrt(dot(Nv, Nv))
        dist = (dot(Nv, C) - d) / nn
        if abs(dist) > r:
            return ["Not found"], []
        cen = _clean(v_sub(C, v_mul(Nv, dist / nn)))
        rad = bcd.sqrt(r * r - dist * dist)
        if rad == 0:
            return ["Point: " + _pt(cen)], [("pt", cen)]
        # circle samples (float)
        nf = [dec.f(c) / dec.f(nn) for c in Nv]
        u = (1.0, 0.0, 0.0) if abs(nf[0]) < 0.9 else (0.0, 1.0, 0.0)
        e1 = [u[1] * nf[2] - u[2] * nf[1], u[2] * nf[0] - u[0] * nf[2], u[0] * nf[1] - u[1] * nf[0]]
        l1 = math.sqrt(sum(c * c for c in e1))
        e1 = [c / l1 for c in e1]
        e2 = [nf[1] * e1[2] - nf[2] * e1[1], nf[2] * e1[0] - nf[0] * e1[2], nf[0] * e1[1] - nf[1] * e1[0]]
        cf = [dec.f(c) for c in cen]
        rf = dec.f(rad)
        pts = []
        for i in range(37):
            a = 2 * math.pi * i / 36
            pts.append(tuple(cf[k] + rf * (math.cos(a) * e1[k] + math.sin(a) * e2[k]) for k in range(3)))
        return ["Circle: C" + _pt(cen), "r=" + _fmt(rad, 10)], [("poly", pts), ("pt", cen)]
    if ka == "sphere" and kb == "sphere":
        return ["Not supported"], []
    return ["Not found"], []


def relation(ga, gb):
    ka, kb = ga[0], gb[0]
    if ka > kb:
        ga, gb = gb, ga
        ka, kb = kb, ka
    if ka == "line" and kb == "line":
        P1, V1 = ga[1], ga[2]
        P2, V2 = gb[1], gb[2]
        sc = _scale(P1, V1, P2, V2)
        c = cross(V1, V2)
        w = v_sub(P2, P1)
        if v_is0(c, sc * sc):
            return "Same line" if v_is0(cross(w, V1), sc * sc) else "Parallel"
        perp = is0(dot(V1, V2), sc * sc)
        if is0(dot(w, c), sc * sc * sc):
            return "Perpendicular, intersecting" if perp else "Intersecting"
        return "Skew, perpendicular" if perp else "Skew"
    if ka == "line" and kb == "plane":
        P, V = ga[1], ga[2]
        Nv, d = gb[1], gb[2]
        sc = _scale(P, V, Nv) + abs(d)
        if is0(dot(Nv, V), sc * sc):
            return "On the plane" if is0(dot(Nv, P) - d, sc * sc) else "Parallel"
        if v_is0(cross(Nv, V), sc * sc):
            return "Perpendicular"
        return "Intersecting"
    if ka == "plane" and kb == "plane":
        N1, d1 = ga[1], ga[2]
        N2, d2 = gb[1], gb[2]
        sc = _scale(N1, N2)
        if v_is0(cross(N1, N2), sc * sc):
            k = 0 if not is0(N1[0], sc) else (1 if not is0(N1[1], sc) else 2)
            same = is0(d1 * N2[k] - d2 * N1[k], (sc + abs(d1) + abs(d2)) * sc)
            return "Same plane" if same else "Parallel"
        return "Perpendicular" if is0(dot(N1, N2), sc * sc) else "Intersecting"
    return "Not supported"


# ---------------------------------------------------------------------------
# Windowdow and setup
# ---------------------------------------------------------------------------
def edit_view():
    """Returns True when something changed."""
    d = data()
    v = d["view"]
    s = d["setup"]
    sel = 0
    changed = False
    flags = ("label", "axes", "box", "mesh")
    flag_names = ("Label", "Axes", "Box", "Mesh")
    while True:
        items = [(VIEW_NAMES[i], _fmt(v[k], 8)) for i, k in enumerate(VIEW_KEYS)]
        for i, k in enumerate(flags):
            items.append((flag_names[i], T("on" if s[k] else "off")))
        items.append(("Reset to default", ""))
        sel = ui.menu("3D View Window", items, sel)
        if sel is None:
            break
        if sel == len(items) - 1:
            v.update(default_view())
            changed = True
            continue
        if sel >= len(VIEW_KEYS):
            k = flags[sel - len(VIEW_KEYS)]
            s[k] = not s[k]
            changed = True
            continue
        key = VIEW_KEYS[sel]
        val = ui.input_number(T("%s (now %s)") % (T(VIEW_NAMES[sel]), _fmt(v[key], 8)), None, state.ctx())
        if not isinstance(val, D):
            continue
        old = v[key]
        v[key] = val
        bad = v["xmin"] >= v["xmax"] or v["ymin"] >= v["ymax"] or v["zmin"] >= v["zmax"] or \
            v["smin"] >= v["smax"] or v["tmin"] >= v["tmax"]
        for g in ("xgrid", "ygrid", "sgrid", "tgrid"):
            if not (2 <= v[g] <= 50) or not bcd.isint(v[g]):
                bad = True
        if not (-180 <= v["theta"] <= 180) or not (0 <= v["phi"] <= 360):
            bad = True
        if bad:
            v[key] = old
            ui.error("Invalid range")
        else:
            changed = True
    save()
    return changed


# ---------------------------------------------------------------------------
# Function list
# ---------------------------------------------------------------------------
ROWH = 22


def edit_template(g):
    t = g["type"]
    forms = FORMS[t]
    if len(forms) > 1:
        cur = [f[0] for f in forms].index(g["form"]) if g["form"] in [f[0] for f in forms] else 0
        k = ui.choose(TYPE_NAMES[TYPES.index(t)], [f[1] for f in forms], forms[cur][1])
        if k is None:
            return False
    else:
        k = 0
    form = forms[k]
    vals = _vals(g)
    sel = 0
    while True:
        items = [(lab, _fmt(vals[key], 10)) for key, lab in form[2]]
        items.append(("Set", ""))
        sel = ui.menu(form[1], items, sel)
        if sel is None:
            return False
        if sel == len(form[2]):
            old = (g["form"], g["v"])
            g["form"] = form[0]
            g["v"] = dict(vals)
            try:
                geometry(g)
            except InvalidSetting:
                g["form"], g["v"] = old
                ui.error("Invalid setting")
                continue
            return True
        key, lab = form[2][sel]
        x = ui.input_number("%s =" % T(lab), vals[key], state.ctx())
        if isinstance(x, D):
            vals[key] = x
            sel = min(sel + 1, len(form[2]))


def _check(src, vars_):
    ctx = state.ctx()
    if len(vars_) == 2:
        ctx.function2(src, vars_[0], vars_[1])
    else:
        ctx.function(src, vars_[0])


def edit_graph(i):
    g = data()["graphs"][i]
    t = g["type"]
    try:
        if t == "z":
            s = ui.input_line("Z%d = f(x,y)" % (i + 1), g["expr"])
            if s is None:
                return
            if s.strip():
                _check(s, ("x", "y"))
            g["expr"] = s.strip()
        elif t == "param":
            out = []
            for name, key in (("X", "ex"), ("Y", "ey"), ("Z", "ez")):
                s = ui.input_line("%s%d(s,t) =" % (name, i + 1), g[key])
                if s is None:
                    return
                if s.strip():
                    _check(s, ("s", "t"))
                out.append(s.strip())
            g["ex"], g["ey"], g["ez"] = out
        elif t in ("rotx", "roty"):
            s = ui.input_line("%s: y = f(x)" % T(TYPE_NAMES[TYPES.index(t)]), g["expr"])
            if s is None:
                return
            if s.strip():
                _check(s, ("x",))
            g["expr"] = s.strip()
        else:
            if not edit_template(g):
                return
        g["on"] = True
        save()
    except Exception as e:
        ui.error(str(e))


class FuncList:
    def __init__(self):
        self.sel = 0

    def draw(self):
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("3D Graph")
        fnt = gfx.font("normal")
        fs = gfx.font("small")
        gs = data()["graphs"]
        for i in range(N):
            y = ui.TOP + 3 + i * ROWH
            g = gs[i]
            col = _shade(COLORS[g["col"] % len(COLORS)][1], 1.0)
            if i == self.sel:
                fb.fill_rect(0, y - 2, ui.W, ROWH, gfx.SEL)
            fb.rect(3, y + 3, 9, 9, col)
            if g["on"] and is_set(i):
                fb.fill_rect(5, y + 5, 5, 5, col)
            x = fnt.text("Z%d" % (i + 1), 15, y + 3, col)
            if is_set(i):
                s = describe(i)
                if g["type"] == "param":
                    s = T("Param") + ": " + s
            else:
                s = T(TYPE_NAMES[TYPES.index(g["type"])]) + "  —"
            fnt.text(fnt.clip(s, ui.W - x - 6), x + 5, y + 3, gfx.FG if g["on"] else gfx.DIM)
        v = data()["view"]
        info = "X:%s~%s  Y:%s~%s  Z:%s~%s" % tuple(_fmt(v[k], 4) for k in
                                                  ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"))
        fs.text(fs.clip(info, ui.W - 4), 2, ui.BOT - 10, gfx.DIM)
        ui.softkeys(["Select", "Type", "Color", "Window", "Delete", "Draw"])
        gfx.show()

    def run(self):
        while True:
            self.draw()
            k = hal.wait_key()
            fk = ui.fkey(k)
            kk = k.nav()
            gs = data()["graphs"]
            g = gs[self.sel]
            if fk == 0 or kk == " ":
                g["on"] = not g["on"]
                save()
            elif fk == 1:
                names = [T(n) for n in TYPE_NAMES]
                c = ui.choose("Type", names, T(TYPE_NAMES[TYPES.index(g["type"])]))
                if c is not None and TYPES[c] != g["type"]:
                    g["type"] = TYPES[c]
                    g["form"] = ""
                    save()
                    edit_graph(self.sel)
            elif fk == 2:
                names = [T(c[0]) for c in COLORS]
                c = ui.choose("Color", names, names[g["col"] % len(COLORS)])
                if c is not None:
                    g["col"] = c
                    save()
            elif fk == 3:
                edit_view()
            elif fk == 4 or kk in (BS, DEL):
                if ui.confirm(T("Clear %s?") % ("Z%d" % (self.sel + 1))):
                    gs[self.sel] = _new_graph(self.sel)
                    gs[self.sel]["col"] = g["col"]
                    save()
            elif fk == 5:
                if not any(gs[i]["on"] and is_set(i) for i in range(N)):
                    ui.error("No graph")
                    continue
                ui.busy("Drawing...")
                gc.collect()
                GraphScreen().run()
                gc.collect()
            elif kk == UP:
                self.sel = (self.sel - 1) % N
            elif kk == DOWN:
                self.sel = (self.sel + 1) % N
            elif kk == ENTER or kk == RIGHT:
                edit_graph(self.sel)
            elif kk == ESC or kk == LEFT:
                return


def run():
    try:
        FuncList().run()
    finally:
        save()
        global _data
        _data = None
