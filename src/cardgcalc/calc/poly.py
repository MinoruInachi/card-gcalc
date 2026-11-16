# Polynomial roots (degree 1..4) and exact forms for quadratics.
#
# Coefficients and roots are decimal (bcd.D, complex roots dec.DC).  For
# degree 3/4 approximate roots come from Durand-Kerner in binary floating
# point (internal only); they are then refined by Newton's method in decimal
# arithmetic and snapped to short decimals when that makes p(x) exactly 0.
import bcd
from bcd import D
from cardgcalc.calc import numfmt
from cardgcalc.calc import dec
from cardgcalc.calc.dec import DC, num, ZERO, ONE
from cardgcalc.calc.fn import clean

_E9 = D("1e-9")
_E12 = D("1e-12")
_E14 = D("1e-14")


def _horner(c, z):
    v = ZERO
    for a in c:
        v = v * z + a
    return v


def _fhorner(c, z):
    v = 0
    for a in c:
        v = v * z + a
    return v


def _snap(x):
    if abs(x) < _E14:
        return ZERO
    return clean(x, D("1e-10"))


def _tidy_root(z, real_coef=True):
    if isinstance(z, DC):
        mag = max(ONE, abs(z))
        re, im = z.real, z.imag
        if real_coef and abs(im) < _E9 * mag:
            return _snap(re)
        if im == 0:
            return _snap(re)
        if abs(re) < _E12 * mag:
            re = ZERO
        return DC(_snap(re), _snap(im))
    return _snap(z)


def _dpoly(c):
    n = len(c) - 1
    return [c[k] * (n - k) for k in range(n)]


def _isc(x):
    return isinstance(x, DC)


def _csqrt(d):
    if _isc(d) or d < 0:
        return dec.csqrt(d)
    return bcd.sqrt(d)


def _refine(m, z, mult):
    """Newton on the (mult-1)th derivative of p in decimal arithmetic."""
    dk = m
    for _ in range(mult - 1):
        dk = _dpoly(dk)
    dk1 = _dpoly(dk)
    for _ in range(12):
        d = _horner(dk1, z)
        if d == 0:
            break
        step = _horner(dk, z) / d
        nz = z - step
        if nz == z:
            break
        z = nz
    return z


def _short(m, z, mult):
    """Shorter decimal for z if it is an exact root (p(z) == 0)."""
    dk = m
    for _ in range(mult - 1):
        dk = _dpoly(dk)
    best = abs(_horner(dk, z))
    if best == 0:
        return z
    for sig in (13, 12, 11, 10):
        if _isc(z):
            c = DC(bcd.rsig(z.real, sig) if z.real != 0 else ZERO,
                   bcd.rsig(z.imag, sig) if z.imag != 0 else ZERO)
        else:
            c = bcd.rsig(z, sig)
        if _horner(dk, c) == 0:
            return c
    return z


def roots(coeffs):
    """Roots of a polynomial given highest-degree-first coefficients."""
    c = [num(x) for x in coeffs]
    while c and c[0] == 0:
        c.pop(0)
    n = len(c) - 1
    if n < 1:
        raise ValueError("Not a polynomial")
    real_coef = not any(_isc(x) for x in c)
    if n == 1:
        return [_tidy_root(-c[1] / c[0], real_coef)]
    if n == 2:
        a, b, cc = c
        if b == 0:
            s = _csqrt(-cc / a)
            return _sort([_tidy_root(z, real_coef) for z in (s, -s)])
        d = b * b - 4 * a * cc
        s = _csqrt(d)
        # numerically stable form
        if (b.real if _isc(b) else b) >= 0:
            q = -(b + s) / 2
        else:
            q = -(b - s) / 2
        if q == 0:
            r = [ZERO, ZERO]
        else:
            r = [q / a, cc / q]
        return _sort([_tidy_root(z, real_coef) for z in r])
    a0 = c[0]
    m = [x / a0 for x in c]
    mf = [dec.f(x) for x in m]
    groups = _approx(mf, n)
    real_coef = not any(_isc(x) for x in c)
    out = []
    cx = []
    for zf, mult in groups:
        if real_coef and abs(zf.imag) < 1e-6 * max(1.0, abs(zf)):
            z = num(zf.real)
        else:
            z = DC(num(zf.real), num(zf.imag))
        z = _refine(m, z, mult)
        z = _short(m, z, mult)
        z = _tidy_root(z, real_coef)
        for _ in range(mult):
            if _isc(z) and real_coef:
                cx.append(z)
            else:
                out.append(z)
    if real_coef:
        cx.sort(key=lambda z: (z.real, abs(z.imag)))
        if len(cx) % 2:
            k = min(range(len(cx)), key=lambda q: abs(cx[q].imag))
            out.append(_snap(cx.pop(k).real))
        for q in range(0, len(cx), 2):
            a, b = cx[q], cx[q + 1]
            re = _snap((a.real + b.real) / 2)
            im = _snap((abs(a.imag) + abs(b.imag)) / 2)
            out.append(DC(re, im))
            out.append(DC(re, -im))
    else:
        out += cx
    return _sort(out)


def _approx(m, n):
    """Durand-Kerner (float) -> [(root, multiplicity)]."""
    z = [(0.4 + 0.9j) ** k for k in range(n)]
    for _ in range(800):
        delta = 0.0
        for i in range(n):
            nm = _fhorner(m, z[i])
            den = 1
            for j in range(n):
                if i != j:
                    den *= z[i] - z[j]
            if den == 0:
                den = 1e-12
            dz = nm / den
            z[i] -= dz
            delta = max(delta, abs(dz))
        if delta < 1e-15:
            break
    # Newton polish
    dc = [m[k] * (n - k) for k in range(n)]
    pol = []
    for zi in z:
        for _ in range(5):
            d = _fhorner(dc, zi)
            if d == 0:
                break
            step = _fhorner(m, zi) / d
            zi -= step
            if abs(step) < 1e-16 * max(1.0, abs(zi)):
                break
        pol.append(complex(zi))
    # Merge clusters (multiple roots converge slowly and spread out).
    used = [False] * n
    out = []
    for i in range(n):
        if used[i]:
            continue
        grp = [i]
        for j in range(i + 1, n):
            if not used[j] and abs(pol[j] - pol[i]) < 2e-2 * max(1.0, abs(pol[i])):
                grp.append(j)
        mean = sum(pol[k] for k in grp) / len(grp)
        worst = max(abs(_fhorner(m, pol[k])) for k in grp)
        if len(grp) > 1 and abs(_fhorner(m, mean)) <= max(worst * 10, 1e-14):
            for k in grp:
                used[k] = True
            out.append((mean, len(grp)))
        else:
            used[i] = True
            out.append((pol[i], 1))
    return out


def _sort(rs):
    reals = sorted([r for r in rs if not _isc(r)])
    cplx = [r for r in rs if _isc(r)]
    cplx.sort(key=lambda z: (z.real, -z.imag))
    return reals + cplx


# ---- exact quadratic roots -------------------------------------------------
def _gcd(a, b):
    a = abs(a)
    b = abs(b)
    while b:
        a, b = b, a % b
    return a


def _frac(x):
    """number -> (num, den) or None."""
    if isinstance(x, (DC, complex)):
        return None
    if isinstance(x, int):
        return (x, 1)
    return numfmt.to_fraction(num(x), 10000, 1e-12)


def _fnorm(n, d):
    if d < 0:
        n, d = -n, -d
    g = _gcd(n, d) or 1
    return n // g, d // g


def _squarefree(n):
    a = 1
    b = n
    k = 2
    while k * k <= b:
        while b % (k * k) == 0:
            b //= k * k
            a *= k
        k += 1
    return a, b


def _fstr(n, d):
    return str(n) if d == 1 else "%d/%d" % (n, d)


def exact_quadratic(a, b, c):
    """Exact root strings [(value, str), (value, str)] or None."""
    fa, fb, fc = _frac(a), _frac(b), _frac(c)
    if not (fa and fb and fc) or fa[0] == 0:
        return None
    an, ad = fa
    bn, bd = fb
    cn, cd = fc
    # D = b² - 4ac = (bn²·ad·cd - 4·an·cn·bd²) / (bd²·ad·cd)
    dn = bn * bn * ad * cd - 4 * an * cn * bd * bd
    dd = bd * bd * ad * cd
    dn, dd = _fnorm(dn, dd)
    neg = dn < 0
    # √(dn/dd) = √(|dn|·dd)/dd = s√m / dd
    if dd > 10 ** 12 or abs(dn) > 10 ** 12:
        return None
    s, m = _squarefree(abs(dn) * dd)
    # R = -b/(2a) = -bn·ad / (2·bd·an);   K = s / (dd · 2a) = s·ad / (2·dd·an)
    rn, rd = _fnorm(-bn * ad, 2 * bd * an)
    kn, kd = _fnorm(s * ad, 2 * dd * an)
    kn = abs(kn)
    if m == 1 and not neg:
        r1 = _fnorm(rn * kd - kn * rd, rd * kd)
        r2 = _fnorm(rn * kd + kn * rd, rd * kd)
        return [(D(r1[0]) / r1[1], _fstr(*r1)), (D(r2[0]) / r2[1], _fstr(*r2))]
    L = rd * kd // _gcd(rd, kd)
    p = rn * (L // rd)
    k = kn * (L // kd)
    g = _gcd(_gcd(p, k), L) or 1
    p //= g
    k //= g
    L //= g
    if m == 1:
        irr = "i"
    else:
        irr = "√%d" % m + ("i" if neg else "")
    kstr = ("" if k == 1 else str(k)) + irr
    outs = []
    for sg in (-1, 1):
        if p == 0:
            num = ("-" if sg < 0 else "") + kstr
            s_ = num if L == 1 else "%s/%d" % (num, L)
        else:
            num = "%d%s%s" % (p, "-" if sg < 0 else "+", kstr)
            s_ = num if L == 1 else "(%s)/%d" % (num, L)
        rv = D(rn) / rd
        kv = D(kn) / kd * bcd.sqrt(m)
        val = DC(rv, sg * kv) if neg else rv + sg * kv
        outs.append((val, s_))
    return outs


def match_exact(numeric_roots, exact):
    """Pair exact strings with numeric roots (nearest value)."""
    out = []
    for z in numeric_roots:
        best = None
        bd = D("1e-6") * max(ONE, abs(z))
        for v, s in exact:
            d = abs(v - z)
            if d <= bd:
                best = s
                bd = d
        out.append(best)
    return out
