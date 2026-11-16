# Host tests: statistics in decimal (bcd.D).
import sys
sys.path.insert(0, "src")
import bcd
from bcd import D
from cardgcalc.calc import statlib, numfmt

fails = 0


def chk(name, got, want):
    """want: exact string (D compared through str / numfmt) or D."""
    global fails
    if isinstance(want, str):
        g = numfmt.fmt(got) if not isinstance(got, str) else got
        ok = g == want
    else:
        ok = got == want
    if not ok or (isinstance(want, D) and not isinstance(got, D)):
        fails += 1
        print("FAIL", name, got, type(got).__name__, "want", want)


def isd(name, v):
    global fails
    if not isinstance(v, D):
        fails += 1
        print("FAIL type", name, v, type(v).__name__)


# exact decimal sums / means
st = dict(statlib.one_var([D("0.1"), D("0.2")]))
chk("mean 0.1,0.2", st["mean"], D("0.15"))
st = dict(statlib.one_var([D("0.1")] * 10))
chk("sum 10x0.1", st["Σx"], D(1))
chk("sigma const", st["σx"], D(0))
st = dict(statlib.one_var([1, 2, 3, 4, 5, 6, 7, 8]))
for k in ("n", "mean", "Σx", "Σx²", "σx", "sx", "Q1", "median", "Q3", "min", "max", "IQR", "range"):
    isd("1var " + k, st[k])
chk("mean", st["mean"], D("4.5"))
chk("Q1", st["Q1"], D("2.5"))
chk("Q3", st["Q3"], D("6.5"))
chk("sigma", st["σx"], "2.291287847")
chk("s", st["sx"], "2.449489743")
# frequencies (old JSON may hold ints/floats)
st = dict(statlib.one_var([1.5, 2, 3], [2, 1, 1.0]))
chk("freq n", st["n"], D(4))
chk("freq mean", st["mean"], D(2))
chk("freq mode", st["mode"], D("1.5"))
# 2-var
st = dict(statlib.two_var([D("0.1"), D("0.2"), D("0.3")], [1, 2, 3]))
chk("2v Σx", st["Σx"], D("0.6"))
chk("2v Σxy", st["Σxy"], D("1.4"))
chk("2v r", st["r"], D(1))
for k, v in st.items():
    isd("2var " + k, v)
# regressions
reg = statlib.regression("lin", [1, 2, 3], [D("2.1"), D("4.1"), D("6.1")])
c = dict(reg["coef"])
chk("lin a", c["a"], D(2))
chk("lin b", c["b"], D("0.1"))
chk("lin r2", reg["r2"], D(1))
chk("lin f", reg["f"](D(10)), D("20.1"))
reg = statlib.regression("quad", [0, 1, 2, 3], [1, 2, 5, 10])
c = dict(reg["coef"])
chk("quad", [numfmt.fmt(c[k]) for k in "abc"], ["1", "0", "1"])
chk("quad r2", reg["r2"], "1")
import math
reg = statlib.regression("exp", [0, 1, 2], [1, bcd.e, bcd.e ** 2])
c = dict(reg["coef"])
chk("exp", [numfmt.fmt(c["a"]), numfmt.fmt(c["b"])], ["1", "1"])
reg = statlib.regression("log", [1, bcd.e, bcd.e ** 2], [2, 5, 8])
c = dict(reg["coef"])
chk("log", [numfmt.fmt(c["a"]), numfmt.fmt(c["b"])], ["2", "3"])
reg = statlib.regression("pow", [1, 2, 4], [3, 12, 48])
c = dict(reg["coef"])
chk("pow", [numfmt.fmt(c["a"]), numfmt.fmt(c["b"])], ["3", "2"])
isd("pow f", reg["f"](D(3)))
chk("pow f(3)", reg["f"](D(3)), "27")
print("expr:", reg["expr"])
# distributions
chk("npdf", statlib.norm_pdf(0, 0, 1), "0.3989422804")
chk("ncdf", statlib.norm_cdf(-1, 1, 0, 1), "0.6826894921")
chk("ncdf inf", statlib.norm_cdf(-math.inf, 0, 0, 1), "0.5")
chk("invn", statlib.inv_norm(D("0.975"), 0, 1), "1.959963985")
x1, x2 = statlib.inv_norm(D("0.95"), 0, 1, "center")
chk("invn c", x2, "1.959963985")
chk("bpdf", statlib.binom_pdf(3, 10, D("0.5")), D("0.1171875"))
chk("bcdf", statlib.binom_cdf(3, 10, D("0.5")), D("0.171875"))
chk("bpdf big", statlib.binom_pdf(500, 1000, D("0.5")), "0.02522501818")
chk("ppdf", statlib.poisson_pdf(2, 3), "0.2240418077")
chk("pcdf", statlib.poisson_cdf(2, 3), "0.4231900811")
chk("ppdf big", statlib.poisson_pdf(100, 100), "0.03986099681")
for nm, v in (("npdf", statlib.norm_pdf(1, 0, 1)), ("ncdf", statlib.norm_cdf(0, 1)),
              ("bpdf", statlib.binom_pdf(2, 5, D("0.3"))), ("ppdf", statlib.poisson_pdf(1, 2))):
    isd(nm, v)
print("FAILS:", fails)
