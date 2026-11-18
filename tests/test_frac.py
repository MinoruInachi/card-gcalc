# Exact (fraction) mode of the calculator: Context.evaluate(src, exact=True).
import sys
sys.path.insert(0, "src")
from cardgcalc.calc.expr import Context, CalcError, has_decimal
from cardgcalc.calc import numfmt, frac

ctx = Context()
fails = 0


def show(v):
    if isinstance(v, frac.Q):
        return frac.to_str(v)
    return numfmt.fmt(v)


def t(src, want, angle="rad", cplx=False):
    global fails
    ctx.angle = angle
    ctx.complex = cplx
    try:
        got = show(ctx.evaluate(src, exact=True))
    except CalcError as e:
        got = "ERR:" + str(e)
    if got != want:
        fails += 1
        print("FAIL", src, "->", got, "want", want)


t("1/3+1/6", "1/2")
t("1/3×3", "1")
t("1/3×3-1", "0")
t("2/4", "1/2")
t("-6/4", "-3/2")
t("1/7+1/13", "20/91")
t("(2/3)^2", "4/9")
t("(2/3)^-2", "9/4")
t("(2/3)⁻¹", "3/2")
t("(1/2)²+(1/2)³", "3/8")
t("√(9/4)", "3/2")
t("(4/9)^(1/2)", "2/3")
t("(4/9)^0.5", "2/3")
t("√2", "1.414213562")
t("√2×√2", "2")
t("0.1+0.2", "3/10")
t("0.1+0.2-0.3", "0")
t("1.5×2", "3")
t("1E-3", "1/1000")
t("50%", "1/2")
t("1/0", "ERR:Math error: ÷0")
t("0^-1", "ERR:Math error: ÷0")
t("π/2", "1.570796327")
t("1/2+π", "3.641592654")
t("sin(30)", "0.5", "deg")  # functions give decimals
t("2sin(30)", "1", "deg")
t("sin(30)+1/2", "1", "deg")
t("1/log(1000)", "1/3")
t("5!/3!", "20")
t("20!", "2432902008176640000")
t("1/20!", "1/2432902008176640000")
t("70!", "ERR:Math error: overflow")
t("Σ(1/k,k,1,4)", "25/12")
t("∏(k/(k+1),k,1,9)", "1/10")
t("abs(-3/4)", "3/4")
t("floor(-7/2)", "-4")
t("ceil(-7/2)", "-3")
t("int(-7/2)", "-3")
t("fpart(7/2)", "1/2")
t("mod(7/2,1)", "1/2")
t("min(1/2,1/3)", "1/3")
t("max(1/2,0.6)", "3/5")
t("1/3<1/2", "1")
t("1/3=2/6", "1")
t("2^10", "1024")
t("2^0.5", "1.414213562")
t("(-8)^(1/3)", "-2")
t("2^200", "1.606938044E60")
t("10^99", "1E99")
t("10^100", "ERR:Math error")
t("1/3^70", "3.994957557E-34")
t("(1+i)/2", "0.5+0.5i", cplx=True)
t("i^2", "-1", cplx=True)
t("12345678901234567-12345678901234560", "7")
# variables keep the exact value; others see the decimal one
t("1/3→A", "1/3")
t("3A", "1")
t("Ans+1/6", "7/6")
print(ctx.vars["A"], ctx.vars["Ans"])
ctx.vars["B"] = ctx.vars["A"]
t("B×3=1", "0")  # B holds the 15-digit decimal
ctx.vars["A"] = ctx.vars["A"] + 1  # changed by another app
t("A", "1.333333333")
ctx.vars["C"] = ctx.vars["Ans"] * 0 + 5
t("C/2", "5/2")
# fraction templates (opt+/ and alt+/ on the Calc screen)
FS, FM, FE, MS, MM = frac.FS, frac.FM, frac.FE, frac.MS, frac.MM


def fr(a, b):
    return FS + a + FM + b + FE


def mx(w, a, b):
    return MS + w + MM + a + FM + b + FE


t(fr("1", "3") + "+" + fr("1", "6"), "1/2")
t(fr("2", "3") + "^2", "4/9")
t("2^" + fr("1", "2"), "1.414213562")
t("2" + fr("3", "4"), "3/2")  # implicit multiplication
t(fr(fr("1", "2"), "3"), "1/6")
t(fr("1+2", "4"), "3/4")
t(mx("2", "1", "3"), "7/3")
t(mx("2", "1", "3") + "×3", "7")
t("-" + mx("2", "1", "2"), "-5/2")
t(mx("1", "1", "2") + "+" + mx("2", "1", "3"), "23/6")
t(fr("", "3"), "ERR:Syntax error")
t(mx("", "1", "2"), "ERR:Syntax error")
t(FS + "1" + FM + "2", "ERR:Syntax error")
t(fr("1", "0"), "ERR:Math error: ÷0")
t("√" + fr("9", "4"), "3/2")
want = [FS + "7" + FM + "3" + FE, MS + "2" + MM + "1" + FM + "3" + FE, "-" + MS + "2" + MM + "1" + FM + "3" + FE]
got = [frac.text(frac.make(7, 3)), frac.text(frac.make(7, 3), True), frac.text(frac.make(-7, 3), True)]
if got != want or frac.text(frac.make(1, 3), True) != fr("1", "3") or frac.template("-2π/3") != "-" + fr("2π", "3"):
    fails += 1
    print("FAIL text", got)
# non-exact mode is unchanged
ctx.angle = "rad"
print("decimal:", numfmt.fmt(ctx.evaluate("1/3")), numfmt.fmt(ctx.evaluate("1/3×3-1")))
print("has_decimal:", has_decimal("1/2+0.5"), has_decimal("1/2"), has_decimal("2E3"))
print("FAILS:", fails)
