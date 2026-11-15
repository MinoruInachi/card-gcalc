# Base Conv: programmer's calculator (DEC/HEX/OCT/BIN, fixed word size).
#
#   operators  + - * / (integer division) %  AND OR XOR NOT NAND NOR XNOR SHL SHR
#              also & | ^ ~ << >>
#   numbers    in the current base; prefixes 0x 0o (and 0b 0d except in HEX)
#   opt+a AND  opt+o OR  opt+x XOR  opt+n NOT  opt+l SHL  opt+r SHR
from nc import hal, gfx, ui, storage
from nc.hal import ENTER, ESC, UP, DOWN, OPT, ALT
from nc.i18n import T

MODES = ("DEC", "HEX", "OCT", "BIN")
BASE = {"DEC": 10, "HEX": 16, "OCT": 8, "BIN": 2}
BITS = (8, 16, 32, 64)
KEYWORDS = ("AND", "OR", "XOR", "NOT", "NAND", "NOR", "XNOR", "SHL", "SHR", "MOD")
_OPTKEYS = {"a": " AND ", "o": " OR ", "x": " XOR ", "n": "NOT ", "l": " SHL ", "r": " SHR ",
            "m": " MOD "}


class BaseError(Exception):
    pass


class Machine:
    def __init__(self, bits=32, signed=True):
        self.bits = bits
        self.signed = signed

    def wrap(self, v):
        mask = (1 << self.bits) - 1
        v &= mask
        if self.signed and v >> (self.bits - 1):
            v -= 1 << self.bits
        return v

    def unsigned(self, v):
        return v & ((1 << self.bits) - 1)

    # ---- parsing ---------------------------------------------------------
    def tokenize(self, s, base):
        toks = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c in " \t":
                i += 1
                continue
            if s.startswith("<<", i) or s.startswith(">>", i):
                toks.append(("op", "SHL" if c == "<" else "SHR"))
                i += 2
                continue
            if c in "+-*/%()&|^~×÷":
                m = {"&": "AND", "|": "OR", "^": "XOR", "~": "NOT", "×": "*", "÷": "/", "%": "MOD"}
                toks.append(("op", m.get(c, c)))
                i += 1
                continue
            if c.isalpha() or c.isdigit():
                j = i
                while j < n and (s[j].isalpha() or s[j].isdigit()):
                    j += 1
                w = s[i:j].upper()
                i = j
                if w in KEYWORDS:
                    toks.append(("op", w))
                elif w == "ANS":
                    toks.append(("ans", None))
                else:
                    toks.append(("num", self.parse_num(w, base)))
                continue
            raise BaseError("Syntax error: '%s'" % c)
        return toks

    def parse_num(self, w, base):
        b = base
        if len(w) > 2 and w[0] == "0" and w[1] in "XO" or (len(w) > 2 and w[0] == "0" and w[1] in "BD" and base != 16):
            b = {"X": 16, "O": 8, "B": 2, "D": 10}[w[1]]
            w = w[2:]
        try:
            v = int(w, b)
        except ValueError:
            raise BaseError("Invalid %s number: %s" % ({10: "DEC", 16: "HEX", 8: "OCT", 2: "BIN"}[b], w))
        return self.wrap(v)

    def evaluate(self, s, base, ans=0):
        self.t = self.tokenize(s, base)
        if not self.t:
            raise BaseError("Syntax error")
        self.p = 0
        self.ans = ans
        v = self._or()
        if self.p != len(self.t):
            raise BaseError("Syntax error")
        return self.wrap(v)

    def _peek(self):
        return self.t[self.p] if self.p < len(self.t) else (None, None)

    def _accept(self, *ops):
        k, v = self._peek()
        if k == "op" and v in ops:
            self.p += 1
            return v
        return None

    def _or(self):
        a = self._xor()
        while True:
            op = self._accept("OR", "NOR")
            if not op:
                return a
            b = self._xor()
            a = self.wrap(a | b)
            if op == "NOR":
                a = self.wrap(~a)

    def _xor(self):
        a = self._and()
        while True:
            op = self._accept("XOR", "XNOR")
            if not op:
                return a
            b = self._and()
            a = self.wrap(a ^ b)
            if op == "XNOR":
                a = self.wrap(~a)

    def _and(self):
        a = self._shift()
        while True:
            op = self._accept("AND", "NAND")
            if not op:
                return a
            b = self._shift()
            a = self.wrap(a & b)
            if op == "NAND":
                a = self.wrap(~a)

    def _shift(self):
        a = self._sum()
        while True:
            op = self._accept("SHL", "SHR")
            if not op:
                return a
            b = self._sum()
            if b < 0:
                raise BaseError("Negative shift")
            if op == "SHL":
                a = self.wrap(a << b) if b < 128 else 0
            else:
                # logical shift on the word
                a = self.wrap(self.unsigned(a) >> b) if b < 128 else 0

    def _sum(self):
        a = self._term()
        while True:
            op = self._accept("+", "-")
            if not op:
                return a
            b = self._term()
            a = self.wrap(a + b if op == "+" else a - b)

    def _term(self):
        a = self._unary()
        while True:
            op = self._accept("*", "/", "MOD")
            if not op:
                return a
            b = self._unary()
            if op == "*":
                a = self.wrap(a * b)
            else:
                if b == 0:
                    raise BaseError("Math error: ÷0")
                q = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    q = -q
                a = self.wrap(q if op == "/" else a - q * b)

    def _unary(self):
        op = self._accept("-", "+", "NOT")
        if op == "-":
            return self.wrap(-self._unary())
        if op == "+":
            return self._unary()
        if op == "NOT":
            return self.wrap(~self._unary())
        return self._atom()

    def _atom(self):
        k, v = self._peek()
        self.p += 1
        if k == "num":
            return v
        if k == "ans":
            return self.wrap(self.ans)
        if k == "op" and v == "(":
            a = self._or()
            if not self._accept(")"):
                if self._peek()[0] is not None:
                    raise BaseError("Syntax error")
            return a
        raise BaseError("Syntax error")

    # ---- formatting -------------------------------------------------------------
    def fmt(self, v, mode):
        if mode == "DEC":
            return str(v if self.signed else self.unsigned(v))
        u = self.unsigned(v)
        if mode == "HEX":
            return "%0*X" % ((self.bits + 3) // 4, u)
        if mode == "OCT":
            return "%o" % u
        s = ""
        for i in range(self.bits - 1, -1, -1):
            s += "1" if (u >> i) & 1 else "0"
        return s


def _group(bits, n=4):
    return " ".join(bits[i:i + n] for i in range(0, len(bits), n))


class App:
    def __init__(self):
        cfg = storage.load_json("basen.json", None) or {}
        self.mode = cfg.get("mode", "DEC")
        self.m = Machine(cfg.get("bits", 32), cfg.get("signed", True))
        self.ans = cfg.get("ans", 0)
        self.last = cfg.get("last", "")
        self.hist = []
        self.err = None
        self.ed = ui.LineEdit("", math=False, font="medium")

    def save(self):
        storage.save_json("basen.json", {"mode": self.mode, "bits": self.m.bits, "signed": self.m.signed,
                                         "ans": self.ans, "last": self.last})

    def draw(self):
        fb = gfx.fb()
        f = gfx.font("normal")
        fm = gfx.font("medium")
        fs = gfx.font("small")
        gfx.fill()
        ui.status_bar("Base Conv", "%s %d%s" % (self.mode, self.m.bits, "s" if self.m.signed else "u"))
        # previous expression
        y = ui.TOP + 2
        if self.err:
            f.text(f.clip(T(self.err), ui.W - 6), 3, y, gfx.ERR)
        elif self.last:
            f.text(f.clip(self.last + " =", ui.W - 6), 3, y, gfx.DIM)
        y += 12
        fb.fill_rect(0, y - 1, ui.W, 17, gfx.PANEL)
        self.ed.draw(4, y + 1, ui.W - 8, bg=gfx.PANEL)
        y += 19
        v = self.ans
        for md in ("DEC", "HEX", "OCT"):
            cur = md == self.mode
            if cur:
                fb.fill_rect(0, y - 1, ui.W, 13, gfx.PANEL2)
            f.text(md, 3, y + 1, gfx.YELLOW if cur else gfx.ACCENT)
            s = self.m.fmt(v, md)
            fm.text(fm.clip(s, ui.W - 40), ui.W - 4 - fm.width(fm.clip(s, ui.W - 40)), y - 1, gfx.FG)
            y += 13
        cur = self.mode == "BIN"
        b = self.m.fmt(v, "BIN")
        lines = [b[i:i + 32] for i in range(0, len(b), 32)]
        h = 10 * len(lines) + 2
        if cur:
            fb.fill_rect(0, y - 1, ui.W, h, gfx.PANEL2)
        f.text("BIN", 3, y + 1, gfx.YELLOW if cur else gfx.ACCENT)
        for i, ln in enumerate(lines):
            t = _group(ln)
            fs.text(t, ui.W - 4 - fs.width(t), y + 1 + i * 10, gfx.FG)
        ui.softkeys(["DEC", "HEX", "OCT", "BIN", "%dbit" % self.m.bits, "signed" if self.m.signed else "unsign"],
                    MODES.index(self.mode))
        gfx.show()

    def run(self):
        while True:
            self.draw()
            k = hal.wait_key()
            fk = ui.fkey(k)
            if fk is not None:
                if fk < 4:
                    self.mode = MODES[fk]
                elif fk == 4:
                    self.m.bits = BITS[(BITS.index(self.m.bits) + 1) % len(BITS)]
                    self.ans = self.m.wrap(self.ans)
                elif fk == 5:
                    self.m.signed = not self.m.signed
                    self.ans = self.m.wrap(self.ans)
                continue
            if k.mods & (OPT | ALT) and k.base in _OPTKEYS:
                self.ed.insert(_OPTKEYS[k.base])
                continue
            if k.key == UP:
                if self.last:
                    self.ed.set(self.last)
                continue
            if k.key == DOWN:
                continue
            r = self.ed.handle(k)
            if r == "enter":
                src = self.ed.text.strip() or self.last
                if not src:
                    continue
                try:
                    self.ans = self.m.evaluate(src, BASE[self.mode], self.ans)
                    self.last = src
                    self.err = None
                    self.ed.set("")
                except BaseError as e:
                    self.err = str(e)
                except Exception as e:
                    self.err = "Error: %s" % e
            elif r == "esc":
                if self.ed.text:
                    self.ed.set("")
                    self.err = None
                else:
                    return


def run():
    a = App()
    try:
        a.run()
    finally:
        a.save()
