# Drawing helpers: bitmap fonts, colours and a few primitives on top of
# framebuf.  All drawing goes to hal.display.fb; call hal.display.show()
# (or show_rect) to push to the panel.
import framebuf
from nc import hal
from nc.hal import rgb

# ---- Palette -------------------------------------------------------------
BLACK = rgb(0, 0, 0)
WHITE = rgb(255, 255, 255)
BG = rgb(16, 18, 24)
PANEL = rgb(32, 36, 48)
PANEL2 = rgb(48, 54, 70)
FG = rgb(232, 234, 240)
DIM = rgb(130, 136, 150)
ACCENT = rgb(255, 170, 40)
ACCENT2 = rgb(80, 180, 255)
SEL = rgb(60, 110, 200)
OK = rgb(90, 210, 120)
ERR = rgb(255, 90, 90)
YELLOW = rgb(255, 220, 60)
MAGENTA = rgb(230, 100, 220)
CYAN = rgb(80, 220, 230)
GRID = rgb(40, 44, 56)
AXIS = rgb(140, 146, 160)

# Colours for graph functions Y1..Y6 (and data series)
SERIES = (
    rgb(255, 90, 90),
    rgb(80, 180, 255),
    rgb(90, 210, 120),
    rgb(255, 170, 40),
    rgb(200, 120, 255),
    rgb(80, 220, 230),
)

# Characters missing from some fonts are drawn as a substitute string.
_SUBST = {"∛": "³√", "ᴇ": "E", "↵": "←", "∠": "<", "▶": ">", "◀": "<", "✓": "v", "ˣ": "x"}


class _JP:
    """Japanese 8x12 glyphs (k8x12L) used as a fallback by every Font.

    The glyph table stays in flash (frozen bytes); glyphs are looked up by
    binary search and the most recently used ones are cached in RAM."""

    W = 8
    H = 12
    CACHE = 160

    def __init__(self):
        from nc.fonts import jp8x12 as m

        self.codes = m.CODES
        self.data = m.GLYPHS
        self.n = m.N
        self.cache = {}

    def find(self, cp):
        c = self.codes
        lo = 0
        hi = self.n - 1
        while lo <= hi:
            mid = (lo + hi) >> 1
            v = (c[2 * mid] << 8) | c[2 * mid + 1]
            if v == cp:
                return mid
            if v < cp:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1

    def glyph(self, ch):
        g = self.cache.get(ch)
        if g is None:
            cp = ord(ch)
            i = self.find(cp) if cp <= 0xFFFF else -1
            if i < 0:
                g = False
            else:
                o = i * 12
                g = framebuf.FrameBuffer(bytearray(self.data[o : o + 12]), 8, 12, framebuf.MONO_HLSB)
            if len(self.cache) >= self.CACHE:
                self.cache.clear()
            self.cache[ch] = g
        return g


_jp = None


def jp():
    global _jp
    if _jp is None:
        _jp = _JP()
    return _jp


class Font:
    def __init__(self, mod):
        self.w = mod.W
        self.h = mod.H
        self._bpr = mod.BPR
        self._gsize = mod.H * mod.BPR
        self._data = bytearray(mod.GLYPHS)
        self._mv = memoryview(self._data)
        self._index = {}
        for i, ch in enumerate(mod.INDEX):
            self._index[ch] = i
        self._cache = {}
        self._pal = framebuf.FrameBuffer(bytearray(4), 2, 1, framebuf.RGB565)
        # vertical offset that centres a 12px Japanese glyph on this font
        self._jpdy = (self.h - 12) // 2

    def glyph(self, ch):
        g = self._cache.get(ch)
        if g is None:
            i = self._index.get(ch)
            if i is None:
                i = self._index.get("?")
            o = i * self._gsize
            g = framebuf.FrameBuffer(self._mv[o : o + self._gsize], self.w, self.h, framebuf.MONO_HLSB)
            self._cache[ch] = g
        return g

    def text(self, s, x, y, fg=FG, bg=None, fb=None):
        """Draw string s at (x, y).  bg=None draws transparently.
        Characters missing from this font (e.g. Japanese) are drawn with the
        8x12 Japanese font.  Returns the x coordinate after the text."""
        if fb is None:
            fb = hal.display.fb
        pal = self._pal
        pal.pixel(1, 0, fg)
        if bg is None:
            # framebuf compares the key with the colour *after* palette
            # mapping, so slot 0 must hold a value different from fg.
            key = fg ^ 0xFFFF
            pal.pixel(0, 0, key)
        else:
            pal.pixel(0, 0, bg)
            key = -1
        w = self.w
        idx = self._index
        for ch in s:
            if ch in idx:
                fb.blit(self.glyph(ch), x, y, key, pal)
                x += w
                continue
            if ch in _SUBST:
                for c2 in _SUBST[ch]:
                    fb.blit(self.glyph(c2), x, y, key, pal)
                    x += w
                continue
            g = jp().glyph(ch) if ord(ch) >= 0x80 else False
            if g:
                fb.blit(g, x, y + self._jpdy, key, pal)
                x += 8
            else:
                fb.blit(self.glyph("?"), x, y, key, pal)
                x += w
        return x

    def cw(self, ch):
        """Width of one character in pixels."""
        if ch in self._index:
            return self.w
        if ch in _SUBST:
            return len(_SUBST[ch]) * self.w
        if ord(ch) >= 0x80 and jp().glyph(ch):
            return 8
        return self.w

    def width(self, s):
        idx = self._index
        n = 0
        extra = 0
        for ch in s:
            if ch in idx:
                n += 1
            else:
                extra += self.cw(ch)
        return n * self.w + extra

    def fits(self, s, maxw):
        """Number of leading characters of s that fit in maxw pixels."""
        x = 0
        for i, ch in enumerate(s):
            x += self.cw(ch)
            if x > maxw:
                return i
        return len(s)

    def clip(self, s, maxw):
        """Truncate s so that it fits in maxw pixels (adds '…')."""
        if self.width(s) <= maxw:
            return s
        n = self.fits(s, maxw - self.w)
        return s[: max(0, n)] + "…"


_fonts = {}


def font(name):
    """Fonts: 'small' (5x8), 'normal' (6x10), 'medium' (6x13), 'large' (10x20)."""
    f = _fonts.get(name)
    if f is None:
        if name == "small":
            from nc.fonts import f5x8 as m
        elif name == "medium":
            from nc.fonts import f6x13 as m
        elif name == "large":
            from nc.fonts import f10x20 as m
        else:
            from nc.fonts import f6x10 as m
        f = Font(m)
        _fonts[name] = f
    return f


def fb():
    return hal.display.fb


def fill(c=BG):
    hal.display.fb.fill(c)


def rect(x, y, w, h, c, filled=True):
    if filled:
        hal.display.fb.fill_rect(x, y, w, h, c)
    else:
        hal.display.fb.rect(x, y, w, h, c)


def line(x0, y0, x1, y1, c):
    hal.display.fb.line(x0, y0, x1, y1, c)


def round_rect(x, y, w, h, c, r=3):
    f = hal.display.fb
    f.fill_rect(x + r, y, w - 2 * r, h, c)
    f.fill_rect(x, y + r, w, h - 2 * r, c)
    f.ellipse(x + r, y + r, r, r, c, True)
    f.ellipse(x + w - r - 1, y + r, r, r, c, True)
    f.ellipse(x + r, y + h - r - 1, r, r, c, True)
    f.ellipse(x + w - r - 1, y + h - r - 1, r, r, c, True)


def show():
    hal.display.show()


def show_rect(x, y, w, h):
    hal.display.show_rect(x, y, w, h)
