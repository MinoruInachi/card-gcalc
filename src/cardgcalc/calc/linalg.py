# Small dense linear algebra on lists of lists (decimal entries: bcd.D, or
# dec.DC for complex values).  Integer matrices get exact determinants
# (Bareiss elimination); other results are rounded to 15 digits per step.
import bcd
from cardgcalc.calc.dec import DC, num, ZERO, ONE
from cardgcalc.calc.fn import clean

_TINY = bcd.D("1e-13")
_EPS = bcd.D("1e-12")


class MatrixError(Exception):
    pass


def dims(a):
    return len(a), (len(a[0]) if a else 0)


def zeros(r, c):
    return [[ZERO] * c for _ in range(r)]


def identity(n):
    m = zeros(n, n)
    for i in range(n):
        m[i][i] = ONE
    return m


def copy(a):
    return [row[:] for row in a]


def _num(a):
    return [[num(x) for x in row] for row in a]


def _tidy_r(x):
    if abs(x) < _TINY:
        return ZERO
    return clean(x, _TINY)


def _tidy(x):
    x = num(x)
    if isinstance(x, DC):
        re, im = x.real, x.imag
        if abs(im) < _TINY * max(ONE, abs(re)):
            return _tidy_r(re)
        if abs(re) < _TINY * abs(im):
            re = ZERO
        return DC(_tidy_r(re), _tidy_r(im))
    return _tidy_r(x)


def tidy(a):
    return [[_tidy(x) for x in row] for row in a]


def _same(a, b):
    if dims(a) != dims(b):
        raise MatrixError("Dimension error")


def add(a, b):
    _same(a, b)
    return [[num(x) + num(y) for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def sub(a, b):
    _same(a, b)
    return [[num(x) - num(y) for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def scale(a, k):
    k = num(k)
    return [[k * num(x) for x in row] for row in a]


def mul(a, b):
    ra, ca = dims(a)
    rb, cb = dims(b)
    if ca != rb:
        raise MatrixError("Dimension error")
    a = _num(a)
    b = _num(b)
    out = zeros(ra, cb)
    for i in range(ra):
        ai = a[i]
        oi = out[i]
        for j in range(cb):
            s = ZERO
            for k in range(ca):
                s = s + ai[k] * b[k][j]
            oi[j] = s
    return tidy(out)


def transpose(a):
    r, c = dims(a)
    return [[num(a[i][j]) for i in range(r)] for j in range(c)]


def _norm(a):
    m = ZERO
    for row in a:
        for x in row:
            v = abs(x)
            if v > m:
                m = v
    return m


def _is_int_matrix(m):
    for row in m:
        for x in row:
            if isinstance(x, DC) or not bcd.isint(x):
                return False
    return True


def _int_rows(m):
    """Real non-integer matrix -> (row-scaled integer matrix, total power of
    ten) when every scaled entry stays below 1e15, else None."""
    if _is_int_matrix(m):
        return None
    out = []
    k = 0
    for row in m:
        s = 0
        for x in row:
            if isinstance(x, DC):
                return None
            neg, c, e = bcd.parts(x)
            if c:
                while c % 10 == 0:
                    c //= 10
                    e += 1
                if -e > s:
                    s = -e
        p = bcd.pow10(s)
        nr = [x * p for x in row]
        for x in nr:
            if abs(x) >= _BIG or not bcd.isint(x):
                return None
        out.append(nr)
        k += s
    return out, k


_BIG = bcd.D("1e15")


def det(a):
    r, c = dims(a)
    if r != c or r == 0:
        raise MatrixError("Dimension error")
    m = _num(a)
    n = r
    scale = _int_rows(m)
    if scale is not None:
        # decimal rows scaled to integers (exact), det scaled back
        m, k = scale
        d = det(m)
        return _tidy(d / bcd.pow10(k)) if k else d
    if _is_int_matrix(m):
        # Bareiss: every division is exact for integer matrices
        sign = 1
        prev = ONE
        for k in range(n - 1):
            if m[k][k] == 0:
                for i in range(k + 1, n):
                    if m[i][k] != 0:
                        m[k], m[i] = m[i], m[k]
                        sign = -sign
                        break
                else:
                    return ZERO
            for i in range(k + 1, n):
                for j in range(k + 1, n):
                    m[i][j] = (m[i][j] * m[k][k] - m[i][k] * m[k][j]) / prev
            prev = m[k][k]
        d = m[n - 1][n - 1]
        return _tidy(-d if sign < 0 else d)
    d = ONE
    for col in range(n):
        piv = max(range(col, n), key=lambda i: abs(m[i][col]))
        if m[piv][col] == 0:
            return ZERO
        if piv != col:
            m[col], m[piv] = m[piv], m[col]
            d = -d
        p = m[col][col]
        d = d * p
        for i in range(col + 1, n):
            f = m[i][col] / p
            if f != 0:
                mi = m[i]
                mc = m[col]
                for j in range(col, n):
                    mi[j] = mi[j] - f * mc[j]
    return _tidy(d)


def rref(a):
    """Reduced row echelon form.  Returns (matrix, rank, pivot_columns)."""
    m = _num(a)
    r, c = dims(m)
    eps = _EPS * max(ONE, _norm(m))
    row = 0
    pivots = []
    for col in range(c):
        if row >= r:
            break
        piv = max(range(row, r), key=lambda i: abs(m[i][col]))
        if abs(m[piv][col]) <= eps:
            for i in range(row, r):
                m[i][col] = ZERO
            continue
        m[row], m[piv] = m[piv], m[row]
        p = m[row][col]
        m[row] = [x / p for x in m[row]]
        m[row][col] = ONE
        for i in range(r):
            if i != row:
                f = m[i][col]
                if f != 0:
                    mr = m[row]
                    m[i] = [x - f * y for x, y in zip(m[i], mr)]
                    m[i][col] = ZERO
        pivots.append(col)
        row += 1
    return tidy(m), row, pivots


def rank(a):
    return rref(a)[1]


def inverse(a):
    r, c = dims(a)
    if r != c:
        raise MatrixError("Dimension error")
    idm = identity(r)
    aug = [list(a[i]) + idm[i] for i in range(r)]
    m, rk, piv = rref(aug)
    if piv[:r] != list(range(r)):
        raise MatrixError("Singular matrix")
    return tidy([row[r:] for row in m])


def power(a, n):
    r, c = dims(a)
    if r != c:
        raise MatrixError("Dimension error")
    n = num(n)
    if isinstance(n, DC) or not bcd.isint(n):
        raise MatrixError("Argument error")
    n = int(n)
    if n < 0:
        a = inverse(a)
        n = -n
    out = identity(r)
    base = _num(a)
    while n:
        if n & 1:
            out = mul(out, base)
        n >>= 1
        if n:
            base = mul(base, base)
    return out


def solve(a, b):
    """Solve A x = b (b: list of numbers).
    Returns ('unique', x) | ('none', None) | ('inf', rref_augmented)."""
    r, c = dims(a)
    if len(b) != r:
        raise MatrixError("Dimension error")
    aug = [list(a[i]) + [b[i]] for i in range(r)]
    m, rk, piv = rref(aug)
    if c in piv:
        return "none", None
    if rk < c:
        return "inf", m
    x = [ZERO] * c
    for i, p in enumerate(piv):
        x[p] = m[i][c]
    return "unique", [_tidy(v) for v in x]
