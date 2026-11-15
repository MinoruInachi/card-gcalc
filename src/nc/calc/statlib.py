# Statistics: 1/2-variable summaries, regressions, probability distributions.
#
# All values are decimal (bcd.D, 15 significant digits): sums of decimal data
# are exact and every statistic is rounded half-up to 15 digits.  Only the
# normal distribution's cdf / inverse and the log-gamma fallback of very large
# binomial / Poisson terms use binary floating point (rounded to 15 digits).
import math
import bcd
from bcd import D
from nc.calc import dec
from nc.calc.dec import num, ZERO, ONE

_HALF = D("0.5")


class StatError(Exception):
    pass


def _check(xs):
    if not xs:
        raise StatError("No data")


def _sum(it):
    s = ZERO
    for v in it:
        s = s + v
    return s


def _sqrt(v):
    return bcd.sqrt(v) if v > 0 else ZERO


def _pairs(xs, fs):
    if fs is None:
        return [(num(x), ONE) for x in xs]
    if len(fs) < len(xs):
        raise StatError("Dimension error")
    out = []
    for x, f in zip(xs, fs):
        f = num(f)
        if f < 0:
            raise StatError("Frequency < 0")
        if f:
            out.append((num(x), f))
    return out


def one_var(xs, fs=None):
    """Summary statistics.  Returns a list of (label, value)."""
    _check(xs)
    pr = _pairs(xs, fs)
    n = _sum(f for _, f in pr)
    if n == 0:
        raise StatError("No data")
    sx = _sum(x * f for x, f in pr)
    sx2 = _sum(x * x * f for x, f in pr)
    mean = sx / n
    var = _sum(f * (x - mean) * (x - mean) for x, f in pr) / n
    sigma = _sqrt(var)
    s = _sqrt(var * n / (n - 1)) if n > 1 else None
    out = [("n", n), ("mean", mean), ("Σx", sx), ("Σx²", sx2), ("σx", sigma), ("sx", s)]
    srt = sorted(pr)
    out.append(("min", srt[0][0]))
    intf = all(bcd.isint(f) for _, f in pr)
    if intf:
        q1, med, q3 = quartiles(srt, int(n))
        out += [("Q1", q1), ("median", med), ("Q3", q3)]
    out.append(("max", srt[-1][0]))
    if intf:
        out.append(("IQR", q3 - q1))
    out.append(("range", srt[-1][0] - srt[0][0]))
    # mode
    cnt = {}
    for x, f in pr:
        cnt[x] = cnt.get(x, ZERO) + f
    mx = max(cnt.values())
    modes = sorted(k for k, v in cnt.items() if v == mx)
    if len(modes) < len(cnt) or len(cnt) == 1:
        for i, m in enumerate(modes[:3]):
            out.append(("mode" if i == 0 else "", m))
    return out


def _value_at(srt, pos):
    acc = 0
    for x, f in srt:
        acc += int(f)
        if pos < acc:
            return x
    return srt[-1][0]


def _median_range(srt, start, count):
    if count <= 0:
        return None
    if count % 2:
        return _value_at(srt, start + count // 2)
    return (_value_at(srt, start + count // 2 - 1) + _value_at(srt, start + count // 2)) / 2


def quartiles(srt, n):
    """(Q1, median, Q3) using the halves excluding the median."""
    med = _median_range(srt, 0, n)
    h = n // 2
    if n == 1:
        return srt[0][0], med, srt[0][0]
    q1 = _median_range(srt, 0, h)
    q3 = _median_range(srt, n - h, h)
    return q1, med, q3


def box_stats(xs, fs=None):
    pr = sorted(_pairs(xs, fs))
    if not pr:
        raise StatError("No data")
    n = int(_sum(f for _, f in pr))
    q1, med, q3 = quartiles(pr, n)
    return pr[0][0], q1, med, q3, pr[-1][0]


def two_var(xs, ys):
    n = min(len(xs), len(ys))
    if n == 0:
        raise StatError("No data")
    xs = [num(v) for v in xs[:n]]
    ys = [num(v) for v in ys[:n]]
    N = D(n)
    sx = _sum(xs)
    sy = _sum(ys)
    sx2 = _sum(x * x for x in xs)
    sy2 = _sum(y * y for y in ys)
    sxy = _sum(x * y for x, y in zip(xs, ys))
    mx = sx / N
    my = sy / N
    sxx = _sum((x - mx) * (x - mx) for x in xs)
    syy = _sum((y - my) * (y - my) for y in ys)
    out = [("n", N), ("mean x", mx), ("mean y", my), ("Σx", sx), ("Σy", sy), ("Σx²", sx2), ("Σy²", sy2),
           ("Σxy", sxy), ("σx", _sqrt(sxx / N)), ("σy", _sqrt(syy / N))]
    if n > 1:
        out += [("sx", _sqrt(sxx / (N - 1))), ("sy", _sqrt(syy / (N - 1)))]
    r = _pearson(xs, ys)
    if r is not None:
        out.append(("r", r))
    return out


def _pearson(xs, ys):
    n = len(xs)
    mx = _sum(xs) / n
    my = _sum(ys) / n
    sxx = _sum((x - mx) * (x - mx) for x in xs)
    syy = _sum((y - my) * (y - my) for y in ys)
    sxy = _sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        return None
    r = sxy / bcd.sqrt(sxx * syy)
    # rounding can push a perfect fit just past +-1
    if r > 1:
        return ONE
    if r < -1:
        return -ONE
    return r


def _linfit(xs, ys):
    n = len(xs)
    if n < 2:
        raise StatError("Need ≥2 points")
    mx = _sum(xs) / n
    my = _sum(ys) / n
    sxx = _sum((x - mx) * (x - mx) for x in xs)
    if sxx == 0:
        raise StatError("Math error")
    sxy = _sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    a = sxy / sxx
    b = my - a * mx
    a, b = _tidy([(a, 1), (b, 0)], xs, ys)
    return a, b, _pearson(xs, ys)


def _solve(A, b):
    """Gaussian elimination with partial pivoting (decimal).  None if singular."""
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if M[p][c] == 0:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[r][c] != 0:
                k = M[r][c] / M[c][c]
                for j in range(c, n + 1):
                    M[r][j] = M[r][j] - k * M[c][j]
    return [M[i][n] / M[i][i] for i in range(n)]


def _tidy(coefs, xs, ys):
    """Remove rounding noise from polynomial coefficients [(c, power), ...]:
    a term contributing less than 1e-12 of the data scale becomes 0 and a
    value within 1e-12 (relative) of an integer becomes that integer."""
    X = max(abs(x) for x in xs)
    if X < 1:
        X = ONE
    scale = max(abs(y) for y in ys)
    for c, k in coefs:
        t = abs(c) * X ** k
        if t > scale:
            scale = t
    eps = D("1e-12")
    out = []
    for c, k in coefs:
        if abs(c) * X ** k < eps * scale:
            c = ZERO
        else:
            r = bcd.rnd(c)
            if r != c and abs(c - r) < eps * max(ONE, abs(c)):
                c = r
        out.append(c)
    return out


REGRESSIONS = (
    ("lin", "Linear  y=ax+b"),
    ("quad", "Quadratic  y=ax²+bx+c"),
    ("exp", "Exponential  y=a·e^(bx)"),
    ("log", "Logarithmic  y=a+b·ln(x)"),
    ("pow", "Power  y=a·x^b"),
)


def _r2(xs, ys, f):
    my = _sum(ys) / len(ys)
    sst = _sum((y - my) * (y - my) for y in ys)
    sse = ZERO
    for x, y in zip(xs, ys):
        d = y - f(x)
        sse = sse + d * d
    if sst == 0:
        return None
    return 1 - sse / sst


def _es(v):
    """Number for an expression string (exponent as E, parsed by expr)."""
    return str(v).replace("e", "E")


def regression(kind, xs, ys):
    """Returns dict: form, coef [(name, value)], r, r2, f (callable), expr (str)."""
    n = min(len(xs), len(ys))
    xs = [num(v) for v in xs[:n]]
    ys = [num(v) for v in ys[:n]]
    if n < 2:
        raise StatError("Need ≥2 points")
    r = None
    if kind == "lin":
        a, b, r = _linfit(xs, ys)
        coef = [("a", a), ("b", b)]
        f = lambda x: a * x + b
        expr = "%s*x+%s" % (_es(a), _es(b))
        form = "y=ax+b"
    elif kind == "quad":
        if n < 3:
            raise StatError("Need ≥3 points")
        s = [_sum(x ** k for x in xs) for k in range(5)]
        t = [_sum(y * x ** k for x, y in zip(xs, ys)) for k in range(3)]
        A = [[s[4], s[3], s[2]], [s[3], s[2], s[1]], [s[2], s[1], s[0]]]
        sol = _solve(A, [t[2], t[1], t[0]])
        if sol is None:
            raise StatError("Math error")
        a, b, c = _tidy([(sol[0], 2), (sol[1], 1), (sol[2], 0)], xs, ys)
        coef = [("a", a), ("b", b), ("c", c)]
        f = lambda x: (a * x + b) * x + c
        expr = "%s*x^2+%s*x+%s" % (_es(a), _es(b), _es(c))
        form = "y=ax²+bx+c"
    elif kind == "exp":
        if any(y <= 0 for y in ys):
            raise StatError("Needs y>0")
        bb, la, r = _linfit(xs, [bcd.ln(y) for y in ys])
        a = bcd.exp(la)
        b = bb
        coef = [("a", a), ("b", b)]
        f = lambda x: a * bcd.exp(b * x)
        expr = "%s*e^(%s*x)" % (_es(a), _es(b))
        form = "y=a·e^(bx)"
    elif kind == "log":
        if any(x <= 0 for x in xs):
            raise StatError("Needs x>0")
        b, a, r = _linfit([bcd.ln(x) for x in xs], ys)
        coef = [("a", a), ("b", b)]
        f = lambda x: a + b * bcd.ln(x)
        expr = "%s+%s*ln(x)" % (_es(a), _es(b))
        form = "y=a+b·ln(x)"
    elif kind == "pow":
        if any(x <= 0 for x in xs) or any(y <= 0 for y in ys):
            raise StatError("Needs x>0, y>0")
        b, la, r = _linfit([bcd.ln(x) for x in xs], [bcd.ln(y) for y in ys])
        a = bcd.exp(la)
        coef = [("a", a), ("b", b)]
        f = lambda x: a * num(x) ** b
        expr = "%s*x^%s" % (_es(a), _es(b))
        form = "y=a·x^b"
    else:
        raise StatError("Unknown regression")
    r2 = _r2(xs, ys, f)
    return {"form": form, "coef": coef, "r": r, "r2": r2, "f": f, "expr": expr.replace("+-", "-")}


# ---- distributions ---------------------------------------------------------
def _flt(v):
    return v if isinstance(v, float) else dec.f(v)


def _d(v):
    """float result -> D (15 digits)."""
    if v != v or v in (math.inf, -math.inf):
        raise StatError("Math error")
    return D(v)


def norm_pdf(x, mu=0, sigma=1):
    x, mu, sigma = num(x), num(mu), num(sigma)
    if sigma <= 0:
        raise StatError("σ must be >0")
    z = (x - mu) / sigma
    return bcd.exp(-z * z / 2) / (sigma * bcd.sqrt(2 * bcd.pi))


def _phi(z):
    """Standard normal cdf of a float."""
    return 0.5 * math.erfc(-z / math.sqrt(2))


def norm_cdf(lo, hi, mu=0, sigma=1):
    mu, sigma = num(mu), num(sigma)
    if sigma <= 0:
        raise StatError("σ must be >0")
    a = ZERO if lo == -math.inf else _d(_phi(_flt((num(lo) - mu) / sigma)))
    b = ONE if hi == math.inf else _d(_phi(_flt((num(hi) - mu) / sigma)))
    return b - a


def inv_norm(p, mu=0, sigma=1, tail="left"):
    """x such that P(X<x)=p (left), P(X>x)=p (right) or P(-|x|<X<|x|)=p (center)."""
    p, mu, sigma = num(p), num(mu), num(sigma)
    if not 0 < p < 1:
        raise StatError("0<area<1")
    if tail == "right":
        p = 1 - p
    elif tail == "center":
        p = _HALF + p / 2
    pf = dec.f(p)
    # bisection on the standard normal
    lo, hi = -40.0, 40.0
    for _ in range(200):
        m = (lo + hi) / 2
        if _phi(m) < pf:
            lo = m
        else:
            hi = m
    z = _d((lo + hi) / 2)
    if tail == "center":
        return mu - z * sigma, mu + z * sigma
    return mu + z * sigma


def _comb(n, k):
    k = min(k, n - k)
    out = 1
    for j in range(k):
        out = out * (n - j) // (j + 1)
    return out


def binom_pdf(x, n, p):
    x, n, p = num(x), num(n), num(p)
    if not (0 <= p <= 1) or n < 0 or not bcd.isint(n):
        raise StatError("Argument error")
    n = int(n)
    if not bcd.isint(x) or x < 0 or x > n:
        return ZERO
    x = int(x)
    if p == 0:
        return ONE if x == 0 else ZERO
    if p == 1:
        return ONE if x == n else ZERO
    try:
        return D(_comb(n, x)) * p ** x * (1 - p) ** (n - x)
    except OverflowError:
        pf = dec.f(p)
        lc = math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1)
        return _d(math.exp(lc + x * math.log(pf) + (n - x) * math.log(1 - pf)))


def binom_cdf(x, n, p):
    x = num(x)
    if x < 0:
        return ZERO
    x = min(int(bcd.floor(x)), int(num(n)))
    return min(ONE, _sum(binom_pdf(k, n, p) for k in range(x + 1)))


def poisson_pdf(x, lam):
    x, lam = num(x), num(lam)
    if lam <= 0:
        raise StatError("λ must be >0")
    if not bcd.isint(x) or x < 0:
        return ZERO
    x = int(x)
    try:
        if x > 69:
            raise OverflowError
        return bcd.exp(-lam) * lam ** x / D(math.factorial(x))
    except OverflowError:
        lf = dec.f(lam)
        return _d(math.exp(-lf + x * math.log(lf) - math.lgamma(x + 1)))


def poisson_cdf(x, lam):
    x = num(x)
    if x < 0:
        return ZERO
    return min(ONE, _sum(poisson_pdf(k, lam) for k in range(int(bcd.floor(x)) + 1)))
