import sys, math
sys.path.insert(0, "src")
from cardgcalc.calc import linalg, poly, statlib, numfmt
fails = 0
def chk(name, got, want, tol=1e-9):
    global fails
    def close(a, b):
        if isinstance(a, (list, tuple)):
            return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
        if isinstance(a, str) or isinstance(b, str) or a is None or b is None:
            return a == b
        return abs(a - b) <= tol * max(1, abs(b))
    if not close(got, want):
        fails += 1
        print("FAIL", name, got, "want", want)

A = [[2, 1], [1, 3]]
chk("det", linalg.det(A), 5)
chk("inv", linalg.inverse(A), [[0.6, -0.2], [-0.2, 0.4]])
chk("mul", linalg.mul(A, linalg.inverse(A)), [[1, 0], [0, 1]])
chk("det3", linalg.det([[1,2,3],[4,5,6],[7,8,10]]), -3)
chk("rank", linalg.rank([[1,2],[2,4]]), 1)
chk("solve", linalg.solve([[1,1],[1,-1]], [3,1]), ("unique", [2, 1]))
chk("none", linalg.solve([[1,1],[1,1]], [1,2])[0], "none")
chk("inf", linalg.solve([[1,1],[2,2]], [1,2])[0], "inf")
chk("pow", linalg.power([[1,1],[0,1]], 5), [[1,5],[0,1]])
chk("powneg", linalg.power(A, -1), [[0.6, -0.2], [-0.2, 0.4]])
try:
    linalg.inverse([[1,2],[2,4]]); fails += 1; print("FAIL singular")
except linalg.MatrixError:
    pass

chk("q roots", poly.roots([1, -3, 2]), [1, 2])
r = poly.roots([1, 0, 1])
chk("q cplx", [r[0].imag, r[1].imag], [1, -1])
chk("cubic", poly.roots([1, -6, 11, -6]), [1, 2, 3])
chk("quartic", poly.roots([1, 0, -5, 0, 4]), [-2, -1, 1, 2])
r = poly.roots([1, 0, 0, -1])
chk("cubic cplx n", len(r), 3); chk("cubic cplx real", r[0], 1)
chk("double root", poly.roots([1, -2, 1]), [1, 1])
chk("triple", poly.roots([1, -3, 3, -1]), [1, 1, 1], 1e-4)
ex = poly.exact_quadratic(1, -2, -1)
print("exact x²-2x-1:", ex)
ex = poly.exact_quadratic(1, 1, 1)
print("exact x²+x+1:", ex)
print("exact 2x²-3x+1:", poly.exact_quadratic(2, -3, 1))
print("exact x²-2:", poly.exact_quadratic(1, 0, -2))
print("exact x²+4:", poly.exact_quadratic(1, 0, 4))

st = dict(statlib.one_var([1, 2, 3, 4, 5, 6, 7, 8]))
chk("mean", st["mean"], 4.5); chk("med", st["median"], 4.5); chk("q1", st["Q1"], 2.5); chk("q3", st["Q3"], 6.5)
chk("sigma", st["σx"], math.sqrt(5.25))
st = dict(statlib.one_var([1, 2, 3, 4, 5, 6, 7]))
chk("q1 odd", st["Q1"], 2); chk("q3 odd", st["Q3"], 6)
st = dict(statlib.one_var([1, 2, 3], [2, 1, 1]))
chk("freq n", st["n"], 4); chk("freq mean", st["mean"], 7/4); chk("mode", st["mode"], 1)
reg = statlib.regression("lin", [1, 2, 3], [2, 4, 6.5])
print("lin", reg["coef"], reg["r"], reg["expr"])
reg = statlib.regression("quad", [0, 1, 2, 3], [1, 2, 5, 10])
chk("quad", [c[1] for c in reg["coef"]], [1, 0, 1])
reg = statlib.regression("exp", [0, 1, 2], [1, math.e, math.e**2])
chk("exp", [c[1] for c in reg["coef"]], [1, 1])
reg = statlib.regression("pow", [1, 2, 4], [3, 12, 48])
chk("pow", [c[1] for c in reg["coef"]], [3, 2])
chk("normcdf", statlib.norm_cdf(-1, 1), 0.6826894921, 1e-8)
chk("invnorm", statlib.inv_norm(0.975), 1.959963985, 1e-8)
chk("binpdf", statlib.binom_pdf(3, 10, 0.5), 0.1171875)
chk("bincdf", statlib.binom_cdf(3, 10, 0.5), 0.171875)
chk("poi", statlib.poisson_pdf(2, 3), 0.2240418077, 1e-8)
print("FAILS:", fails)

from cardgcalc.apps.basen import Machine, BaseError
m = Machine(32, True)
chk("b add", m.evaluate("1+2*3", 10), 7)
chk("b hex", m.evaluate("FF+1", 16), 256)
chk("b and", m.evaluate("12 AND 10", 10), 8)
chk("b or", m.evaluate("12 or 3", 10), 15)
chk("b xor", m.evaluate("0x0F ^ 0xFF", 10), 240)
chk("b not", m.evaluate("NOT 0", 10), -1)
chk("b shl", m.evaluate("1 SHL 31", 10), -2147483648)
chk("b shr", m.evaluate("-1 >> 28", 10), 15)
chk("b div", m.evaluate("-7/2", 10), -3)
chk("b mod", m.evaluate("-7%2", 10), -1)
chk("b ovf", m.evaluate("2147483647+1", 10), -2147483648)
chk("b bin", m.evaluate("1011", 2), 11)
chk("b fmt", m.fmt(-1, "HEX"), "FFFFFFFF")
chk("b ans", m.evaluate("Ans*2", 10, 21), 42)
m8 = Machine(8, False)
chk("u8", m8.evaluate("255+1", 10), 0)
chk("u8 not", m8.evaluate("NOT 0", 10), 255)
try:
    m.evaluate("1/0", 10); fails += 1; print("FAIL div0")
except BaseError:
    pass
try:
    m.evaluate("12G", 16); fails += 1; print("FAIL bad hex")
except BaseError:
    pass
print("FAILS:", fails)
