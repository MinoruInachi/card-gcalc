# Home-screen icons, drawn procedurally (no image assets).
# Each icon is a 36x36 rounded tile in the app's colour with a white glyph.
import math
from nc import gfx
from nc.hal import rgb

S = 36
WHITE = gfx.WHITE
INK = rgb(20, 24, 32)


def tile(x, y, col, sel=False):
    if sel:
        gfx.round_rect(x - 3, y - 3, S + 6, S + 6, gfx.YELLOW, 6)
        gfx.round_rect(x - 1, y - 1, S + 2, S + 2, gfx.BG, 5)
    gfx.round_rect(x, y, S, S, col, 5)


def _calc(fb, x, y):
    fb.fill_rect(x + 9, y + 6, 18, 24, WHITE)
    fb.fill_rect(x + 11, y + 8, 14, 5, INK)
    for r in range(3):
        for c in range(3):
            fb.fill_rect(x + 11 + c * 5, y + 15 + r * 5, 4, 4, rgb(255, 140, 60) if (r, c) == (2, 2) else INK)


def _graph(fb, x, y):
    fb.hline(x + 5, y + 20, 26, WHITE)
    fb.vline(x + 12, y + 5, 26, WHITE)
    px = py = None
    for i in range(27):
        xx = x + 5 + i
        yy = y + 20 - int(9 * math.sin(i / 26 * 2 * math.pi))
        if px is not None:
            fb.line(px, py, xx, yy, rgb(255, 230, 90))
            fb.line(px, py + 1, xx, yy + 1, rgb(255, 230, 90))
        px, py = xx, yy


def _graph3d(fb, x, y):
    # axes in oblique projection and a curved mesh surface
    ox, oy = x + 12, y + 24
    fb.line(ox, oy, ox + 20, oy, WHITE)
    fb.line(ox, oy, ox, oy - 19, WHITE)
    fb.line(ox, oy, ox - 7, oy + 7, WHITE)
    yel = rgb(255, 230, 90)
    for i in range(5):
        pts = []
        for j in range(9):
            u = j / 8
            v = i / 4
            px = ox - 6 + int(22 * u + 9 * v)
            py = oy - 4 - int(10 * math.sin(math.pi * u) * (1 - 0.6 * v)) - int(7 * v) + 3
            pts.append((px, py))
        for j in range(8):
            fb.line(pts[j][0], pts[j][1], pts[j + 1][0], pts[j + 1][1], yel)
        if i == 0:
            first = pts
        if i == 4:
            for j in range(0, 9, 2):
                fb.line(first[j][0], first[j][1], pts[j][0], pts[j][1], yel)


def _table(fb, x, y):
    fb.fill_rect(x + 6, y + 7, 24, 22, WHITE)
    fb.fill_rect(x + 6, y + 7, 24, 5, rgb(255, 200, 80))
    for r in range(4):
        fb.hline(x + 6, y + 12 + r * 5, 24, INK)
    fb.vline(x + 15, y + 7, 22, INK)
    fb.rect(x + 6, y + 7, 24, 22, INK)


def _equation(fb, x, y):
    f = gfx.font("large")
    f.text("x", x + 4, y + 6, WHITE)
    gfx.font("medium").text("2", x + 14, y + 4, WHITE)
    f.text("=", x + 20, y + 8, WHITE)
    fb.fill_rect(x + 6, y + 28, 24, 2, WHITE)


def _stats(fb, x, y):
    for i, h in enumerate((8, 15, 22, 12, 18)):
        fb.fill_rect(x + 6 + i * 5, y + 29 - h, 4, h, WHITE)
    fb.hline(x + 5, y + 30, 26, WHITE)


def _matrix(fb, x, y):
    for xx in (x + 7, x + 27):
        fb.vline(xx, y + 7, 22, WHITE)
        fb.vline(xx + 1, y + 7, 22, WHITE)
    for xx in (x + 9, x + 25):
        fb.hline(xx - 1 if xx < x + 20 else xx - 1, y + 7, 3, WHITE)
        fb.hline(xx - 1, y + 28, 3, WHITE)
    for r in range(3):
        for c in range(3):
            fb.fill_rect(x + 12 + c * 5, y + 11 + r * 6, 3, 3, WHITE)


def _basen(fb, x, y):
    f = gfx.font("medium")
    f.text("0x", x + 6, y + 5, WHITE)
    f.text("1F", x + 18, y + 5, rgb(255, 230, 120))
    f.text("101", x + 9, y + 19, WHITE)


def _python(fb, x, y):
    blue = rgb(70, 130, 210)
    yel = rgb(255, 210, 60)
    gfx.round_rect(x + 7, y + 6, 14, 14, blue, 4)
    gfx.round_rect(x + 15, y + 16, 14, 14, yel, 4)
    fb.fill_rect(x + 10, y + 8, 2, 2, WHITE)
    fb.fill_rect(x + 24, y + 26, 2, 2, INK)


def _editor(fb, x, y):
    fb.fill_rect(x + 7, y + 6, 20, 24, WHITE)
    for i, w in enumerate((12, 9, 14, 7)):
        fb.fill_rect(x + 10 + (2 if i in (1, 2) else 0), y + 10 + i * 5, w, 2, INK)
    # pencil
    for i in range(10):
        fb.fill_rect(x + 18 + i, y + 26 - i, 3, 3, rgb(255, 190, 60))
    fb.fill_rect(x + 17, y + 27, 2, 2, INK)


def _shell(fb, x, y):
    fb.fill_rect(x + 5, y + 8, 26, 20, INK)
    fb.rect(x + 5, y + 8, 26, 20, WHITE)
    gfx.font("normal").text(">_", x + 8, y + 13, rgb(120, 255, 140))


def _files(fb, x, y):
    c = rgb(255, 215, 100)
    fb.fill_rect(x + 6, y + 9, 10, 4, c)
    fb.fill_rect(x + 6, y + 12, 24, 17, c)
    fb.fill_rect(x + 6, y + 15, 24, 1, rgb(220, 170, 40))
    # sd card
    fb.fill_rect(x + 20, y + 18, 8, 9, WHITE)
    fb.fill_rect(x + 21, y + 19, 6, 2, INK)


def _gpio(fb, x, y):
    fb.fill_rect(x + 10, y + 10, 16, 16, INK)
    fb.rect(x + 10, y + 10, 16, 16, WHITE)
    for i in range(4):
        o = 12 + i * 4
        fb.fill_rect(x + o, y + 6, 2, 4, WHITE)
        fb.fill_rect(x + o, y + 26, 2, 4, WHITE)
        fb.fill_rect(x + 6, y + o, 4, 2, WHITE)
        fb.fill_rect(x + 26, y + o, 4, 2, WHITE)
    fb.ellipse(x + 14, y + 14, 1, 1, WHITE, True)


def _settings(fb, x, y):
    cx = x + 18
    cy = y + 18
    for k in range(8):
        a = k * math.pi / 4
        dx = int(round(11 * math.cos(a)))
        dy = int(round(11 * math.sin(a)))
        fb.fill_rect(cx + dx - 2, cy + dy - 2, 5, 5, WHITE)
    fb.ellipse(cx, cy, 9, 9, WHITE, True)
    fb.ellipse(cx, cy, 4, 4, rgb(110, 116, 130), True)


def _sequence(fb, x, y):
    f = gfx.font("medium")
    f.text("u", x + 6, y + 6, WHITE)
    gfx.font("small").text("n+1", x + 13, y + 12, WHITE)
    for i, h in enumerate((4, 7, 11, 16)):
        fb.fill_rect(x + 7 + i * 6, y + 30 - h, 3, 3, rgb(255, 230, 90))


def _units(fb, x, y):
    f = gfx.font("normal")
    f.text("km", x + 5, y + 6, WHITE)
    fb.line(x + 9, y + 20, x + 27, y + 20, WHITE)
    fb.line(x + 24, y + 17, x + 27, y + 20, WHITE)
    fb.line(x + 24, y + 23, x + 27, y + 20, WHITE)
    f.text("mi", x + 17, y + 24, WHITE)


DRAW = {
    "calc": _calc, "graph": _graph, "table": _table, "equation": _equation,
    "stats": _stats, "matrix": _matrix, "basen": _basen, "python": _python,
    "editor": _editor, "shell": _shell, "files": _files, "gpio": _gpio,
    "settings": _settings, "graph3d": _graph3d, "sequence": _sequence, "units": _units,
}


def draw(name, x, y, col, sel=False):
    tile(x, y, col, sel)
    f = DRAW.get(name)
    if f:
        f(gfx.fb(), x, y)
