# Decimal (BCD) results of the polynomial / linear algebra code.
import sys
sys.path.insert(0, "src")
from bcd import D
from nc.calc import linalg, poly, numfmt
from nc.calc.dec import DC

fails = 0


def eq(name, got, want):
    """Exact comparison; want given as strings (D) / tuples (DC) / lists."""
    global fails

    def conv(w):
        if isinstance(w, list):
            return [conv(x) for x in w]
        if isinstance(w, tuple):
            return DC(D(w[0]), D(w[1]))
        if isinstance(w, str):
            return D(w)
        return w

    def same(a, b):
        if isinstance(b, list):
            return isinstance(a, list) and len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if isinstance(b, DC):
            return isinstance(a, DC) and a.real == b.real and a.imag == b.imag
        return isinstance(a, D) and a == b

    w = conv(want)
    if not same(got, w):
        fails += 1
        print("FAIL", name, got, "want", w)


def kinds(name, v):
    """No Python float / complex anywhere in a result."""
    global fails
    if isinstance(v, (list, tuple)):
        for x in v:
            kinds(name, x)
    elif isinstance(v, (float, complex)):
        fails += 1
        print("FAIL type", name, repr(v))


# polynomials
eq("cubic 1,2,3", poly.roots([1, -6, 11, -6]), ["1", "2", "3"])
eq("x²+1", poly.roots([1, 0, 1]), [("0", "1"), ("0", "-1")])
eq("quad", poly.roots([1, -3, 2]), ["1", "2"])
eq("2x²-3x+1", poly.roots([2, -3, 1]), ["0.5", "1"])
eq("decimal coefs", poly.roots([D("0.5"), D("-0.75"), D("0.25")]), ["0.5", "1"])
eq("quartic", poly.roots([1, 0, -5, 0, 4]), ["-2", "-1", "1", "2"])
eq("triple", poly.roots([1, -3, 3, -1]), ["1", "1", "1"])
eq("quadruple", poly.roots([1, -4, 6, -4, 1]), ["1", "1", "1", "1"])
eq("x³-1 real", poly.roots([1, 0, 0, -1])[0], "1")
eq("±√2 symmetric", [abs(r) for r in poly.roots([1, 0, -2])], ["1.4142135623731", "1.4142135623731"])
eq("decimal roots", poly.roots([1, D("-0.3"), D("0.02")]), ["0.1", "0.2"])
eq("cubic decimals", poly.roots([1, D("-0.6"), D("0.11"), D("-0.006")]), ["0.1", "0.2", "0.3"])
for c in ([1, -6, 11, -6], [1, 0, 1], [1, 0, 0, -1], [1, 2, 3, 4, 5], [1, 0, 0, 0, 1]):
    kinds("roots %s" % c, poly.roots(c))
ex = poly.exact_quadratic(1, -2, -1)
if [s for _, s in ex] != ["1-√2", "1+√2"]:
    fails += 1
    print("FAIL exact", ex)
kinds("exact", [v for v, _ in ex] + [v for v, _ in poly.exact_quadratic(1, 1, 1)])

# linear algebra
A = [[2, 1], [1, 3]]
eq("det", linalg.det(A), "5")
eq("det3", linalg.det([[1, 2, 3], [4, 5, 6], [7, 8, 10]]), "-3")
eq("det decimal", linalg.det([[D("0.1"), D("0.2")], [D("0.3"), D("0.4")]]), "-0.02")
eq("det 4x4", linalg.det([[2, 0, 1, 3], [1, 1, 0, 2], [0, 3, 1, 1], [4, 1, 2, 0]]), "-32")
eq("inverse", linalg.inverse(A), [["0.6", "-0.2"], ["-0.2", "0.4"]])
eq("inverse decimal", linalg.inverse([[D("0.1"), D("0.2")], [D("0.3"), D("0.4")]]), [["-20", "10"], ["15", "-5"]])
eq("A·A⁻¹", linalg.mul(A, linalg.inverse(A)), [["1", "0"], ["0", "1"]])
eq("solve", linalg.solve([[1, 1], [1, -1]], [3, 1])[1], ["2", "1"])
eq("solve decimal", linalg.solve([[D("0.1"), D("0.2")], [D("0.3"), D("0.4")]], [D("0.5"), D("1.1")])[1], ["1", "2"])
eq("power", linalg.power([[1, 1], [0, 1]], 5), [["1", "5"], ["0", "1"]])
eq("power -1", linalg.power(A, -1), [["0.6", "-0.2"], ["-0.2", "0.4"]])
eq("rref", linalg.rref([[1, 2, 3], [4, 5, 6]])[0], [["1", "0", "-1"], ["0", "1", "2"]])
eq("0.1 sums", linalg.add([[D("0.1")]], [[D("0.2")]]), [["0.3"]])
if linalg.rank([[1, 2], [2, 4]]) != 1:
    fails += 1
    print("FAIL rank")
eq("complex det", linalg.det([[DC(0, 1), 1], [1, DC(0, 1)]]), "-2")
kinds("inv", linalg.inverse([[1, 2], [3, 4]]))
print("exact inv elem:", numfmt.exact(linalg.inverse([[3, 0], [0, 7]])[1][1]))
print("FAILS:", fails)
