# Decimal (BCD) numbers for the calculator apps.
#
# Real numbers are bcd.D: 15 significant decimal digits, exponent -99..99,
# every operation rounded half-up (see firmware/cmodules/bcd/bcd.c).
# Complex numbers are DC, a pair of D.  Python scripts keep using float;
# only the calculator apps work with these types.
import bcd
from bcd import D

pi = bcd.pi
e = bcd.e
ZERO = D(0)
ONE = D(1)
TWO = D(2)
HALF = D("0.5")


class DC:
    """Complex number with decimal real and imaginary parts."""

    def __init__(self, re, im=ZERO):
        self.real = D(re)
        self.imag = D(im)

    # arithmetic --------------------------------------------------------
    def __add__(self, o):
        o = cx(o)
        if o is None:
            return NotImplemented
        return DC(self.real + o.real, self.imag + o.imag)

    def __radd__(self, o):
        return self.__add__(o)

    def __sub__(self, o):
        o = cx(o)
        if o is None:
            return NotImplemented
        return DC(self.real - o.real, self.imag - o.imag)

    def __rsub__(self, o):
        o = cx(o)
        if o is None:
            return NotImplemented
        return DC(o.real - self.real, o.imag - self.imag)

    def __mul__(self, o):
        o = cx(o)
        if o is None:
            return NotImplemented
        a, b, c, d = self.real, self.imag, o.real, o.imag
        if b == 0:
            return DC(a * c, a * d)
        if d == 0:
            return DC(a * c, b * c)
        return DC(a * c - b * d, a * d + b * c)

    def __rmul__(self, o):
        return self.__mul__(o)

    def __truediv__(self, o):
        o = cx(o)
        if o is None:
            return NotImplemented
        a, b, c, d = self.real, self.imag, o.real, o.imag
        if d == 0:
            if c == 0:
                raise ZeroDivisionError
            return DC(a / c, b / c)
        den = c * c + d * d
        return DC((a * c + b * d) / den, (b * c - a * d) / den)

    def __rtruediv__(self, o):
        o = cx(o)
        if o is None:
            return NotImplemented
        return o.__truediv__(self)

    def __pow__(self, o):
        return cpow(self, o)

    def __rpow__(self, o):
        return cpow(cx(o), self)

    def __neg__(self):
        return DC(-self.real, -self.imag)

    def __pos__(self):
        return self

    def __abs__(self):
        return cabs(self)

    def __eq__(self, o):
        o = cx(o)
        return o is not None and self.real == o.real and self.imag == o.imag

    def __ne__(self, o):
        return not self.__eq__(o)

    def __hash__(self):
        return hash(self.real) ^ hash(self.imag)

    def __repr__(self):
        return "(%s%s%sj)" % (self.real, "+" if self.imag >= 0 else "", self.imag)

    def conjugate(self):
        return DC(self.real, -self.imag)


def cx(v):
    """Value as DC (None if not a number)."""
    if isinstance(v, DC):
        return v
    if isinstance(v, D):
        return DC(v)
    if isinstance(v, (int, float)):
        return DC(D(v))
    if isinstance(v, complex):
        return DC(D(v.real), D(v.imag))
    return None


def num(v):
    """int / float / str / complex / D / DC -> D or DC."""
    if isinstance(v, (D, DC)):
        return v
    if isinstance(v, complex):
        return DC(D(v.real), D(v.imag))
    return D(v)


def isnum(v):
    return isinstance(v, (D, DC, int, float)) and not isinstance(v, bool)


def isreal(v):
    return isinstance(v, (D, int, float)) and not isinstance(v, bool)


def isint(v):
    if isinstance(v, int):
        return True
    return isinstance(v, D) and bcd.isint(v)


def f(v):
    """Python float (or complex) of a calculator value (for drawing)."""
    if isinstance(v, D):
        return bcd.tof(v)
    if isinstance(v, DC):
        return complex(bcd.tof(v.real), bcd.tof(v.imag))
    return float(v)


def simp(v, tol=None):
    """DC with a zero (or negligible) imaginary part -> D."""
    if isinstance(v, DC):
        if v.imag == 0:
            return v.real
        if tol is not None and abs(v.imag) <= tol * abs(v.real):
            return v.real
    return v


# ---- complex functions (radians) -------------------------------------------
def cabs(z):
    a = abs(z.real)
    b = abs(z.imag)
    if a == 0:
        return b
    if b == 0:
        return a
    if a < b:
        a, b = b, a
    r = b / a
    return a * bcd.sqrt(1 + r * r)


def carg(z):
    return bcd.atan2(z.imag, z.real)


def cexp(z):
    z = cx(z)
    m = bcd.exp(z.real)
    if z.imag == 0:
        return DC(m)
    return DC(m * bcd.cos(z.imag), m * bcd.sin(z.imag))


def cln(z):
    z = cx(z)
    if z.real == 0 and z.imag == 0:
        raise ValueError
    return DC(bcd.ln(cabs(z)), carg(z))


def csqrt(z):
    z = cx(z)
    a, b = z.real, z.imag
    if b == 0:
        if a >= 0:
            return DC(bcd.sqrt(a))
        return DC(ZERO, bcd.sqrt(-a))
    r = cabs(z)
    if a >= 0:
        t = bcd.sqrt((r + a) / 2)
        return DC(t, b / (2 * t))
    t = bcd.sqrt((r - a) / 2)
    return DC(abs(b) / (2 * t), t if b >= 0 else -t)


def cpow(z, w):
    """z ** w with z or w complex (principal value)."""
    z = cx(z)
    w = cx(w)
    if w.imag == 0 and bcd.isint(w.real) and abs(w.real) <= 1000000:
        n = int(w.real)
        if z.real == 0 and z.imag == 0:
            if n < 0:
                raise ZeroDivisionError
            return DC(ONE if n == 0 else ZERO)
        r = DC(ONE)
        b = z
        k = abs(n)
        while k:
            if k & 1:
                r = r * b
            k >>= 1
            if k:
                b = b * b
        return DC(ONE) / r if n < 0 else r
    if z.real == 0 and z.imag == 0:
        if w.real > 0:
            return DC(ZERO)
        raise ZeroDivisionError
    if w.imag == 0 and z.imag == 0 and z.real > 0:
        return DC(z.real ** w.real)
    if w.imag == 0 and (w.real * 2) == bcd.trunc(w.real * 2) and abs(w.real) <= 1000000:
        # half-integer powers through the square root
        return cpow(csqrt(z), w.real * 2)
    if z.imag == 0 and z.real == e:
        return cexp(w)
    return cexp(w * cln(z))


def csin(z):
    z = cx(z)
    a, b = z.real, z.imag
    return DC(bcd.sin(a) * bcd.cosh(b), bcd.cos(a) * bcd.sinh(b))


def ccos(z):
    z = cx(z)
    a, b = z.real, z.imag
    return DC(bcd.cos(a) * bcd.cosh(b), -(bcd.sin(a) * bcd.sinh(b)))


def ctan(z):
    return csin(z) / ccos(z)


_I = DC(ZERO, ONE)


def casin(z):
    # -i ln(iz + sqrt(1 - z^2))
    z = cx(z)
    return -_I * cln(_I * z + csqrt(1 - z * z))


def cacos(z):
    return DC(pi / 2) - casin(z)


# ---- JSON ------------------------------------------------------------------
def to_json(v):
    """Replace D / DC (recursively) by JSON-safe markers."""
    if isinstance(v, D):
        return {"$d": str(v)}
    if isinstance(v, DC):
        return {"$c": [str(v.real), str(v.imag)]}
    if isinstance(v, list):
        return [to_json(x) for x in v]
    if isinstance(v, tuple):
        return [to_json(x) for x in v]
    if isinstance(v, dict):
        return {k: to_json(x) for k, x in v.items()}
    if isinstance(v, complex):
        return {"$c": [str(D(v.real)), str(D(v.imag))]}
    return v


def from_json(v):
    if isinstance(v, dict):
        if "$d" in v and len(v) == 1:
            return D(v["$d"])
        if "$c" in v and len(v) == 1:
            return simp(DC(D(v["$c"][0]), D(v["$c"][1])))
        return {k: from_json(x) for k, x in v.items()}
    if isinstance(v, list):
        return [from_json(x) for x in v]
    if isinstance(v, float):
        return D(v)  # data saved before the decimal number type
    return v
