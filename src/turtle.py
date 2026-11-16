# turtle: classic turtle graphics on the card-gcalc screen.
# Origin at the screen centre, y up, heading 0 = east, angles in degrees.
import math
from cardgcalc import hal, gfx
from cardgcalc import runner as _r

_COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 180, 0),
    "blue": (0, 0, 255), "yellow": (255, 220, 0), "cyan": (0, 220, 220), "magenta": (255, 0, 255),
    "orange": (255, 150, 0), "purple": (150, 0, 200), "pink": (255, 150, 200), "brown": (140, 80, 20),
    "gray": (128, 128, 128), "grey": (128, 128, 128),
}
_W = hal.W
_H = hal.H
_SPR = 7  # cursor half-size


class _T:
    pass


_t = _T()


def _rgb(c):
    if isinstance(c, str):
        c = _COLORS.get(c.lower(), (0, 0, 0))
    if isinstance(c, (tuple, list)):
        r, g, b = c[0], c[1], c[2]
        if r <= 1 and g <= 1 and b <= 1 and (isinstance(r, float) or isinstance(g, float)):
            r, g, b = int(r * 255), int(g * 255), int(b * 255)
        if r == g == b == 0:
            b = 8  # avoid the text blit transparent key
        return hal.rgb(int(r), int(g), int(b))
    return int(c)


def reset():
    hal.init()  # no-op when the calculator already did it (REPL / mpremote)
    _t.x = 0.0
    _t.y = 0.0
    _t.h = 0.0
    _t.down = True
    _t.col = _rgb("black")
    _t.colname = "black"
    _t.size = 1
    _t.speed = 6
    _t.visible = True
    _t.under = None
    _t.bg = hal.rgb(255, 255, 255)
    _r.mark_dirty()
    hal.display.fb.fill(_t.bg)
    _draw_cursor()


def _sx(x):
    return int(round(_W // 2 + x))


def _sy(y):
    return int(round(_H // 2 - y))


def _hide_cursor():
    u = _t.under
    if u is None:
        return
    x0, y0, px = u
    fb = hal.display.fb
    n = 2 * _SPR + 1
    i = 0
    for dy in range(n):
        for dx in range(n):
            fb.pixel(x0 + dx, y0 + dy, px[i])
            i += 1
    _t.under = None


def _draw_cursor():
    if not _t.visible:
        return
    fb = hal.display.fb
    cx = _sx(_t.x)
    cy = _sy(_t.y)
    x0 = cx - _SPR
    y0 = cy - _SPR
    n = 2 * _SPR + 1
    px = []
    for dy in range(n):
        for dx in range(n):
            px.append(fb.pixel(x0 + dx, y0 + dy) or 0)
    _t.under = (x0, y0, px)
    a = math.radians(_t.h)
    ca = math.cos(a)
    sa = math.sin(a)
    pts = ((6, 0), (-4, 4), (-2, 0), (-4, -4))
    xs = []
    for (u, v) in pts:
        xs.append((cx + int(round(u * ca - v * sa)), cy - int(round(u * sa + v * ca))))
    for i in range(4):
        x1, y1 = xs[i]
        x2, y2 = xs[(i + 1) % 4]
        fb.line(x1, y1, x2, y2, _t.col)


def _line(x0, y0, x1, y1):
    fb = hal.display.fb
    s = _t.size
    if s <= 1:
        fb.line(x0, y0, x1, y1, _t.col)
        return
    r = s // 2
    dx = x1 - x0
    dy = y1 - y0
    n = max(abs(dx), abs(dy), 1)
    for i in range(n + 1):
        fb.fill_rect(x0 + dx * i // n - r, y0 + dy * i // n - r, s, s, _t.col)


def _moveto(x, y):
    _r.check()
    _r.mark_dirty()
    _hide_cursor()
    if _t.down:
        _line(_sx(_t.x), _sy(_t.y), _sx(x), _sy(y))
    _t.x = x
    _t.y = y
    _draw_cursor()
    if _t.speed:
        _r.show()
        if _t.speed < 10:
            import time

            time.sleep_ms((10 - _t.speed) * 4)


def forward(d):
    a = math.radians(_t.h)
    _moveto(_t.x + d * math.cos(a), _t.y + d * math.sin(a))


fd = forward


def backward(d):
    forward(-d)


back = bk = backward


def right(a):
    _hide_cursor()
    _t.h = (_t.h - a) % 360
    _draw_cursor()
    _r.mark_dirty()


rt = right


def left(a):
    right(-a)


lt = left


def goto(x, y=None):
    if y is None:
        x, y = x
    _moveto(float(x), float(y))


setposition = setpos = goto


def setheading(a):
    _hide_cursor()
    _t.h = a % 360
    _draw_cursor()


seth = setheading


def home():
    goto(0, 0)
    setheading(0)


def position():
    return (_t.x, _t.y)


pos = position


def xcor():
    return _t.x


def ycor():
    return _t.y


def heading():
    return _t.h


def towards(x, y=None):
    if y is None:
        x, y = x
    return math.degrees(math.atan2(y - _t.y, x - _t.x)) % 360


def distance(x, y=None):
    if y is None:
        x, y = x
    return math.sqrt((x - _t.x) ** 2 + (y - _t.y) ** 2)


def penup():
    _t.down = False


pu = up = penup


def pendown():
    _t.down = True


pd = down = pendown


def isdown():
    return _t.down


def pensize(s=None):
    if s is None:
        return _t.size
    _t.size = max(1, int(s))


width = pensize


def color(*c):
    if not c:
        return _t.colname
    if len(c) == 3:
        c = (c,)
    _hide_cursor()
    _t.colname = c[0]
    _t.col = _rgb(c[0])
    _draw_cursor()


pencolor = color


def bgcolor(c):
    _t.bg = _rgb(c)
    _hide_cursor()
    hal.display.fb.fill(_t.bg)
    _draw_cursor()
    _r.mark_dirty()


def speed(s=None):
    if s is None:
        return _t.speed
    _t.speed = max(0, min(10, int(s)))


def circle(radius, extent=360, steps=None):
    if steps is None:
        steps = max(8, min(72, int(abs(radius) * abs(extent) / 360 / 2) + 8))
    step_a = extent / steps
    seg = 2 * radius * math.sin(math.radians(abs(step_a)) / 2)
    left(step_a / 2)
    for _ in range(steps):
        forward(seg if radius >= 0 else -seg)
        left(step_a)
    left(-step_a / 2)


def dot(size=5, c=None):
    col = _t.col if c is None else _rgb(c)
    _hide_cursor()
    hal.display.fb.ellipse(_sx(_t.x), _sy(_t.y), size // 2, size // 2, col, True)
    _draw_cursor()
    _r.mark_dirty()


def write(text, *a, **k):
    _hide_cursor()
    gfx.font("normal").text(str(text), _sx(_t.x), _sy(_t.y) - 10, _t.col)
    _draw_cursor()
    _r.mark_dirty()


def hideturtle():
    _hide_cursor()
    _t.visible = False
    _r.mark_dirty()


ht = hideturtle


def showturtle():
    _t.visible = True
    _draw_cursor()
    _r.mark_dirty()


st = showturtle


def isvisible():
    return _t.visible


def clear():
    _hide_cursor()
    hal.display.fb.fill(_t.bg)
    _draw_cursor()
    _r.mark_dirty()


def done():
    _r.show()


mainloop = exitonclick = done

reset()
