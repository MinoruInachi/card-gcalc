# Graph / Table with decimal numbers (run with the unix MicroPython build).
import sys
sys.path.insert(0, "src")
from bcd import D
from cardgcalc import settings, funcs, state
from cardgcalc.calc.dec import DC

settings.get("angle")
settings._s["angle"] = "rad"
settings._s["complex"] = False
funcs._data = funcs._defaults()  # do not depend on saved files

from cardgcalc.apps import graph as G
from cardgcalc.apps import table as TB

fails = 0


def chk(name, got, want):
    global fails
    if got != want:
        fails += 1
        print("FAIL", name, repr(got), "want", repr(want))


def setf(i, expr, kind="y", expr2=""):
    f = funcs.funcs()[i]
    f.update({"expr": expr, "expr2": expr2, "type": kind, "enabled": True})


for i in range(funcs.N):
    funcs.funcs()[i]["enabled"] = False

# ---- funcs.real / safe --------------------------------------------------------
chk("real D", funcs.real(D("0.1")), D("0.1"))
chk("real int", funcs.real(3), D(3))
chk("real DC tiny", funcs.real(DC(D(2), D("1e-20"))), D(2))
chk("real DC", funcs.real(DC(D(2), D(1))), None)
chk("real float inf", funcs.real(float("inf")), None)
setf(0, "√(x)")
g = funcs.safe(funcs.compile(0))
chk("safe sqrt", g(D(4)), D(2))
chk("safe sqrt neg", g(D(-1)), None)
setf(0, "1÷x")
chk("safe 1/0", funcs.safe(funcs.compile(0))(D(0)), None)

# ---- helpers -------------------------------------------------------------------
chk("nice 20/5", G._nice(D(20), 5), D(5))
chk("nice 7/5", G._nice(D(7), 5), D(2))
chk("nice 0.03/4", G._nice(D("0.03"), 4), D("0.01"))
chk("lab 2", G._lab(D(2), D(20)), "2")
chk("lab 0.5", G._lab(D("0.5"), D(20)), "0.5")
chk("lab 1e-10 zero", G._lab(D("1e-10"), D(20)), "0")
chk("lab 20000", G._lab(D(20000), D(1e5)), "2E4")
chk("lab -0.00002", G._lab(D("-0.00002"), D("0.001")), "-2E-5")
chk("lab 1234.5", G._lab(D("1234.5"), D(1e4)), "1235")
chk("fmt 7", G._fmt(D(1) / 3, 7), "0.3333333")
chk("fmt big", G._fmt(D("123456789"), 7), "123456789")
chk("fmt None", G._fmt(None), "undef")

# ---- mapping -------------------------------------------------------------------
p = G.Plot()
v = p.v
v.update({"xmin": D(0), "xmax": D("23.9"), "ymin": D(-5), "ymax": D(5)})
chk("x_of 1", p.x_of(1), D("0.1"))
chk("x_of 3", p.x_of(3), D("0.3"))
chk("x_of 239", p.x_of(239), D("23.9"))
chk("px", p.px(D("0.3")), 3.0)
chk("ipy 0", p.ipy(D(0)), G.PY0 + (G.PH - 1) // 2 + ((G.PH - 1) % 2))
v["xmin"] = D(-10)
v["xmax"] = D(10)
chk("remap", p.x_of(239), D(10))
p.zoom(D("0.5"))
chk("zoom", (v["xmin"], v["xmax"]), (D(-5), D(5)))
p.pan(D("0.1"), 0)
chk("pan", (v["xmin"], v["xmax"]), (D(-4), D(6)))
p.set_integer()
chk("integer", (v["xmin"], v["xmax"], v["ymin"], v["ymax"]), (D(-119), D(120), D(-55), D(56)))
p.set_trig()
chk("trig", v["xmax"], 2 * D("3.14159265358979"))
p.set_standard()

# ---- Analysis ---------------------------------------------------------------------
setf(0, "x²-2")
setf(1, "x")
setf(2, "sin(x)")
for i in (3, 4, 5):
    funcs.funcs()[i]["enabled"] = False
gv = G.GraphView()
gv.p.compile_all()
f0 = gv.p.fns[0]
roots = gv.roots_of(f0)
from cardgcalc.calc import numfmt

chk("roots", [numfmt.fmt(r) for r in roots], ["-1.414213562", "1.414213562"])
mins = gv.extrema_of(f0, False)
chk("min", mins, [D(0)])
f2 = gv.p.fns[2]
mx = gv.extrema_of(f2, True)
# golden-section search: about 8 correct digits (as before with floats)
chk("max sin", [G._fmt(x, 6) for x in mx], ["-4.71239", "1.5708", "7.85398"])
r2 = gv.roots_of(f2)
chk("sin root pi", D("3.14159265358979") in r2 and D(0) in r2, True)
f1 = gv.p.fns[1]


def g(x):
    a = f0(x)
    b = f1(x)
    return None if a is None or b is None else a - b


chk("isect", gv.roots_of(g), [D(-1), D(2)])
from cardgcalc.calc import fn as F

chk("integ", numfmt.fmt(F.integ(G._raising(f1), D(0), D(3))), "4.5")
d = F.deriv(G._raising(f0), D(3))
chk("deriv", F.clean(d), D(6))

# trace steps on a 0.1 grid
v = gv.p.v
v.update({"xmin": D(0), "xmax": D("23.9")})
gv.tx = D(0)
gv.tr = 0
gv.mode = "trace"
gv.trace_move(1)
gv.trace_move(1)
gv.trace_move(1)
chk("trace 0.3", gv.tx, D("0.3"))
chk("trace text", gv.trace_text(), "Y1 x=0.3 y=-1.91")

# polar / param points
setf(3, "2", "r")
funcs.funcs()[3]["enabled"] = True
gv = G.GraphView()
gv.p.compile_all()
x, y = gv.p.point(3, D("3.14159265358979") / 2)
chk("polar", (x, y), (D(0), D(2)))
t0, st, n = gv.p.t_values()
chk("t_values n", n, 121)

# ---- Table -------------------------------------------------------------------------
funcs.table()["start"] = D(0)
funcs.table()["step"] = D("0.1")
tb = TB.Table()
tb.compile()
chk("table x3", tb.x_at(3), D("0.3"))
chk("table x7", tb.x_at(7), D("0.7"))
chk("table y", tb.fns[0](tb.x_at(3)), D("-1.91"))
chk("cell", TB._cell(D(1) / 3, TB.CW), "0.3333333")
chk("cell big", TB._cell(D("123456789012"), TB.CW), "1.235E11")
chk("cell none", TB._cell(None, TB.CW), "undef")
print("FAILS:", fails)
