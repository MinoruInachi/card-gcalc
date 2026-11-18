# Two-dimensional drawing of calculator text with fractions.
#
# A fraction or a mixed number is kept in the (single-line) text with marker
# characters (see calc/frac.py):
#
#   FS num FM den FE          num over den
#   MS whole MM num FM den FE whole and num over den (mixed number)
#
# The parts may contain further fractions.  Fraction parts are drawn with the
# next smaller font, centred above and below a bar on the text's centre line.
from cardgcalc import gfx
from cardgcalc.calc.frac import FS, FM, FE, MS, MM, MARKS

_SMALLER = {20: "medium", 13: "normal", 10: "small", 8: "small"}


def has_marks(s):
    for c in MARKS:
        if c in s:
            return True
    return False


def sub(f):
    """The font used for fraction parts written in font f."""
    return gfx.font(_SMALLER.get(f.h, "small"))


def find(s, k):
    """For an opener (FS / MS) at s[k]: (separator positions, end position)."""
    depth = 0
    seps = []
    n = len(s)
    p = k + 1
    while p < n:
        c = s[p]
        if c == FS or c == MS:
            depth += 1
        elif c == FE:
            if depth == 0:
                return seps, p
            depth -= 1
        elif (c == FM or c == MM) and depth == 0:
            seps.append(p)
        p += 1
    return seps, n


def enclosing(s, cur):
    """Innermost template around position cur: (opener index, seps, end) or None."""
    depth = 0
    p = cur - 1
    while p >= 0:
        c = s[p]
        if c == FE:
            depth += 1
        elif c == FS or c == MS:
            if depth == 0:
                seps, end = find(s, p)
                if cur <= end:
                    return p, seps, end
            else:
                depth -= 1
        p -= 1
    return None


# ---- layout -----------------------------------------------------------------
def _frac_dims(s, a, m, e, f):
    fs = sub(f)
    wn, un, dn = measure(s, fs, a, m)
    wd, ud, dd = measure(s, fs, m + 1, e)
    return max(wn, wd) + 4, 1 + dn + un, 2 + ud + dd


def measure(s, f, i=0, j=None):
    """Size of s[i:j] in font f: (width, height above centre, below)."""
    if j is None:
        j = len(s)
    if i >= j:
        # empty slot: a placeholder box
        return f.w, f.h // 2, f.h - f.h // 2
    w = 0
    up = f.h // 2
    down = f.h - up
    k = i
    while k < j:
        c = s[k]
        if c == FS or c == MS:
            seps, e = find(s, k)
            if c == FS:
                if len(seps) != 1:
                    return w, up, down
                fw, fu, fd = _frac_dims(s, k + 1, seps[0], e, f)
            else:
                if len(seps) != 2:
                    return w, up, down
                ww, wu, wdn = measure(s, f, k + 1, seps[0])
                fw, fu, fd = _frac_dims(s, seps[0] + 1, seps[1], e, f)
                fw += ww + 1
                fu = max(fu, wu)
                fd = max(fd, wdn)
            w += fw
            up = max(up, fu)
            down = max(down, fd)
            k = e + 1
            continue
        if c not in MARKS:
            w += f.cw(c)
        k += 1
    return w, up, down


def draw(s, f, x, yc, fg, pos=None, x1=None, i=0, j=None):
    """Draw s[i:j] with its centre line at yc.  Returns the x after it.

    pos: optional dict filled with cursor positions {index: (x, top, h)}.
    x1: characters that would reach past x1 are not drawn."""
    if j is None:
        j = len(s)
    fb = gfx.fb()
    top = yc - f.h // 2
    if i >= j:
        if pos is not None:
            pos[i] = (x, top, f.h)
        if x1 is None or x + f.w <= x1:
            fb.rect(x, top + 1, f.w, f.h - 2, gfx.DIM)
        return x + f.w
    k = i
    while k < j:
        if pos is not None:
            pos[k] = (x, top, f.h)
        c = s[k]
        if c == FS or c == MS:
            seps, e = find(s, k)
            if c == FS and len(seps) == 1:
                x = _draw_frac(s, k + 1, seps[0], e, f, x, yc, fg, pos, x1)
            elif c == MS and len(seps) == 2:
                x = draw(s, f, x, yc, fg, pos, x1, k + 1, seps[0]) + 1
                x = _draw_frac(s, seps[0] + 1, seps[1], e, f, x, yc, fg, pos, x1)
            else:
                k += 1
                continue
            k = e + 1
            continue
        if c not in MARKS:
            cw = f.cw(c)
            if x1 is None or x + cw <= x1:
                f.text(c, x, top, fg)
            x += cw
        k += 1
    if pos is not None:
        pos[j] = (x, top, f.h)
    return x


def _draw_frac(s, a, m, e, f, x, yc, fg, pos, x1):
    fs = sub(f)
    wn, un, dn = measure(s, fs, a, m)
    wd, ud, dd = measure(s, fs, m + 1, e)
    w = max(wn, wd) + 4
    if x1 is None or x + w <= x1:
        gfx.fb().hline(x + 1, yc, w - 2, fg)
    draw(s, fs, x + (w - wn) // 2, yc - 1 - dn, fg, pos, x1, a, m)
    draw(s, fs, x + (w - wd) // 2, yc + 2 + ud, fg, pos, x1, m + 1, e)
    return x + w

