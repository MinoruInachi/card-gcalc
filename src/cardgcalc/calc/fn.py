# Math function library used by compiled calculator expressions.
#
# All calculator numbers are decimal: bcd.D (15 significant digits) and
# dec.DC for complex values.  Python ints may appear (loop counters of Σ/∏)
# and mix freely with D.  A few special functions (gamma, erf) are evaluated
# in binary floating point and rounded to 15 digits.
import math
import bcd
from bcd import D
from cardgcalc.calc import dec
from cardgcalc.calc.dec import DC, num, ZERO, ONE

try:
    import random
except ImportError:
    random = None

pi = bcd.pi
e = bcd.e
inf = math.inf  # only as an integration bound
i = DC(ZERO, ONE)

_EPS12 = D("1e-12")


class CalcError(Exception):
    pass


def _err(msg="Math error"):
    from cardgcalc.calc.expr import CalcError as CE

    raise CE(msg)


def check(v, complex_mode):
    """Normalise a result to D / DC: ints and floats become D, a complex
    value with a zero imaginary part becomes real."""
    if isinstance(v, bool):
        return ONE if v else ZERO
    if isinstance(v, int):
        return D(v)
    if isinstance(v, float):
        if v != v or v in (math.inf, -math.inf):
            _err("Math error")
        return D(v)
    if isinstance(v, complex):
        v = dec.cx(v)
    if isinstance(v, DC):
        v = dec.simp(v, D("1e-14"))
        if isinstance(v, DC):
            if not complex_mode:
                _err("Non-real error")
            return v
    return v


def is_int(x):
    return dec.isint(x)


def _isc(x):
    return isinstance(x, (DC, complex))


def div(a, b):
    if b == 0:
        _err("Math error: ÷0")
    a = num(a)
    b = num(b)
    if isinstance(b, DC) and not isinstance(a, DC):
        a = DC(a)
    return a / b


def _small_frac(x, maxden=64):
    """x ~ p/q with q <= maxden (within 1e-12)?  returns (p, q) or None.
    Continued fraction of the exact decimal value, in integer arithmetic."""
    neg, c, ex = bcd.parts(x)
    if ex >= 0:
        return (-c if neg else c) * 10 ** ex, 1
    P = c
    Q = 10 ** (-ex)
    h0, h1, k0, k1 = 0, 1, 1, 0
    p, q = P, Q
    while q:
        a = p // q
        h0, h1 = h1, a * h1 + h0
        k0, k1 = k1, a * k1 + k0
        if k1 > maxden:
            return None
        if abs(h1 * Q - k1 * P) * 1000000000000 < k1 * Q:
            return (-h1 if neg else h1), k1
        p, q = q, p - a * q
    return None


def pw(a, b):
    a = num(a)
    b = num(b)
    if _isc(a) or _isc(b):
        return dec.cpow(a, b)
    if a < 0 and not bcd.isint(b):
        # odd roots of negative numbers are real: (-8)^(1/3) = -2
        fr = _small_frac(b)
        if fr and fr[1] % 2 == 1:
            r = root(-a, fr[1])
            if fr[0] != 1:
                r = r ** abs(fr[0])
                if fr[0] < 0:
                    r = 1 / r
            return -r if fr[0] % 2 else r
        return dec.cpow(a, b)
    if a == 0 and b < 0:
        _err("Math error: ÷0")
    if a == e:
        return bcd.exp(b)
    if bcd.isint(b) or bcd.isint(b * 2):
        return a ** b
    fr = None
    if not bcd.isint(b) and a > 0:
        # exact rational powers: 8^(1/3) = 2, 4^(1.5) = 8
        fr = _small_frac(b, 12)
    if fr and fr[1] > 2:
        r = root(a, fr[1])
        return r ** fr[0]
    return a ** b


def fact(n):
    n = num(n)
    if bcd.isint(n):
        n = int(n)
        if n < 0:
            _err()
        if n > 69:
            _err("Math error: overflow")
        return D(math.factorial(n))
    return gamma(n + 1)


def _ints(n, r):
    if not (bcd.isint(num(n)) and bcd.isint(num(r))):
        _err()
    n = int(n)
    r = int(r)
    if r < 0 or n < 0 or r > n:
        _err()
    return n, r


def nPr(n, r):
    n, r = _ints(n, r)
    out = 1
    for k in range(n - r + 1, n + 1):
        out *= k
    return D(out)


def nCr(n, r):
    n, r = _ints(n, r)
    r = min(r, n - r)
    out = 1
    for k in range(r):
        out = out * (n - k) // (k + 1)
    return D(out)


def ln(x):
    x = num(x)
    if _isc(x) or x < 0:
        return dec.cln(x)
    if x == 0:
        _err()
    return bcd.ln(x)


def _snap_int(r, base, x):
    """log results that are integers: base^n == x exactly -> n."""
    n = bcd.rnd(r)
    if n != r and abs(r - n) < D("1e-12") and abs(n) < 400:
        try:
            if base ** n == x:
                return n
        except (OverflowError, ValueError, ZeroDivisionError):
            pass
    return r


def log(x, b=None):
    x = num(x)
    if b is None:
        if _isc(x) or x < 0:
            return dec.cln(x) / bcd.ln(D(10))
        if x == 0:
            _err()
        return bcd.log10(x)
    b = num(b)
    if _isc(x) or _isc(b) or x < 0 or b < 0:
        return dec.cln(x) / dec.cln(b)
    if x == 0 or b == 0 or b == 1:
        _err()
    return _snap_int(bcd.log10(x) / bcd.log10(b), b, x)


def log2(x):
    return log(x, 2)


def exp(x):
    x = num(x)
    if _isc(x):
        return dec.cexp(x)
    return bcd.exp(x)


def sqrt(x):
    x = num(x)
    if _isc(x) or x < 0:
        return dec.csqrt(x)
    return bcd.sqrt(x)


def cbrt(x):
    x = num(x)
    if _isc(x):
        return dec.cpow(x, ONE / 3)
    return bcd.cbrt(x)


def root(x, n):
    x = num(x)
    n = num(n)
    if not _isc(x) and not _isc(n) and bcd.isint(n) and n >= 1:
        k = int(n)
        if x >= 0 or k % 2 == 1:
            return bcd.root(x, k)
    return pw(x, ONE / n)


def abs_(x):
    return abs(num(x))


def floor(x):
    return bcd.floor(x)


def ceil(x):
    return bcd.ceil(x)


def round_(x, n=0):
    return bcd.rnd(x, int(n))


def int_(x):
    return bcd.trunc(x)


def fpart(x):
    return bcd.frac(x)


def sign(x):
    x = num(x)
    return ONE if x > 0 else (-ONE if x < 0 else ZERO)


def mod(a, b):
    if b == 0:
        _err()
    return num(a) % num(b)


def gcd(a, b):
    a = abs(int(a))
    b = abs(int(b))
    while b:
        a, b = b, a % b
    return D(a)


def lcm(a, b):
    g = int(gcd(a, b))
    return D(abs(int(a) * int(b)) // g if g else 0)


def min_(*a):
    return min(a)


def max_(*a):
    return max(a)


def mean(*a):
    return sum_(*a) / len(a)


def sum_(*a):
    s = ZERO
    for v in a:
        s = s + v
    return s


def rand():
    if random is None:
        _err()
    return D(random.random())


def randint(a, b):
    return D(random.randint(int(a), int(b)))


def isprime(n):
    if not bcd.isint(num(n)):
        return ZERO
    n = int(n)
    if n < 2:
        return ZERO
    if n % 2 == 0:
        return ONE if n == 2 else ZERO
    k = 3
    while k * k <= n:
        if n % k == 0:
            return ZERO
        k += 2
    return ONE


def _flt(fn, x):
    """Special functions in binary floating point, result rounded to 15 digits."""
    v = fn(dec.f(x))
    if v != v or v in (math.inf, -math.inf):
        _err()
    return D(v)


def gamma(x):
    x = num(x)
    if bcd.isint(x) and 0 < x <= 70:
        return D(math.factorial(int(x) - 1))
    return _flt(math.gamma, x)


def erf(x):
    return _flt(math.erf, x)


def erfc(x):
    return _flt(math.erfc, x)


def hypot(a, b):
    return dec.cabs(DC(num(a), num(b)))


def re(z):
    return z.real if _isc(z) else z


def im(z):
    return z.imag if _isc(z) else ZERO


def conj(z):
    return DC(z.real, -z.imag) if _isc(z) else z


# ---- numerical calculus ---------------------------------------------------
def integ(f, a, b):
    """Adaptive Gauss-Kronrod integration of f over [a, b]."""
    a_inf = a == -math.inf
    b_inf = b == math.inf
    if not a_inf:
        a = num(a)
    if not b_inf:
        b = num(b)
    if not a_inf and not b_inf:
        if a == b:
            return ZERO
        if a > b:
            return -integ(f, b, a)
        return _result(_gauss_kronrod(f, a, b, _TOL))
    # substitute x = t/(1-t^2) on (-1,1)
    lo = -ONE if a_inf else _inv_sub(a)
    hi = ONE if b_inf else _inv_sub(b)
    eps = D("1e-9")

    def g(t):
        d = 1 - t * t
        return f(t / d) * (1 + t * t) / (d * d)

    return _result(_gauss_kronrod(g, lo + eps, hi - eps, _TOL))


def _result(v):
    # the quadrature is good to ~1e-11: drop the noise in the last digits
    return clean(bcd.rsig(num(v), 13), D("1e-12"))


def _inv_sub(x):
    # inverse of x = t/(1-t^2)
    if x == 0:
        return ZERO
    return (-1 + bcd.sqrt(1 + 4 * x * x)) / (2 * x)


_GK_X = tuple(D(s) for s in ("0.991455371120813", "0.949107912342759", "0.864864423359769",
                              "0.741531185599394", "0.586087235467691", "0.405845151377397",
                              "0.207784955007898", "0"))
_GK_WK = tuple(D(s) for s in ("0.0229353220105292", "0.0630920926299786", "0.104790010322250",
                               "0.140653259715525", "0.169004726639267", "0.190350578064785",
                               "0.204432940075298", "0.209482141084728"))
_GK_WG = tuple(D(s) for s in ("0.129484966168870", "0.279705391489277", "0.381830050505119",
                               "0.417959183673469"))
_TOL = D("1e-11")


def _gk15(f, a, b):
    c = (a + b) / 2
    h = (b - a) / 2
    fc = num(f(c))
    k = fc * _GK_WK[7]
    g = fc * _GK_WG[3]
    for j in range(7):
        dx = h * _GK_X[j]
        s = num(f(c - dx)) + num(f(c + dx))
        k = k + _GK_WK[j] * s
        if j % 2 == 1:
            g = g + _GK_WG[j // 2] * s
    return k * h, abs((k - g) * h)


def _gauss_kronrod(f, a, b, tol, depth=0):
    val, err = _gk15(f, a, b)
    if err < tol * max(ONE, abs(val)) or depth > 12:
        return val
    m = (a + b) / 2
    return _gauss_kronrod(f, a, m, tol / 2, depth + 1) + _gauss_kronrod(f, m, b, tol / 2, depth + 1)


def deriv(f, x):
    """Numerical derivative (Richardson extrapolated central difference)."""
    x = num(x)
    h = D("1e-3") * max(ONE, abs(x))
    d1 = (num(f(x + h)) - num(f(x - h))) / (2 * h)
    h2 = h / 2
    d2 = (num(f(x + h2)) - num(f(x - h2))) / (2 * h2)
    return clean((4 * d2 - d1) / 3, D("1e-9"))


def deriv2(f, x):
    x = num(x)
    h = D("1e-3") * max(ONE, abs(x))
    return (num(f(x + h)) - 2 * num(f(x)) + num(f(x - h))) / (h * h)


def sigma(f, a, b):
    a = int(a)
    b = int(b)
    s = ZERO
    for k in range(a, b + 1):
        s = s + f(D(k))
    return s


def prod(f, a, b):
    a = int(a)
    b = int(b)
    s = ONE
    for k in range(a, b + 1):
        s = s * f(D(k))
    return s


def _real(y):
    return isinstance(y, (D, int)) and not isinstance(y, bool)


def solve(f, x0=0, x1=None):
    """Find a root of f.  With a bracket [x0, x1] uses bisection,
    otherwise Newton from x0 with fallback scanning."""
    x0 = num(x0)
    if x1 is not None:
        r = bracket_root(f, x0, num(x1))
        if r is None:
            _err("No solution")
        return r
    x = x0
    tol = D("1e-13")
    for _ in range(100):
        try:
            fx = f(x)
            if not _real(fx):
                break
            d = deriv(f, x)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            break
        if fx == 0:
            return x
        if d == 0:
            x = x + D("1e-3") * max(ONE, abs(x))
            continue
        nx = x - fx / d
        if abs(nx - x) <= tol * max(ONE, abs(x)):
            return clean(nx)
        x = nx
    # scan outward for a sign change
    for span in (1, 10, 100, 1000, 100000):
        r = scan_root(f, x0 - span, x0 + span, 200)
        if r is not None:
            return r
    _err("No solution")


def scan_root(f, a, b, n=200):
    a = num(a)
    b = num(b)
    prev_x = a
    try:
        prev = f(a)
    except Exception:
        prev = None
    for k in range(1, n + 1):
        x = a + (b - a) * k / n
        try:
            y = f(x)
        except Exception:
            y = None
        if prev is not None and y is not None and _real(y) and _real(prev):
            if prev == 0:
                return prev_x
            if (prev < 0) != (y < 0):
                r = bracket_root(f, prev_x, x)
                if r is not None:
                    return r
        prev, prev_x = y, x
    return None


def bracket_root(f, a, b, it=200):
    a = num(a)
    b = num(b)
    fa = f(a)
    fb = f(b)
    if not (_real(fa) and _real(fb)):
        return None
    if fa == 0:
        return a
    if fb == 0:
        return b
    if (fa < 0) == (fb < 0):
        return None
    for _ in range(it):
        m = (a + b) / 2
        if m == a or m == b:
            break
        fm = f(m)
        if fm == 0:
            return clean(m)
        if (fm < 0) == (fa < 0):
            a, fa = m, fm
        else:
            b, fb = m, fm
    m = a if abs(fa) <= abs(fb) else b
    # A sign change across a pole is not a root.
    if abs(f(m)) > D("1e-6") * max(ONE, abs(fa), abs(fb)):
        return None
    return clean(m)


def minimize(f, a, b, it=100):
    """Golden-section search for a minimum of f on [a, b]."""
    a = num(a)
    b = num(b)
    g = (bcd.sqrt(5) - 1) / 2
    c = b - g * (b - a)
    d = a + g * (b - a)
    fc = f(c)
    fd = f(d)
    for _ in range(it):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
        if abs(b - a) < D("1e-12") * max(ONE, abs(a)):
            break
    x = (a + b) / 2
    return clean(x), f(x)


def clean(x, tol=None):
    """Snap values extremely close to an integer."""
    if isinstance(x, D):
        r = bcd.rnd(x)
        if r != x and abs(x - r) < (tol or D("1e-11")) * max(ONE, abs(x)):
            return r
    return x


# ---- namespace ------------------------------------------------------------
_UNIT = {"rad": 0, "deg": 1, "grad": 2}


def namespace(angle="rad", complex_mode=False):
    """Build the evaluation namespace for the given angle unit."""
    g = globals()
    ns = {}
    for k in ("pi", "e", "inf", "i", "div", "pw", "fact", "nPr", "nCr", "ln", "log", "log2", "exp",
              "sqrt", "cbrt", "root", "abs_", "floor", "ceil", "round_", "int_", "fpart", "sign",
              "mod", "gcd", "lcm", "min_", "max_", "mean", "sum_", "rand", "randint", "isprime",
              "gamma", "erf", "erfc", "hypot", "re", "im", "conj", "integ", "deriv", "sigma",
              "prod", "solve"):
        ns[k] = g[k]
    u = _UNIT.get(angle, 0)
    # complex arguments are always taken in radians after this conversion
    k_in = (ONE, pi / 180, pi / 200)[u]

    def sin(x):
        x = num(x)
        if _isc(x):
            return dec.csin(x * k_in)
        return bcd.sin(x, u)

    def cos(x):
        x = num(x)
        if _isc(x):
            return dec.ccos(x * k_in)
        return bcd.cos(x, u)

    def tan(x):
        x = num(x)
        if _isc(x):
            return dec.ctan(x * k_in)
        return bcd.tan(x, u)

    def _inv(rf, cf, x):
        x = num(x)
        if _isc(x) or abs(x) > 1:
            if not complex_mode:
                _err()
            r = cf(x)
            return r / k_in if u else r
        return rf(x, u)

    def asin(x):
        return _inv(bcd.asin, dec.casin, x)

    def acos(x):
        return _inv(bcd.acos, dec.cacos, x)

    def atan(x):
        return bcd.atan(x, u)

    def atan2(y, x):
        return bcd.atan2(y, x, u)

    def sec(x):
        return div(1, cos(x))

    def csc(x):
        return div(1, sin(x))

    def cot(x):
        return div(1, tan(x))

    def todeg(x):
        return num(x) * 180 / pi

    def torad(x):
        return num(x) * pi / 180

    def arg(z):
        z = num(z)
        if _isc(z):
            r = dec.carg(dec.cx(z))
            return r / k_in if u else r
        if z >= 0:
            return ZERO
        return (pi, D(180), D(200))[u]

    ns["sin"] = sin
    ns["cos"] = cos
    ns["tan"] = tan
    ns["asin"] = asin
    ns["acos"] = acos
    ns["atan"] = atan
    ns["atan2"] = atan2
    ns["sec"] = sec
    ns["csc"] = csc
    ns["cot"] = cot
    ns["todeg"] = todeg
    ns["torad"] = torad
    ns["arg"] = arg
    ns["sinh"] = bcd.sinh
    ns["cosh"] = bcd.cosh
    ns["tanh"] = bcd.tanh
    ns["asinh"] = bcd.asinh
    ns["acosh"] = bcd.acosh
    ns["atanh"] = bcd.atanh
    return ns
