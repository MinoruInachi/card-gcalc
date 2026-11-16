# Minimal matplotlib.pyplot for card-gcalc.
#   plot(x, y, color), plot(y), scatter(x, y), bar(x, h, width), hist(data, bins),
#   text(x, y, s), arrow(x, y, dx, dy), axis([xmin,xmax,ymin,ymax] | 'off' | 'on'),
#   grid(True/False), title(s), xlabel/ylabel (ignored), show(), clf()
# Data may be lists, tuples, ranges or ulab ndarrays (1-D, or 2-D for plot:
# each column is drawn as a separate line, as in matplotlib).
import math
from cardgcalc import hal, gfx
from cardgcalc import runner as _r

_COLS = {
    "b": (31, 119, 180), "blue": (31, 119, 180), "r": (220, 40, 40), "red": (220, 40, 40),
    "g": (40, 160, 40), "green": (40, 160, 40), "k": (0, 0, 0), "black": (0, 0, 0),
    "y": (220, 190, 0), "yellow": (220, 190, 0), "c": (0, 180, 200), "cyan": (0, 180, 200),
    "m": (200, 0, 200), "magenta": (200, 0, 200), "orange": (255, 127, 14), "w": (255, 255, 255),
    "white": (255, 255, 255), "gray": (128, 128, 128), "grey": (128, 128, 128), "purple": (148, 103, 189),
}
_CYCLE = ((31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40), (148, 103, 189), (140, 86, 75))

_items = []
_lims = None
_axis_on = True
_grid = False
_title = None
_ci = [0]


def _color(c):
    if c is None:
        c = _CYCLE[_ci[0] % len(_CYCLE)]
        _ci[0] += 1
    if isinstance(c, str):
        cl = c.lower()
        if cl in _COLS:
            c = _COLS[cl]
        else:
            # format strings like "r-", "bo", "--"
            c = None
            for ch in cl:
                if ch in _COLS:
                    c = _COLS[ch]
                    break
            if c is None:
                c = _CYCLE[_ci[0] % len(_CYCLE)]
                _ci[0] += 1
    if isinstance(c, int):
        return c
    r, g, b = int(c[0]), int(c[1]), int(c[2])
    if r == g == b == 0:
        b = 8  # pure black is the transparent key of gfx text blits
    return hal.rgb(r, g, b)


def _seq(v):
    """List of numbers from a list, tuple, range or ulab ndarray.
    Returns None for a scalar."""
    if isinstance(v, (list, tuple)):
        return list(v)
    if isinstance(v, (int, float)):
        return None
    tl = getattr(v, "tolist", None)  # ulab ndarray
    if tl is not None:
        r = tl()
        return r if isinstance(r, list) else None
    try:
        return list(v)
    except TypeError:
        return None


def _columns(y):
    """Columns of a 2-D list (rows of a 2-D ndarray), else None."""
    if y and isinstance(y[0], list):
        return [[row[j] for row in y] for j in range(len(y[0]))]
    return None


def clf():
    global _lims, _axis_on, _grid, _title
    _items.clear()
    _lims = None
    _axis_on = True
    _grid = False
    _title = None
    _ci[0] = 0


def plot(x, y=None, color=None, fmt=None, **kw):
    if isinstance(y, str):
        fmt, y = y, None
    if y is None:
        y = _seq(x)
        x = list(range(len(y)))
    else:
        x = _seq(x)
        y = _seq(y)
    c = color if color is not None else (fmt if fmt else kw.get("c"))
    kind = "scatter" if (fmt and "o" in fmt and "-" not in fmt) else "plot"
    cols = _columns(y)
    for yy in cols if cols is not None else (y,):
        _items.append((kind, x, yy, _color(c)))


def scatter(x, y, color=None, **kw):
    xs = _seq(x)
    if xs is None:
        xs = [x]
        ys = [y]
    else:
        ys = _seq(y)
    _items.append(("scatter", xs, ys, _color(color if color is not None else kw.get("c"))))


def bar(x, height, width=0.8, color=None, **kw):
    xs = _seq(x)
    if xs is None:
        xs = [x]
    hs = _seq(height)
    if hs is None:
        hs = [height] * len(xs)
    _items.append(("bar", xs, hs, _color(color), width))


def hist(data, bins=10, color=None, **kw):
    data = _seq(data)
    cols = _columns(data)
    if cols is not None:
        data = [v for col in cols for v in col]
    lo = min(data)
    hi = max(data)
    if _seq(bins) is not None:
        edges = _seq(bins)
    else:
        if hi == lo:
            hi = lo + 1
        edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    counts = [0] * (len(edges) - 1)
    for v in data:
        for i in range(len(counts)):
            if edges[i] <= v < edges[i + 1] or (i == len(counts) - 1 and v == edges[-1]):
                counts[i] += 1
                break
    xs = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    w = edges[1] - edges[0]
    _items.append(("bar", xs, counts, _color(color), w))
    return counts, edges


def text(x, y, s, **kw):
    _items.append(("text", x, y, str(s)))


def arrow(x, y, dx, dy, color=None, **kw):
    _items.append(("arrow", x, y, dx, dy, _color(color if color is not None else "k")))


def axis(a=None):
    global _lims, _axis_on
    if a is None:
        return _limits()
    if isinstance(a, str):
        _axis_on = a != "off"
        return
    _lims = tuple(float(v) for v in _seq(a))
    return _lims


def xlim(lo, hi):
    l = list(_limits())
    axis([lo, hi, l[2], l[3]])


def ylim(lo, hi):
    l = list(_limits())
    axis([l[0], l[1], lo, hi])


def grid(on=True):
    global _grid
    _grid = bool(on) if on is not None else not _grid


def title(s):
    global _title
    _title = str(s)


def xlabel(s):
    pass


def ylabel(s):
    pass


def legend(*a, **k):
    pass


def _limits():
    if _lims:
        return _lims
    xs = []
    ys = []
    for it in _items:
        k = it[0]
        if k in ("plot", "scatter"):
            xs += it[1]
            ys += it[2]
        elif k == "bar":
            w = it[4]
            xs += [v - w / 2 for v in it[1]] + [v + w / 2 for v in it[1]]
            ys += it[2] + [0]
        elif k == "text":
            xs.append(it[1])
            ys.append(it[2])
        elif k == "arrow":
            xs += [it[1], it[1] + it[3]]
            ys += [it[2], it[2] + it[4]]
    ys = [v for v in ys if v == v and abs(v) < 1e30]
    if not xs or not ys:
        return (0.0, 1.0, 0.0, 1.0)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 - x0 < 1e-12:
        x0 -= 1
        x1 += 1
    if y1 - y0 < 1e-12:
        y0 -= 1
        y1 += 1
    px = (x1 - x0) * 0.05
    py = (y1 - y0) * 0.05
    return (x0 - px, x1 + px, y0 - py, y1 + py)


def _nice_step(span, n=5):
    raw = span / n
    p = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * p:
            return m * p
    return 10 * p


def show():
    hal.init()  # no-op when the calculator already did it (REPL / mpremote)
    fb = hal.display.fb
    _r.mark_dirty()
    W = hal.W
    H = hal.H
    x0, x1, y0, y1 = _limits()
    L, R, T, B = (28, 4, 4, 12) if _axis_on else (0, 0, 0, 0)
    if _title:
        T += 10
    pw = W - L - R
    ph = H - T - B
    fb.fill(hal.rgb(255, 255, 255))
    ink = hal.rgb(0, 0, 8)
    gridc = hal.rgb(220, 220, 220)
    sf = gfx.font("small")

    def sx(x):
        return L + int((x - x0) * (pw - 1) / (x1 - x0))

    def sy(y):
        return T + int((y1 - y) * (ph - 1) / (y1 - y0))

    if _axis_on:
        xs = _nice_step(x1 - x0)
        ys = _nice_step(y1 - y0, 4)
        v = math.ceil(x0 / xs) * xs
        while v <= x1 + 1e-12:
            px = sx(v)
            if _grid:
                fb.vline(px, T, ph, gridc)
            fb.vline(px, T + ph, 3, ink)
            s = "%g" % (round(v / xs) * xs)
            sf.text(s, max(0, min(W - sf.width(s), px - sf.width(s) // 2)), T + ph + 3, ink)
            v += xs
        v = math.ceil(y0 / ys) * ys
        while v <= y1 + 1e-12:
            py = sy(v)
            if _grid:
                fb.hline(L, py, pw, gridc)
            fb.hline(L - 3, py, 3, ink)
            s = "%g" % (round(v / ys) * ys)
            sf.text(s[:5], max(0, L - 4 - sf.width(s[:5])), py - 4, ink)
            v += ys
        fb.rect(L, T, pw, ph, ink)
    if _title:
        gfx.font("normal").text(_title, (W - gfx.font("normal").width(_title)) // 2, 1, ink)
    for it in _items:
        k = it[0]
        if k == "plot":
            prev = None
            for x, y in zip(it[1], it[2]):
                if y is None or y != y:
                    prev = None
                    continue
                p = (sx(x), sy(y))
                if prev:
                    fb.line(prev[0], prev[1], p[0], p[1], it[3])
                prev = p
        elif k == "scatter":
            for x, y in zip(it[1], it[2]):
                fb.fill_rect(sx(x) - 1, sy(y) - 1, 3, 3, it[3])
        elif k == "bar":
            w = it[4]
            for x, h in zip(it[1], it[2]):
                a = sx(x - w / 2)
                b = sx(x + w / 2)
                ya = sy(max(h, 0))
                yb = sy(min(h, 0))
                fb.fill_rect(a, ya, max(1, b - a), max(1, yb - ya), it[3])
        elif k == "text":
            sf.text(it[3], sx(it[1]), sy(it[2]) - 8, ink)
        elif k == "arrow":
            ax, ay = sx(it[1]), sy(it[2])
            bx, by = sx(it[1] + it[3]), sy(it[2] + it[4])
            fb.line(ax, ay, bx, by, it[5])
            ang = math.atan2(by - ay, bx - ax)
            for da in (2.6, -2.6):
                fb.line(bx, by, bx + int(5 * math.cos(ang + da)), by + int(5 * math.sin(ang + da)), it[5])
    _r.show()
    from cardgcalc import wait_key

    try:
        wait_key()
    except KeyboardInterrupt:
        pass
    clf()
