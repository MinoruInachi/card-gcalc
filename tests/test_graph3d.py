# Host tests for the 3D Graph app: template geometry, intersections and
# relations (decimal), and mesh building.
import sys

sys.path.insert(0, "src")
from bcd import D
from cardgcalc.apps import graph3d as g3

fails = 0


def chk(name, got, want):
    global fails
    if got != want:
        fails += 1
        print("FAIL", name, "->", got, "want", want)


def tpl(t, form="", **v):
    return {"type": t, "on": True, "col": 0, "expr": "", "ex": "", "ey": "", "ez": "", "form": form,
            "v": {k: D(x) for k, x in v.items()}}


def geo(t, form="", **v):
    return g3.geometry(tpl(t, form, **v))


L1 = geo("line", "pv", x0=0, y0=0, z0=0, l=1, m=1, n=1)
L2 = geo("line", "pts", x1=1, y1=0, z1=0, x2=0, y2=1, z2=0)  # in z=0
L3 = geo("line", "pv", x0=0, y0=0, z0=1, l=1, m=-1, n=0)  # skew to L2? parallel to L2
L4 = geo("line", "pv", x0="0.1", y0="0.2", z0="0.3", l=2, m=2, n=2)
P1 = geo("plane", "eq", a=0, b=0, c=1, d="0.5")
P2 = geo("plane", "pts", x1=0, y1=0, z1=0, x2=1, y2=0, z2=0, x3=0, y3=0, z3=1)  # y = 0
P3 = geo("plane", "vec", x0=0, y0=0, z0=2, u1=1, u2=0, u3=0, v1=0, v2=1, v3=0)  # z = 2
S1 = geo("sphere", "fac", a=0, b=0, c=0, r=2)
S2 = geo("sphere", "exp", a=-2, b=0, c=0, d=-3)  # (x-1)^2 + y^2 + z^2 = 4

chk("plane pts", P2, ("plane", (D(0), D(-1), D(0)), D(0)))
chk("sphere exp", S2, ("sphere", (D(1), D(0), D(0)), D(2)))
chk("line-plane", g3.intersection(L1, P1)[0], ["Point: (0.5, 0.5, 0.5)"])
chk("line-line", g3.intersection(L1, geo("line", "pts", x1=1, y1=1, z1=0, x2=1, y2=1, z2="2.5"))[0],
    ["Point: (1, 1, 1)"])
chk("line-line skew", g3.intersection(L1, L3)[0], ["Not found"])
chk("same line", g3.intersection(L1, geo("line", "pv", x0=1, y0=1, z0=1, l=-2, m=-2, n=-2))[0],
    ["Infinite (same line)"])
chk("parallel line", g3.intersection(L2, L3)[0], ["Not found"])
chk("plane-plane", g3.intersection(P1, P2)[0], ["Line: (0, 0, 0.5)+t(1, 0, 0)"])
chk("parallel planes", g3.intersection(P1, P3)[0], ["Not found"])
chk("same plane", g3.intersection(P1, geo("plane", "eq", a=0, b=0, c=2, d=1))[0], ["Infinite (same plane)"])
chk("line on plane", g3.intersection(L2, geo("plane", "eq", a=0, b=0, c=1, d=0))[0], ["Infinite (on the plane)"])
chk("plane-sphere", g3.intersection(P1, S1)[0], ["Circle: C(0, 0, 0.5)", "r=1.936491673"])
chk("plane-sphere tangent", g3.intersection(geo("plane", "eq", a=0, b=0, c=1, d=2), S1)[0], ["Point: (0, 0, 2)"])
chk("plane-sphere none", g3.intersection(P3, geo("sphere", "fac", a=0, b=0, c=0, r=1))[0], ["Not found"])
chk("line-sphere", g3.intersection(geo("line", "pv", x0=0, y0=0, z0=0, l=1, m=0, n=0), S1)[0],
    ["Point: (-2, 0, 0)", "Point: (2, 0, 0)"])
chk("line-sphere decimal", g3.intersection(L4, S1)[0],
    ["Point: (-1.25181017, -1.15181017, -1.05181017)", "Point: (1.05181017, 1.15181017, 1.25181017)"])

chk("rel intersect", g3.relation(L1, P1), "Intersecting")
chk("rel perp", g3.relation(geo("line", "pv", x0=0, y0=0, z0=0, l=0, m=0, n=1), P1), "Perpendicular")
chk("rel parallel lp", g3.relation(L3, P1), "Parallel")
chk("rel on plane", g3.relation(L2, geo("plane", "eq", a=0, b=0, c=1, d=0)), "On the plane")
chk("rel skew perp", g3.relation(L1, L3), "Skew, perpendicular")
chk("rel skew", g3.relation(L4, geo("line", "pv", x0=0, y0=0, z0=5, l=1, m=0, n=0)), "Skew")
chk("rel perp lines", g3.relation(L2, geo("line", "pv", x0=1, y0=0, z0=0, l=1, m=1, n=0)),
    "Perpendicular, intersecting")
chk("rel parallel planes", g3.relation(P1, P3), "Parallel")
chk("rel perp planes", g3.relation(P1, P2), "Perpendicular")
chk("rel parallel lines", g3.relation(L1, L4), "Parallel")
chk("rel same line", g3.relation(L1, geo("line", "pv", x0=2, y0=2, z0=2, l="0.5", m="0.5", n="0.5")), "Same line")

for bad in (tpl("line", "pts", x1=1, y1=1, z1=1, x2=1, y2=1, z2=1), tpl("plane", "eq", a=0, b=0, c=0, d=1),
            tpl("plane", "pts", x1=0, y1=0, z1=0, x2=1, y2=1, z2=1, x3=2, y3=2, z3=2),
            tpl("sphere", "fac", a=0, b=0, c=0, r=0), tpl("sphere", "exp", a=0, b=0, c=0, d=1),
            tpl("cyl", r=1, h0=1, h1=1), tpl("cone", r=-1, h0=0, h1=1)):
    try:
        g3.geometry(bad)
        fails += 1
        print("FAIL invalid accepted", bad["type"], bad["form"])
    except g3.InvalidSetting:
        pass

# meshes
g3._data = {"graphs": [], "view": g3.default_view(), "setup": {}}
g3._data["graphs"] = [
    {"type": "z", "on": True, "col": 0, "expr": "x²-y²", "ex": "", "ey": "", "ez": "", "form": "", "v": {}},
    tpl("sphere", "fac", a=0, b=0, c=0, r=2),
    tpl("line", "pv", x0=0, y0=0, z0=0, l=1, m=1, n=1),
]
from cardgcalc import state

box = g3.Box(g3._data["view"])
ctx = state.ctx()
m = g3.build(0, box, g3._data["view"], ctx)
chk("z mesh size", (m.nu, m.nv), (20, 20))
chk("z node", m.node_d(13, 11), (D("0.9"), D("0.3"), D("0.72")))
m = g3.build(1, box, g3._data["view"], ctx)
chk("sphere node", m.node_d(8, 12), (D(-2), D(0), D(0)))
m = g3.build(2, box, g3._data["view"], ctx)
chk("line nodes", (m.nu, m.nv, m.node_d(10)), (20, 0, (D(0), D(0), D(0))))
chk("clip", len(g3._clip([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)])), 4)
chk("clip out", g3._clip([(2, 2, 2), (3, 2, 2), (3, 3, 2)]), [])

print("FAILS:", fails)
