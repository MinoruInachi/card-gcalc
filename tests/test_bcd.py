# Tests for the bcd module (15-digit decimal numbers).  Run with the unix
# MicroPython built by tools/setup.sh (it includes the bcd C module).
import bcd
from bcd import D

fails = 0


def t(name, got, want):
    global fails
    if str(got) != want:
        fails += 1
        print("FAIL", name, "->", got, "want", want)


# exact decimal arithmetic, half-up rounding to 15 digits
t("0.1+0.2", D("0.1") + D("0.2"), "0.3")
t("1-0.9", 1 - D("0.9"), "0.1")
t("1/3", D(1) / 3, "0.333333333333333")
t("2/3", D(2) / 3, "0.666666666666667")
t("1/3*3", D(1) / 3 * 3, "0.999999999999999")
t("half-up", D("0.1234567890123455"), "0.123456789012346")
t("half-up neg", D("-0.1234567890123455"), "-0.123456789012346")
t("big int", D(123456789012345678), "1.23456789012346e+17")
t("int exact", D(999999999999999) + 1, "1e+15")
t("tiny sub", D(1) - D("1e-20"), "1")
t("float in", D(0.1), "0.1")
t("float mix", 0.5 + D("0.1"), "0.6")
t("mul", D("1.1") * D("1.1"), "1.21")
t("div exact", D(1) / 8, "0.125")
t("neg zero", -D(0), "0")
t("str", D("1e-6"), "1e-06")
t("str2", D("123.4500"), "123.45")
t("str3", D("1e15"), "1e+15")

# range
t("max", D("9.99999999999999e99"), "9.99999999999999e+99")
try:
    D("1e99") * 10
    t("overflow", "no error", "OverflowError")
except OverflowError:
    pass
t("underflow", D("1e-99") / 10, "0")

# comparisons on both sides, hashing
t("cmp", (0 < D("0.1"), D("0.1") < 1, 0.05 < D("0.1"), D(2) == 2, 2 == D(2), D("0.1") == 0.1), "(True, True, True, True, True, True)")
t("hash", {D(5): "x"}.get(5), "x")
t("int", (int(D("123.9")), int(D("-123.9")), int(D("1e20"))), "(123, -123, 100000000000000000000)")

# mod / floor division (Python semantics)
t("mod", (D(7) % 3, D(-7) % 3, D(7) % -3, D("7.5") % 2, D("0.3") % D("0.1")), "(1, 2, -2, 1.5, 0)")
t("floordiv", (D(7) // 2, D(-7) // 2), "(3, -4)")

# powers
t("pow int", D(2) ** 10, "1024")
t("pow big", D(2) ** 100, "1.26765060022823e+30")
t("pow neg", D(10) ** -3, "0.001")
t("pow half", D(2) ** D("0.5"), "1.4142135623731")
t("pow half exact", D(4) ** D("1.5"), "8")

# functions
t("sqrt", (bcd.sqrt(2), bcd.sqrt(D("2.25")), bcd.sqrt(D("1e-10"))), "(1.4142135623731, 1.5, 0.00001)")
t("cbrt", (bcd.cbrt(8), bcd.cbrt(-27), bcd.root(32, 5)), "(2, -3, 2)")
t("exp/ln", (bcd.exp(1), bcd.ln(bcd.e), bcd.ln(1), bcd.exp(0)), "(2.71828182845905, 1, 0, 1)")
t("log10", (bcd.log10(1000), bcd.log10(D("0.001")), bcd.log10(2)), "(3, -3, 0.301029995663981)")
t("pow10", (bcd.pow10(3), bcd.pow10(-2)), "(1000, 0.01)")
t("trig rad", (bcd.sin(bcd.pi), bcd.cos(bcd.pi / 2), bcd.tan(bcd.pi), bcd.sin(2 * bcd.pi), bcd.cos(bcd.pi)), "(0, 0, 0, 0, -1)")
t("trig deg", (bcd.sin(30, 1), bcd.cos(60, 1), bcd.tan(45, 1), bcd.sin(180, 1), bcd.sin(-90, 1), bcd.cos(720, 1)), "(0.5, 0.5, 1, 0, -1, 1)")
t("trig grad", (bcd.sin(100, 2), bcd.cos(200, 2)), "(1, -1)")
t("inv trig", (bcd.asin(D("0.5"), 1), bcd.acos(D("0.5"), 1), bcd.atan(1, 1), bcd.atan2(1, -1, 1), bcd.asin(1)), "(30, 60, 45, 135, 1.5707963267949)")
t("hyp", (bcd.sinh(0), bcd.cosh(0), bcd.tanh(100), bcd.asinh(0), bcd.atanh(0)), "(0, 1, 1, 0, 0)")
t("round", (bcd.rnd(D("2.5")), bcd.rnd(D("-2.5")), bcd.rnd(D("1.23456"), 3), bcd.rsig(D("123456"), 2)), "(3, -3, 1.235, 120000)")
t("floor", (bcd.floor(D("-1.5")), bcd.ceil(D("-1.5")), bcd.trunc(D("-1.5")), bcd.frac(D("-1.25"))), "(-2, -1, -1, -0.25)")
t("parts", (bcd.parts(D("-1.5")), bcd.make(0, 15, -1), bcd.isint(D("3.0")), bcd.isint(D("3.5"))), "((True, 150000000000000, -14), 1.5, True, False)")
for bad in ((bcd.sqrt, -1), (bcd.ln, 0), (bcd.asin, 2)):
    try:
        bad[0](bad[1])
        t("domain", bad, "ValueError")
    except ValueError:
        pass
try:
    bcd.tan(90, 1)
    t("tan 90", "no error", "ValueError")
except ValueError:
    pass

print("FAILS:", fails)
