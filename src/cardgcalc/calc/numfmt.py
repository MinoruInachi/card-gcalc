# Number formatting for the calculator display.
#
# Values are decimal (bcd.D, 15 significant digits) and are formatted from
# their decimal digits directly, rounded half-up to the displayed digits.
import bcd
from bcd import D
from cardgcalc.calc import dec
from cardgcalc.calc.dec import DC

SIG = 10  # significant digits in Norm mode


def _digits(x):
    """(neg, 15-digit string, exponent of the leading digit) of a D."""
    neg, c, e = bcd.parts(x)
    s = "%015d" % c if c else "0" * 15
    return neg, s, e + 14


def _plain(neg, s, X, ndec):
    """Decimal notation of digits s (leading digit at 10^X), ndec decimals."""
    if X >= 0:
        ip = s[: X + 1] if X + 1 <= len(s) else s + "0" * (X + 1 - len(s))
        fp = s[X + 1 :]
    else:
        ip = "0"
        fp = "0" * (-X - 1) + s
    fp = (fp + "0" * ndec)[:ndec]
    out = ip + ("." + fp if ndec > 0 else "")
    if neg and out.strip("0.") != "":
        out = "-" + out
    return out


def _strip(m):
    if "." in m:
        m = m.rstrip("0").rstrip(".")
    return m


def fmt_real(x, mode="norm", digits=SIG):
    """Format a real number.

    mode: 'norm' (up to `digits` significant digits, sci for very large/small),
          'fix'  (`digits` decimals), 'sci' (`digits` significant digits),
          'eng'  (engineering notation)."""
    if isinstance(x, bool):
        x = int(x)
    if isinstance(x, float):
        if x != x:
            return "NaN"
        if x in (float("inf"), float("-inf")):
            return "∞" if x > 0 else "-∞"
    if not isinstance(x, D):
        x = D(x)
    if mode == "fix":
        r = bcd.rnd(x, digits)
        if r != 0 and abs(r) >= D("1e15"):
            return _sci(x, 10, False, strip=True)
        neg, s, X = _digits(r)
        if r == 0:
            return _plain(False, s, 0, digits) if digits > 0 else "0"
        return _plain(neg, s, X, digits)
    if mode in ("sci", "eng"):
        return _sci(x, max(1, digits), mode == "eng")
    if x == 0:
        return "0"
    r = bcd.rsig(x, SIG)
    ax = abs(r)
    if ax >= D("1e10") or ax < D("1e-9"):
        return _sci(x, SIG, False, strip=True)
    neg, s, X = _digits(r)
    return _strip(_plain(neg, s, X, max(0, SIG - 1 - X)))


def _sci(x, sig, eng=False, strip=False):
    if not isinstance(x, D):
        x = D(x)
    if x == 0:
        neg, s, X = False, "0" * 15, 0
    else:
        neg, s, X = _digits(bcd.rsig(x, sig))
    k = X % 3 if eng else 0
    E = X - k
    dec_ = max(0, sig - 1 - k)
    ms = _plain(neg, s, k, dec_)
    if strip:
        ms = _strip(ms)
    return "%sE%d" % (ms, E)


def fmt(v, mode="norm", digits=SIG):
    if isinstance(v, complex):
        v = dec.cx(v)
    if isinstance(v, DC):
        re = v.real
        im = v.imag
        if abs(re) < D("1e-14") * abs(im):
            re = D(0)
        if abs(im) < D("1e-14") * abs(re):
            return fmt_real(re, mode, digits)
        if re == 0:
            s = ""
        else:
            s = fmt_real(re, mode, digits)
        si = fmt_real(abs(im), mode, digits)
        if si == "1":
            si = ""
        if s:
            return s + ("-" if im < 0 else "+") + si + "i"
        return ("-" if im < 0 else "") + si + "i"
    if isinstance(v, (list, tuple)):
        return "{" + ",".join(fmt(a, mode, digits) for a in v) + "}"
    if isinstance(v, (D, int, float)):
        return fmt_real(v, mode, digits)
    return str(v)


# ---- exact forms (Exact) -------------------------------------------------
def _ratio(x):
    """Exact value of a decimal x as (P, Q) integers."""
    neg, c, e = bcd.parts(x)
    if e >= 0:
        P, Q = c * 10 ** e, 1
    else:
        P, Q = c, 10 ** (-e)
    g = _gcd(P, Q)
    P //= g
    Q //= g
    return (-P if neg else P), Q


def to_fraction(x, maxden=10000, tol=1e-12):
    """Best rational approximation p/q (q <= maxden) of x within the
    relative tolerance tol, or None.  Exact for terminating decimals."""
    if isinstance(x, int):
        return x, 1
    if isinstance(x, float):
        x = D(x)
    if not isinstance(x, D) or abs(x) > D("1e12"):
        return None
    P, Q = _ratio(x)
    if Q <= maxden:
        return P, Q
    sign = -1 if P < 0 else 1
    P = abs(P)
    # tolerance as an integer ratio 1/T
    T = 1
    while T * tol < 1:
        T *= 10
    big = max(P, Q)
    h0, h1 = 0, 1
    k0, k1 = 1, 0
    p, q = P, Q
    for _ in range(60):
        a = p // q
        h0, h1 = h1, a * h1 + h0
        k0, k1 = k1, a * k1 + k0
        if k1 > maxden:
            return None
        # |h1/k1 - P/Q| <= tol * max(1, P/Q)
        if abs(h1 * Q - k1 * P) * T <= k1 * big:
            return sign * h1, k1
        p, q = q, p - a * q
        if q == 0:
            break
    return None


def _frac_str(p, q, suffix=""):
    if q == 1:
        if suffix:
            if p == 1:
                return suffix
            if p == -1:
                return "-" + suffix
        return "%d%s" % (p, suffix)
    if suffix:
        if p == 1:
            return "%s/%d" % (suffix, q)
        if p == -1:
            return "-%s/%d" % (suffix, q)
    return "%d%s/%d" % (p, suffix, q)


def _squarefree(n):
    """n = a^2 * b with b squarefree -> (a, b)."""
    a = 1
    b = n
    k = 2
    while k * k <= b:
        while b % (k * k) == 0:
            b //= k * k
            a *= k
        k += 1
    return a, b


def exact(x):
    """Try to express x exactly: fraction, multiple of π, or (p/q)√n.
    Returns a string or None."""
    if isinstance(x, (DC, complex)):
        return None
    if isinstance(x, int):
        return None
    if isinstance(x, float):
        x = D(x)
    if not isinstance(x, D) or bcd.isint(x):
        return None
    fr = to_fraction(x, 10000)
    if fr and fr[1] != 1:
        return _frac_str(fr[0], fr[1])
    if fr:
        return None
    fr = to_fraction(x / bcd.pi, 1000, 1e-11)
    if fr and fr[0] != 0:
        return _frac_str(fr[0], fr[1], "π")
    # (p/q)·√n : x² rational
    x2 = to_fraction(x * x, 100000, 1e-11)
    if x2 and x2[0] > 0:
        p2, q2 = x2
        # x = sqrt(p2/q2) = sqrt(p2*q2)/q2
        a, b = _squarefree(p2 * q2)
        if b > 1 and b < 100000:
            num, den = a, q2
            g = _gcd(num, den)
            num //= g
            den //= g
            s = "-" if x < 0 else ""
            core = "√%d" % b
            if num != 1:
                core = "%d%s" % (num, core)
            if den != 1:
                core = "%s/%d" % (core, den)
            return s + core
    return None


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a
