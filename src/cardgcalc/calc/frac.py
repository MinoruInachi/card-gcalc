# Exact fractions for the Calc app.
#
# Q is a rational number n/d held as Python integers (d > 0, gcd(n, d) = 1).
# The calculation screen evaluates in exact mode: number literals become Q,
# and + - × ÷, integer powers and a few functions keep the result exact, so
# 1/3+1/6 is exactly 1/2.  Anything else (π, √2, sin, ...) falls back to the
# 15-digit decimal type D: a Q combined with a D gives a D.
#
# A Q whose numerator or denominator grows past LIMIT becomes a D.
import bcd
from bcd import D

LIMIT = 10 ** 30

# Markers for fractions typed as templates (drawn by cardgcalc.mathtext):
#   FS num FM den FE            num over den
#   MS whole MM num FM den FE   mixed number  whole num/den
FS = "\x0e"
FM = "\x0f"
FE = "\x10"
MS = "\x11"
MM = "\x12"
MARKS = FS + FM + FE + MS + MM
MAXBITS = 400  # largest integer power computed exactly


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def make(n, d=1):
    """n/d reduced: a Q, or a D when the parts are too large."""
    if d == 0:
        raise ZeroDivisionError
    if d < 0:
        n, d = -n, -d
    g = _gcd(abs(n), d)
    if g > 1:
        n //= g
        d //= g
    if abs(n) >= LIMIT or d >= LIMIT:
        return _dec(n, d)
    return Q(n, d)


def _dec(n, d):
    if d == 1:
        return D(n)
    return D(n) / D(d)


def from_text(s):
    """Exact value of a number literal: '12', '3.5', '.5', '1.2e-3'."""
    m, _, x = s.partition("e")
    ip, _, fp = m.partition(".")
    n = int((ip or "0") + fp)
    ex = (int(x) if x else 0) - len(fp)
    if ex >= 0:
        return make(n * 10 ** ex)
    return make(n, 10 ** -ex)


def from_dec(v):
    """Exact value of a D (terminating decimal) as Q, or None if too large."""
    neg, c, ex = bcd.parts(v)
    if ex >= 0:
        if ex > 30:
            return None
        n, d = c * 10 ** ex, 1
    else:
        if -ex > 30:
            return None
        n, d = c, 10 ** -ex
    r = make(-n if neg else n, d)
    return r if isinstance(r, Q) else None


def todec(v):
    """Q -> D; anything else is returned unchanged."""
    if isinstance(v, Q):
        return v.dec()
    return v


def exact(v):
    """int / Q -> Q; anything else is returned unchanged."""
    if isinstance(v, Q):
        return v
    if isinstance(v, int):
        return make(int(v))
    return v


def isint(v):
    return isinstance(v, Q) and v.d == 1


def to_str(v):
    """'n/d' (or 'n' for an integer)."""
    if v.d == 1:
        return "%d" % v.n
    return "%d/%d" % (v.n, v.d)


def text(v, mixed=False):
    """Template text of a non-integer Q (for display and re-entry); with
    mixed=True a value above 1 is written as a mixed number."""
    sg = "-" if v.n < 0 else ""
    n = abs(v.n)
    if mixed and n > v.d:
        return "%s%s%d%s%d%s%d%s" % (sg, MS, n // v.d, MM, n % v.d, FM, v.d, FE)
    return "%s%s%d%s%d%s" % (sg, FS, n, FM, v.d, FE)


def template(s):
    """Linear exact form 'a/b' (as numfmt.exact gives: 1/3, 2π/3, √3/2) ->
    template text; other strings are returned unchanged."""
    if s.count("/") != 1:
        return s
    a, b = s.split("/")
    sg = ""
    if a[:1] == "-":
        sg, a = "-", a[1:]
    return sg + FS + a + FM + b + FE


class Q:
    __slots__ = ("n", "d")

    def __init__(self, n, d=1):
        self.n = n
        self.d = d

    def dec(self):
        return _dec(self.n, self.d)

    # arithmetic --------------------------------------------------------
    def __add__(self, o):
        if isinstance(o, Q):
            return make(self.n * o.d + o.n * self.d, self.d * o.d)
        if isinstance(o, int):
            return make(self.n + o * self.d, self.d)
        return self.dec() + o

    def __radd__(self, o):
        if isinstance(o, int):
            return self.__add__(o)
        return o + self.dec()

    def __sub__(self, o):
        if isinstance(o, Q):
            return make(self.n * o.d - o.n * self.d, self.d * o.d)
        if isinstance(o, int):
            return make(self.n - o * self.d, self.d)
        return self.dec() - o

    def __rsub__(self, o):
        if isinstance(o, int):
            return make(o * self.d - self.n, self.d)
        return o - self.dec()

    def __mul__(self, o):
        if isinstance(o, Q):
            return make(self.n * o.n, self.d * o.d)
        if isinstance(o, int):
            return make(self.n * o, self.d)
        return self.dec() * o

    def __rmul__(self, o):
        if isinstance(o, int):
            return self.__mul__(o)
        return o * self.dec()

    def __truediv__(self, o):
        if isinstance(o, int):
            o = Q(o)
        if isinstance(o, Q):
            if o.n == 0:
                raise ZeroDivisionError
            return make(self.n * o.d, self.d * o.n)
        return self.dec() / o

    def __rtruediv__(self, o):
        if isinstance(o, int):
            return Q(o).__truediv__(self)
        return o / self.dec()

    def __pow__(self, o):
        return power(self, o)

    def __neg__(self):
        return Q(-self.n, self.d)

    def __pos__(self):
        return self

    def __abs__(self):
        return Q(abs(self.n), self.d)

    # comparison --------------------------------------------------------
    def _cmp(self, o):
        """sign of self - o, or None for an unsupported type."""
        if isinstance(o, int):
            o = Q(o)
        if isinstance(o, Q):
            a = self.n * o.d - o.n * self.d
        elif isinstance(o, D):
            a = self.dec() - o
        else:
            return None
        return (a > 0) - (a < 0)

    def __eq__(self, o):
        c = self._cmp(o)
        return c == 0 if c is not None else False

    def __ne__(self, o):
        return not self.__eq__(o)

    def __lt__(self, o):
        return self._cmp(o) < 0

    def __le__(self, o):
        return self._cmp(o) <= 0

    def __gt__(self, o):
        return self._cmp(o) > 0

    def __ge__(self, o):
        return self._cmp(o) >= 0

    def __hash__(self):
        return hash((self.n, self.d))

    def __bool__(self):
        return self.n != 0

    def __int__(self):
        # toward zero, like int() of a float
        q = abs(self.n) // self.d
        return -q if self.n < 0 else q

    def __repr__(self):
        return "Q(%s)" % to_str(self)


def _bits(n):
    """Bit length of an integer n >= 0 (rounded up to a multiple of 4)."""
    return len("%x" % n) * 4 if n else 0


def _isqrt(n):
    """floor(sqrt(n)) for an integer n >= 0."""
    if n < 2:
        return n
    x = 1 << ((_bits(n) + 1) // 2)
    while True:
        y = (x + n // x) // 2
        if y >= x:
            return x
        x = y


def sqrt_(q):
    """Exact square root of a Q, or None if it is not a rational square."""
    if q.n < 0:
        return None
    a = _isqrt(q.n)
    b = _isqrt(q.d)
    if a * a == q.n and b * b == q.d:
        return Q(a, b)
    return None


def power(a, b):
    """a^b for a Q a and an integer Q b, or None if it is not exact
    (fractional exponent, or the result would be too large)."""
    if not isinstance(b, Q):
        if isinstance(b, int):
            b = Q(b)
        else:
            return None
    if b.d == 2:
        r = sqrt_(a)
        if r is None:
            return None
        b = Q(b.n)
        a = r
    if b.d != 1:
        return None
    k = b.n
    if k < 0:
        if a.n == 0:
            raise ZeroDivisionError
        a = Q(a.d, a.n) if a.n > 0 else Q(-a.d, -a.n)
        k = -k
    if _bits(max(abs(a.n), a.d)) * k > MAXBITS:
        return None
    return make(a.n ** k, a.d ** k)


# ---- evaluation namespace (exact mode) ----------------------------------------
def _back(v):
    """An integer D result of a decimal function becomes exact again, so
    that 1/log(1000) is 1/3."""
    if isinstance(v, D) and bcd.isint(v) and abs(v) < D("1e15"):
        return make(int(v))
    return v


def _wrap(f):
    def g(*a):
        a = [(lambda t, h=x: todec(h(t))) if callable(x) else todec(x) for x in a]
        return _back(f(*a))

    return g


# functions that do their own exact work below (or are constants)
_KEEP = ("pi", "e", "inf", "i")


def namespace(base):
    """Exact-mode copy of a fn.namespace(): every function accepts Q."""
    ns = {}
    for k, v in base.items():
        if k in _KEEP or not callable(v):
            ns[k] = v
        else:
            ns[k] = _wrap(v)
    dpw = base["pw"]
    dsqrt = base["sqrt"]
    dfact = base["fact"]
    dsigma = base["sigma"]
    dprod = base["prod"]

    def div(a, b):
        if b == 0:
            raise ZeroDivisionError
        a = exact(a)
        b = exact(b)
        if isinstance(a, Q) and isinstance(b, Q):
            return a / b
        return base["div"](todec(a), todec(b))

    def mixed(w, a, b):
        q = div(a, b)
        return w - q if w < 0 else w + q

    def pw(a, b):
        a = exact(a)
        b = exact(b)
        if isinstance(a, Q) and isinstance(b, Q):
            if a.n == 0 and b.n < 0:
                raise ZeroDivisionError
            r = power(a, b)
            if r is not None:
                return r
        return _back(dpw(todec(a), todec(b)))

    def sqrt(x):
        if isinstance(x, Q):
            r = sqrt_(x)
            if r is not None:
                return r
        return _back(dsqrt(todec(x)))

    def fact(n):
        if isint(n) and 0 <= n.n <= 69:
            r = 1
            for k in range(2, n.n + 1):
                r *= k
            return make(r)
        return dfact(todec(n))

    def abs_(x):
        return abs(x) if isinstance(x, Q) else _back(abs(todec(x)))

    def sign(x):
        if isinstance(x, Q):
            return Q((x.n > 0) - (x.n < 0))
        return _back(base["sign"](x))

    def floor(x):
        if isinstance(x, Q):
            return Q(x.n // x.d)
        return _back(base["floor"](x))

    def ceil(x):
        if isinstance(x, Q):
            return Q(-((-x.n) // x.d))
        return _back(base["ceil"](x))

    def int_(x):
        if isinstance(x, Q):
            return Q(int(x))
        return _back(base["int_"](x))

    def fpart(x):
        if isinstance(x, Q):
            return x - int(x)
        return base["fpart"](x)

    def mod(a, b):
        if isinstance(a, Q) and isinstance(b, Q):
            if b.n == 0:
                raise ValueError
            return a - b * Q((a.n * b.d) // (a.d * b.n))
        return _back(base["mod"](todec(a), todec(b)))

    def _loop(f, a, b, s, mul, dec_fn):
        a = exact(a)
        b = exact(b)
        if not (isint(a) and isint(b)):
            return dec_fn(lambda t: todec(f(t)), todec(a), todec(b))
        for k in range(a.n, b.n + 1):
            v = f(Q(k))
            s = s * v if mul else s + v
        return s

    def sigma(f, a, b):
        return _loop(f, a, b, Q(0), False, dsigma)

    def prod(f, a, b):
        return _loop(f, a, b, Q(1), True, dprod)

    def mn(*a):
        return min(a)

    def mx(*a):
        return max(a)

    ns["div"] = div
    ns["mixed"] = mixed
    ns["pw"] = pw
    ns["sqrt"] = sqrt
    ns["fact"] = fact
    ns["abs_"] = abs_
    ns["sign"] = sign
    ns["floor"] = floor
    ns["ceil"] = ceil
    ns["int_"] = int_
    ns["fpart"] = fpart
    ns["mod"] = mod
    ns["sigma"] = sigma
    ns["prod"] = prod
    ns["min_"] = mn
    ns["max_"] = mx
    return ns
