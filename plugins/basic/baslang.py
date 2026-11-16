# Structured BASIC interpreter (core; no screen code -- see basic.py).
#
# The program is compiled once into a flat list of closures ("instructions").
# Each instruction returns None (next), an index (jump) or -1 (return from a
# SUB / FUNCTION).  Block statements (IF, FOR, WHILE, DO, SELECT, SUB) are
# compiled to jumps, so GOTO / GOSUB and labels work too.
#
#   b = Basic(io)          io: output / input / graphics (see HostIO)
#   b.load(source)         compile (raises BasicError with .line)
#   b.run()                run from the top (variables are reset)
#   b.immediate("PRINT x") compile and run one line in the program context
import math
import random
import time

VERSION = "1.0"

KW = set((
    "AND BOX CALL CASE CIRCLE CLS COLOR CONST DATA DIM DO ELSE ELSEIF END ENDIF "
    "EXIT FOR FUNCTION GCLS GOSUB GOTO GPRINT IF INPUT IS LET LINE LOCAL LOOP MOD "
    "NEXT NOT OR PRINT PSET RANDOMIZE READ REM RESTORE RETURN SELECT SLEEP STEP "
    "STOP SUB SWAP THEN TO UNTIL WEND WHILE XOR").split())

CLOSE = {"FOR": "NEXT", "WHILE": "WEND", "DO": "LOOP", "IF": "END IF", "SELECT": "END SELECT",
         "SUB": "END SUB", "FUNCTION": "END FUNCTION"}
ZONE = 10  # PRINT , column width
EOL = ("eol", None)
COLON = ("op", ":")
LPAR = ("op", "(")
RPAR = ("op", ")")
COMMA = ("op", ",")


class BasicError(Exception):
    def __init__(self, msg, line=None):
        super().__init__(msg)
        self.msg = msg
        self.line = line
        self.compile = False

    def __str__(self):
        if self.line:
            return "%s (line %d)" % (self.msg, self.line)
        return self.msg


class _End(Exception):
    pass


# ---- values -----------------------------------------------------------------
def fmtnum(v):
    if isinstance(v, int):
        return str(v)
    if v != v:
        return "NaN"
    if v in (math.inf, -math.inf):
        return "-Inf" if v < 0 else "Inf"
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    s = "%.10g" % v
    if "e" in s:
        m, e = s.split("e")
        s = m + "E" + ("-" if e[0] == "-" else "+") + e[1:].lstrip("0")
    return s


def tostr(v):
    return v if isinstance(v, str) else fmtnum(v)


def tonum(s):
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return None


def _dflt(name):
    return "" if name[-1] == "$" else 0


def _ix(v):
    i = int(v)
    if i < 0:
        raise IndexError
    return i


def _idiv(a, b):
    a = int(a)
    b = int(b)
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _mod(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a - b * _idiv(a, b)
    return math.fmod(a, b)


def _pow(a, b):
    r = a ** b
    if isinstance(r, complex):
        raise ValueError
    return r


def _floor(x):
    return x if isinstance(x, int) else math.floor(x)


def _sgn(x):
    return (x > 0) - (x < 0)


def _round(x, n=0):
    n = int(n)
    if n >= 0:
        r = math.floor(abs(x) * 10 ** n + 0.5)
        if n:
            r = r / 10 ** n
    else:
        r = math.floor(abs(x) / 10 ** -n + 0.5) * 10 ** -n
    return -r if x < 0 else r


def _log10(x):
    return math.log(x) / math.log(10)


def _mid(s, a, n=None):
    a = int(a) - 1
    if a < 0:
        raise ValueError
    return s[a:] if n is None else s[a: a + max(0, int(n))]


def _instr(a, b, c=None):
    if c is None:
        return a.find(b) + 1
    st = int(a) - 1
    if st < 0:
        raise ValueError
    return b.find(c, st) + 1


def _asc(s):
    if not s:
        raise ValueError
    return ord(s[0])


def _strs(n, c):
    return (c[0] if isinstance(c, str) else chr(int(c))) * int(n)


def _bin(n):
    n = int(n)
    if n < 0:
        raise ValueError
    s = ""
    while True:
        s = "01"[n & 1] + s
        n >>= 1
        if not n:
            return s


def pyerr(e):
    """BASIC message for a Python exception raised while running."""
    if isinstance(e, ZeroDivisionError):
        return "Division by zero"
    if isinstance(e, IndexError):
        return "Subscript out of range"
    if isinstance(e, KeyError):
        k = e.args[0] if e.args else "?"
        return "Array not dimensioned: %s" % str(k).rstrip("(")
    if isinstance(e, TypeError):
        return "Type mismatch"
    if isinstance(e, OverflowError):
        return "Overflow"
    if isinstance(e, MemoryError):
        return "Out of memory"
    if isinstance(e, RuntimeError) and "recursion" in str(e):
        return "Too many nested calls"
    if isinstance(e, ValueError):
        return "Illegal function call"
    return "%s: %s" % (type(e).__name__, e)


# ---- tokenizer --------------------------------------------------------------
def _idch(c):
    return c.isalpha() or c.isdigit() or c == "_"


def tokenize(s, ln=None):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == " " or c == "\t":
            i += 1
            continue
        if c == "'":
            break
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            while j < n and s[j].isdigit():
                j += 1
            flt = False
            if j < n and s[j] == ".":
                flt = True
                j += 1
                while j < n and s[j].isdigit():
                    j += 1
            if j < n and s[j] in "eE":
                k = j + 1
                if k < n and s[k] in "+-":
                    k += 1
                if k < n and s[k].isdigit():
                    flt = True
                    j = k
                    while j < n and s[j].isdigit():
                        j += 1
            t = s[i:j]
            out.append(("num", float(t) if flt else int(t)))
            i = j
            continue
        if c == "&" and i + 2 < n and s[i + 1] in "hHbBoO" and _idch(s[i + 2]):
            base = {"h": 16, "b": 2, "o": 8}[s[i + 1].lower()]
            j = i + 2
            while j < n and _idch(s[j]):
                j += 1
            try:
                out.append(("num", int(s[i + 2: j], base)))
            except ValueError:
                raise BasicError("Bad number", ln)
            i = j
            continue
        if c == '"':
            j = i + 1
            buf = ""
            while True:
                if j >= n:
                    raise BasicError("Missing closing \"", ln)
                if s[j] == '"':
                    if j + 1 < n and s[j + 1] == '"':
                        buf += '"'
                        j += 2
                        continue
                    break
                buf += s[j]
                j += 1
            out.append(("str", buf))
            i = j + 1
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and _idch(s[j]):
                j += 1
            if j < n and s[j] == "$":
                j += 1
            w = s[i:j]
            u = w.upper()
            if u == "REM":
                break
            if u in KW:
                out.append(("kw", u))
            else:
                out.append(("id", w.lower()))
            i = j
            continue
        two = s[i: i + 2]
        if two in ("<=", ">=", "<>"):
            out.append(("op", two))
            i += 2
            continue
        if c == "?":
            out.append(("kw", "PRINT"))
            i += 1
            continue
        if c in "+-*/\\^()=<>,;:&":
            out.append(("op", c))
            i += 1
            continue
        raise BasicError("Unexpected character '%s'" % c, ln)
    out.append(EOL)
    return out


# ---- I/O for the host (tests) -----------------------------------------------
class HostIO:
    """Default I/O: print to stdout (or collect), input from a list."""

    def __init__(self, inputs=None, echo=True):
        self.inputs = list(inputs or ())
        self.text = []
        self.echo = echo
        self.calls = []

    def out(self, s):
        self.text.append(s)
        if self.echo:
            print(s, end="")

    def input(self, prompt):
        self.out(prompt)
        if not self.inputs:
            raise KeyboardInterrupt
        s = self.inputs.pop(0)
        self.out(s + "\n")
        return s

    check = None  # nothing to poll for a break key

    def cls(self):
        self.calls.append(("cls",))

    def sleep(self, s):
        pass

    def inkey(self):
        return ""

    def waitkey(self):
        return self.inputs.pop(0) if self.inputs else "ENTER"

    def keydown(self, k):
        return False

    def rgb(self, r, g, b):
        return ((int(r) & 0xF8) << 8) | ((int(g) & 0xFC) << 3) | (int(b) >> 3)

    def __getattr__(self, name):
        # graphics: gcls pset line box circle gprint -> recorded
        def f(*a):
            self.calls.append((name,) + a)

        return f


# ---- compiler + runtime -----------------------------------------------------
class Sub:
    def __init__(self, name, params, func, line):
        self.name = name
        self.params = params
        self.func = func
        self.line = line
        self.locals = set(params)
        if func:
            self.locals.add(name)
        self.entry = None
        self.init = None


class Basic:
    def __init__(self, io=None):
        self.io = io or HostIO()
        self.G = {}
        self.gnames = set()
        self.L = {}
        self.gs = []
        self.ret = None
        self.col = 0
        self.color = None
        self.brk = None
        self.bi = self._builtins()
        self.load("")

    # ---- output helpers ---------------------------------------------------
    def out(self, s):
        self.io.out(s)
        i = s.rfind("\n")
        self.col = len(s) - i - 1 if i >= 0 else self.col + len(s)

    def _tab(self, n):
        n = int(n) - 1
        return " " * (n - self.col) if n > self.col else ""

    def _builtins(self):
        io = self.io
        R = random.random
        return {
            "abs": (abs, 1, 1), "int": (_floor, 1, 1), "fix": (int, 1, 1), "sgn": (_sgn, 1, 1),
            "sqr": (math.sqrt, 1, 1), "sin": (math.sin, 1, 1), "cos": (math.cos, 1, 1),
            "tan": (math.tan, 1, 1), "atn": (math.atan, 1, 1), "atan2": (math.atan2, 2, 2),
            "exp": (math.exp, 1, 1), "log": (math.log, 1, 1), "log10": (_log10, 1, 1),
            "round": (_round, 1, 2), "min": (min, 1, 99), "max": (max, 1, 99),
            "pi": (lambda: math.pi, 0, 0), "rnd": (lambda x=0: R(), 0, 1),
            "len": (len, 1, 1), "left$": (lambda s, n: s[: max(0, int(n))], 2, 2),
            "right$": (lambda s, n: s[max(0, len(s) - int(n)):] if int(n) > 0 else "", 2, 2),
            "mid$": (_mid, 2, 3), "instr": (_instr, 2, 3),
            "ucase$": (lambda s: s.upper(), 1, 1), "lcase$": (lambda s: s.lower(), 1, 1),
            "trim$": (lambda s: s.strip(), 1, 1), "ltrim$": (lambda s: s.lstrip(), 1, 1),
            "rtrim$": (lambda s: s.rstrip(), 1, 1), "str$": (fmtnum, 1, 1),
            "val": (lambda s: tonum(s) or 0, 1, 1), "chr$": (lambda n: chr(int(n)), 1, 1),
            "asc": (_asc, 1, 1), "space$": (lambda n: " " * int(n), 1, 1),
            "string$": (_strs, 2, 2), "hex$": (lambda n: "%X" % int(n), 1, 1), "bin$": (_bin, 1, 1),
            "spc": (lambda n: " " * int(n), 1, 1), "tab": (self._tab, 1, 1),
            "timer": (lambda: time.ticks_ms() / 1000, 0, 0), "ticks": (time.ticks_ms, 0, 0),
            "inkey$": (io.inkey, 0, 0), "waitkey$": (io.waitkey, 0, 0),
            "keydown": (lambda k: -1 if io.keydown(k) else 0, 1, 1), "rgb": (io.rgb, 3, 3),
            "band": (lambda a, b: int(a) & int(b), 2, 2), "bor": (lambda a, b: int(a) | int(b), 2, 2),
            "bxor": (lambda a, b: int(a) ^ int(b), 2, 2),
        }

    # ---- loading ------------------------------------------------------------
    def load(self, src):
        """Compile a program (replaces the current one)."""
        self.code = []
        self.lnos = []
        self.labels = {}
        self.dlab = {}
        self.data = []
        self.subs = {}
        self.fix = []
        self.blocks = []
        self.cur = None
        self.imm = False
        self.lastk = None
        self.gnames = set()
        self.G.clear()
        toks = []
        try:
            for i, line in enumerate(src.split("\n")):
                toks.append((i + 1, tokenize(line, i + 1)))
            self._prescan(toks)
            for ln, ts in toks:
                self._line(ln, ts)
            del toks
            if self.blocks:
                b = self.blocks[-1]
                raise BasicError("%s without %s" % (b["k"], CLOSE[b["k"]]), b["ln"])
            self.ln = None
            self._emit(self._i_end)
            self._resolve()
        except BasicError as e:
            e.compile = True
            self.code = [self._i_end]
            self.lnos = [None]
            self.subs = {}
            raise
        for s in self.subs.values():
            s.init = dict((n, _dflt(n)) for n in s.locals if n[-1] != "(")

    def _prescan(self, toks):
        for ln, ts in toks:
            p = 0
            if ts[0][0] == "num":
                p = 1
            elif ts[0][0] == "id" and ts[1] == COLON:
                p = 2
            t = ts[p]
            if t[0] == "kw" and t[1] in ("SUB", "FUNCTION"):
                nm = ts[p + 1]
                if nm[0] != "id":
                    raise BasicError("Name expected", ln)
                if nm[1] in self.subs or nm[1] in self.bi:
                    raise BasicError("Duplicate name: %s" % nm[1], ln)
                params = []
                q = p + 2
                if ts[q] == LPAR:
                    q += 1
                    while ts[q] != RPAR:
                        if ts[q][0] != "id":
                            raise BasicError("Parameter name expected", ln)
                        params.append(ts[q][1])
                        q += 1
                        if ts[q] == COMMA:
                            q += 1
                        elif ts[q] != RPAR:
                            raise BasicError("Syntax error", ln)
                self.subs[nm[1]] = Sub(nm[1], params, t[1] == "FUNCTION", ln)

    def _resolve(self):
        for kind, cell, label, ln in self.fix:
            tab = self.labels if kind == "c" else self.dlab
            if label not in tab:
                raise BasicError("Label not found: %s" % label, ln)
            cell[0] = tab[label]
        self.fix = []

    # ---- token cursor -------------------------------------------------------
    def _peek(self):
        return self.t[self.p]

    def _next(self):
        t = self.t[self.p]
        if t is not EOL:
            self.p += 1
        return t

    def _acc(self, tok):
        if self.t[self.p] == tok:
            self.p += 1
            return True
        return False

    def _acck(self, k):
        return self._acc(("kw", k))

    def _exp(self, tok, what=None):
        if not self._acc(tok):
            self._err("%s expected" % (what or "'%s'" % tok[1]))

    def _err(self, msg="Syntax error"):
        raise BasicError(msg, self.ln)

    def _end_stmt(self):
        t = self.t[self.p]
        return t is EOL or t == COLON or t == ("kw", "ELSE")

    def _name(self):
        t = self._next()
        if t[0] != "id":
            self._err("Name expected")
        return t[1]

    def _emit(self, f):
        self.code.append(f)
        self.lnos.append(self.ln)
        return len(self.code) - 1

    def _here(self):
        return len(self.code)

    # ---- lines and statements ---------------------------------------------
    def _line(self, ln, ts):
        self.ln = ln
        self.t = ts
        self.p = 0
        t0 = ts[0]
        if not self.imm:
            if t0[0] == "num" and isinstance(t0[1], int):
                self._label(str(t0[1]))
                self.p = 1
            elif t0[0] == "id" and ts[1] == COLON and t0[1] not in self.subs:
                self._label(t0[1])
                self.p = 2
        while True:
            if self._peek() is EOL:
                return
            self._stmt()
            if self._peek() is EOL:
                return
            if not self._acc(COLON):
                self._err()

    def _label(self, name):
        if name in self.labels:
            self._err("Duplicate label: %s" % name)
        self.labels[name] = self._here()
        self.dlab[name] = len(self.data)

    def _stmt(self):
        t = self._next()
        if t[0] == "kw":
            f = getattr(self, "_s_" + t[1], None)
            if f is None:
                self._err()
            f()
        elif t[0] == "id":
            if t[1] in self.subs and self._peek() != ("op", "="):
                self._call_stmt(t[1])
            else:
                self._assign(t[1])
        else:
            self._err()

    def _inline(self):
        # statements of a single-line IF, up to ELSE / end of line
        while True:
            t = self._peek()
            if t[0] == "num":
                self.p += 1
                self._goto(str(t[1]))
            else:
                self._stmt()
            if self._acc(COLON) and not (self._peek() is EOL or self._peek() == ("kw", "ELSE")):
                continue
            return

    # ---- variables ----------------------------------------------------------
    def _is_local(self, name):
        return self.cur is not None and name in self.cur.locals

    def _scal(self, name):
        if self._is_local(name):
            it = self

            def g():
                return it.L[name]

            def s(v):
                it.L[name] = v

            return g, s
        G = self.G
        if name not in G:
            G[name] = _dflt(name)
        self.gnames.add(name)

        def g():
            return G[name]

        def s(v):
            G[name] = v

        return g, s

    def _hidden(self, tag):
        name = "\x00%s%d" % (tag, len(self.code))
        if self.cur is not None:
            self.cur.locals.add(name)
        return self._scal(name)

    def _arr(self, name, idx):
        key = name + "("
        loc = self._is_local(key)
        it = self
        G = self.G
        last = idx[-1]
        first = idx[:-1]

        def cont():
            a = it.L[key] if loc else G[key]
            for i in first:
                a = a[_ix(i())]
            return a

        if not first:
            if loc:
                def g():
                    return it.L[key][_ix(last())]
            else:
                def g():
                    return G[key][_ix(last())]
        else:
            def g():
                return cont()[_ix(last())]

        def s(v):
            cont()[_ix(last())] = v

        return g, s

    def _lval(self):
        name = self._name()
        if self._peek() == LPAR:
            idx = self._args()
            if not idx:
                self._err("Subscript expected")
            g, s = self._arr(name, idx)
        else:
            g, s = self._scal(name)
        return g, s, name

    def _assign(self, name):
        if self._peek() == LPAR:
            idx = self._args()
            if not idx:
                self._err("Subscript expected")
            _, s = self._arr(name, idx)
            self._exp(("op", "="))
            e = self._expr()

            def f():
                s(e())
        else:
            self._exp(("op", "="))
            e = self._expr()
            if self._is_local(name):
                it = self

                def f():
                    it.L[name] = e()
            else:
                g, s = self._scal(name)
                G = self.G

                def f():
                    G[name] = e()
        self._emit(f)

    # ---- expressions --------------------------------------------------------
    def _expr(self):
        a = self._and()
        while True:
            if self._acck("OR"):
                a = _logic("OR", a, self._and())
            elif self._acck("XOR"):
                a = _logic("XOR", a, self._and())
            else:
                return a

    def _and(self):
        a = self._not()
        while self._acck("AND"):
            a = _logic("AND", a, self._not())
        return a

    def _not(self):
        if self._acck("NOT"):
            a = self._not()
            return lambda: 0 if a() else -1
        return self._cmp()

    def _cmp(self):
        a = self._cat()
        t = self._peek()
        if t[0] == "op" and t[1] in ("=", "<>", "<", ">", "<=", ">="):
            self.p += 1
            a = _compare(t[1], a, self._cat())
        return a

    def _cat(self):
        a = self._add()
        while self._acc(("op", "&")):
            b = self._add()
            a = _concat(a, b)
        return a

    def _add(self):
        a = self._modl()
        while True:
            t = self._peek()
            if t == ("op", "+"):
                self.p += 1
                a = _arith("+", a, self._modl())
            elif t == ("op", "-"):
                self.p += 1
                a = _arith("-", a, self._modl())
            else:
                return a

    def _modl(self):
        a = self._idv()
        while self._acck("MOD"):
            a = _arith("MOD", a, self._idv())
        return a

    def _idv(self):
        a = self._mul()
        while self._acc(("op", "\\")):
            a = _arith("\\", a, self._mul())
        return a

    def _mul(self):
        a = self._unary()
        while True:
            t = self._peek()
            if t == ("op", "*") or t == ("op", "/"):
                self.p += 1
                a = _arith(t[1], a, self._unary())
            else:
                return a

    def _unary(self):
        if self._acc(("op", "-")):
            a = self._unary()
            k = self.lastk
            if k is not None and k[0] is a:
                return self._k(-k[1])
            return lambda: -a()
        if self._acc(("op", "+")):
            return self._unary()
        return self._pow()

    def _pow(self):
        a = self._prim()
        while self._acc(("op", "^")):
            if self._acc(("op", "-")):
                b = self._prim()
                b = _neg(b)
            else:
                b = self._prim()
            a = _arith("^", a, b)
        return a

    def _k(self, v):
        f = _const(v)
        self.lastk = (f, v)
        return f

    def _args(self):
        self._exp(LPAR)
        args = []
        if self._acc(RPAR):
            return args
        while True:
            args.append(self._expr())
            if self._acc(RPAR):
                return args
            self._exp(COMMA, "',' or ')'")

    def _prim(self):
        t = self._next()
        k = t[0]
        if k == "num" or k == "str":
            return self._k(t[1])
        if t == LPAR:
            e = self._expr()
            self._exp(RPAR)
            return e
        if k == "id":
            name = t[1]
            paren = self._peek() == LPAR
            sub = self.subs.get(name)
            if sub is not None and sub.func and (paren or self.cur is not sub):
                args = self._args() if paren else []
                return self._fcall(sub, args)
            if sub is not None and not sub.func:
                self._err("SUB %s has no value" % name)
            b = self.bi.get(name)
            if b is not None:
                args = self._args() if paren else []
                if not b[1] <= len(args) <= b[2]:
                    self._err("Wrong number of arguments: %s" % name)
                return _bcall(b[0], args)
            if paren:
                idx = self._args()
                if not idx:
                    self._err("Subscript expected")
                return self._arr(name, idx)[0]
            return self._scal(name)[0]
        if t is EOL:
            self._err("Expression expected")
        self._err("Syntax error: %s" % (t[1],))

    def _fcall(self, sub, args):
        if len(args) != len(sub.params):
            self._err("Wrong number of arguments: %s" % sub.name)
        it = self

        def f():
            return it.call(sub, [a() for a in args])

        return f

    # ---- runtime ------------------------------------------------------------
    def call(self, sub, args):
        # The run loop is repeated here instead of calling exec(): every
        # Python frame per BASIC call level costs C stack (recursion depth).
        L = sub.init.copy()
        for n, v in zip(sub.params, args):
            L[n] = v
        sv = (self.L, self.gs, self.ret)
        self.L = L
        self.gs = []
        self.ret = None
        code = self.code
        pc = sub.entry
        try:  # one handler only: each one costs C stack
            while True:
                r = code[pc]()
                if r is None:
                    pc += 1
                elif r < 0:
                    break
                else:
                    pc = r
        except BaseException as e:
            self.L, self.gs, self.ret = sv
            if isinstance(e, KeyboardInterrupt):
                if self.brk is None:
                    self.brk = self.lnos[pc]
                raise
            raise self._fault(e, pc)
        r = self.ret
        if r is None and sub.func:
            r = L[sub.name]
        self.L, self.gs, self.ret = sv
        return r

    def _fault(self, e, pc):
        """Exception to raise for e caught at instruction pc."""
        if isinstance(e, BasicError):
            if e.line is None:
                e.line = self.lnos[pc]
            return e
        if isinstance(e, _End):
            return e
        return BasicError(pyerr(e), self.lnos[pc])

    def exec(self, pc):
        code = self.code
        try:
            while True:
                r = code[pc]()
                if r is None:
                    pc += 1
                elif r < 0:
                    return
                else:
                    pc = r
        except BasicError as e:
            if e.line is None:
                e.line = self.lnos[pc]
            raise
        except _End:
            raise
        except KeyboardInterrupt:
            if self.brk is None:
                self.brk = self.lnos[pc]
            raise
        except Exception as e:
            raise BasicError(pyerr(e), self.lnos[pc])

    def reset(self):
        G = self.G
        G.clear()
        for n in self.gnames:
            G[n] = _dflt(n)
        self.L = {}
        self.gs = []
        self.ret = None
        self.dp = 0
        self.col = 0
        self.color = None
        self.brk = None

    def run(self):
        """Run the program from the top.  Raises BasicError on errors and
        KeyboardInterrupt on break (self.brk = line)."""
        self.reset()
        try:
            self.exec(0)
        except _End:
            pass

    def immediate(self, src):
        """Compile and run one line (direct mode).  Variables, SUBs and
        FUNCTIONs of the loaded program are available."""
        start = len(self.code)
        self.imm = True
        self.blocks = []
        self.cur = None
        self.brk = None
        compiled = False
        try:
            self._line(None, tokenize(src))
            if self.blocks:
                k = self.blocks[-1]["k"]
                self._err("%s without %s" % (k, CLOSE[k]))
            self._emit(_ret)
            self._resolve()
            compiled = True
            self.L = {}
            self.gs = []
            try:
                self.exec(start)
            except _End:
                pass
        except BasicError as e:
            e.compile = not compiled
            raise
        finally:
            self.imm = False
            self.fix = []
            del self.code[start:]
            del self.lnos[start:]

    def _i_end(self):
        raise _End

    # ---- jumps ----------------------------------------------------------------
    def _jmp(self, cell, back=False):
        chk = self.io.check
        if back and chk is not None:
            def f():
                chk()
                return cell[0]
        else:
            def f():
                return cell[0]
        return f

    def _goto(self, label):
        cell = [0]
        self.fix.append(("c", cell, label, self.ln))
        self._emit(self._jmp(cell, True))

    # ---- statements -----------------------------------------------------------
    def _s_LET(self):
        self._assign(self._name())

    def _s_PRINT(self):
        items = []
        nl = True
        while not self._end_stmt():
            if self._acc(("op", ";")):
                nl = False
                continue
            if self._acc(COMMA):
                items.append(None)
                nl = False
                continue
            items.append(self._expr())
            nl = True
        it = self

        def f():
            for e in items:
                if e is None:
                    it.out(" " * (ZONE - it.col % ZONE))
                else:
                    v = e()
                    it.out(v if isinstance(v, str) else fmtnum(v))
            if nl:
                it.out("\n")

        self._emit(f)

    def _s_INPUT(self):
        prompt = ""
        qm = True
        t = self._peek()
        if t[0] == "str":
            self.p += 1
            prompt = t[1]
            if self._acc(COMMA):
                qm = False
            else:
                self._exp(("op", ";"), "';'")
        lv = [self._lval()]
        while self._acc(COMMA):
            lv.append(self._lval())
        it = self
        pr = prompt + ("? " if qm else "")

        def f():
            while True:
                s = it.io.input(pr)
                it.col = 0
                parts = s.split(",") if len(lv) > 1 else [s]
                vals = []
                if len(parts) == len(lv):
                    for (g, st, nm), p in zip(lv, parts):
                        v = p if nm[-1] == "$" else tonum(p)
                        if v is None:
                            break
                        vals.append(v)
                if len(vals) == len(lv):
                    break
                it.out("?Redo from start\n")
            for (g, st, nm), v in zip(lv, vals):
                st(v)

        self._emit(f)

    def _s_IF(self):
        c = self._expr()
        if self._acck("GOTO"):
            self._cond_goto(c)
            return
        self._exp(("kw", "THEN"), "THEN")
        if self._peek() is EOL:
            cell = [0]
            self._emit(_jz(c, cell))
            self.blocks.append({"k": "IF", "next": cell, "ends": [], "ln": self.ln})
            return
        depth = len(self.blocks)
        t = self._peek()
        if t[0] == "num" and self.t[self.p + 1] is EOL:
            self.p += 1
            self._cond_goto(c, str(t[1]))
            return
        els = [0]
        self._emit(_jz(c, els))
        self._inline()
        if self._acck("ELSE"):
            end = [0]
            self._emit(self._jmp(end))
            els[0] = self._here()
            self._inline()
            end[0] = self._here()
        else:
            els[0] = self._here()
        if len(self.blocks) != depth:
            self._err("Block not closed on the IF line")

    def _cond_goto(self, c, label=None):
        if label is None:
            t = self._next()
            if t[0] not in ("id", "num"):
                self._err("Label expected")
            label = str(t[1])
        cell = [0]
        self.fix.append(("c", cell, label, self.ln))
        chk = self.io.check or _nop

        def f():
            if c():
                chk()
                return cell[0]

        self._emit(f)

    def _top(self, kind, what):
        if not self.blocks or self.blocks[-1]["k"] != kind:
            self._err("%s without %s" % (what, kind))
        return self.blocks[-1]

    def _s_ELSEIF(self):
        b = self._top("IF", "ELSEIF")
        if b["next"] is None:
            self._err("ELSEIF after ELSE")
        end = [0]
        b["ends"].append(end)
        self._emit(self._jmp(end))
        b["next"][0] = self._here()
        c = self._expr()
        self._exp(("kw", "THEN"), "THEN")
        cell = [0]
        self._emit(_jz(c, cell))
        b["next"] = cell

    def _s_ELSE(self):
        b = self._top("IF", "ELSE")
        if b["next"] is None:
            self._err("Duplicate ELSE")
        end = [0]
        b["ends"].append(end)
        self._emit(self._jmp(end))
        b["next"][0] = self._here()
        b["next"] = None

    def _s_ENDIF(self):
        b = self._top("IF", "END IF")
        self.blocks.pop()
        h = self._here()
        if b["next"] is not None:
            b["next"][0] = h
        for c in b["ends"]:
            c[0] = h

    def _s_END(self):
        t = self._peek()
        if t[0] == "kw" and t[1] in ("IF", "SUB", "FUNCTION", "SELECT", "WHILE"):
            self.p += 1
            if t[1] == "IF":
                self._s_ENDIF()
            elif t[1] == "WHILE":
                self._s_WEND()
            elif t[1] == "SELECT":
                self._end_select()
            else:
                self._end_sub(t[1])
            return
        self._emit(self._i_end)

    def _s_STOP(self):
        self._emit(_stop)

    def _s_FOR(self):
        name = self._name()
        g, s = self._scal(name)
        self._exp(("op", "="))
        a = self._expr()
        self._exp(("kw", "TO"), "TO")
        b = self._expr()
        st = self._expr() if self._acck("STEP") else None
        ex = [0]
        if self.cur is None:
            # top level: limit and step kept in the closure, variable in G
            fast = [0, 1]
            G = self.G

            def init():
                v = a()
                lim = b()
                stp = st() if st else 1
                G[name] = v
                fast[0] = lim
                fast[1] = stp
                if (v > lim) if stp >= 0 else (v < lim):
                    return ex[0]

            self._emit(init)
            self.blocks.append({"k": "FOR", "var": name, "top": self._here(), "exit": ex,
                                "acc": None, "fast": fast, "ln": self.ln})
            return
        gl, sl = self._hidden("l")
        gs, ss = self._hidden("s")

        def init():
            v = a()
            lim = b()
            stp = st() if st else 1
            s(v)
            sl(lim)
            ss(stp)
            if (v > lim) if stp >= 0 else (v < lim):
                return ex[0]

        self._emit(init)
        self.blocks.append({"k": "FOR", "var": name, "top": self._here(), "exit": ex,
                            "acc": (g, s, gl, gs), "fast": None, "ln": self.ln})

    def _s_NEXT(self):
        while True:
            b = self._top("FOR", "NEXT")
            if self._peek()[0] == "id":
                nm = self._name()
                if nm != b["var"]:
                    self._err("NEXT %s does not match FOR %s" % (nm, b["var"]))
            self.blocks.pop()
            if b["fast"] is not None:
                self._emit(_next_fast(self.G, b["var"], b["fast"], b["top"], self.io.check))
            else:
                self._emit(_next_ins(b["acc"], b["top"], self.io.check or _nop))
            b["exit"][0] = self._here()
            if not self._acc(COMMA):
                return

    def _s_WHILE(self):
        top = self._here()
        c = self._expr()
        ex = [0]
        self._emit(_jz(c, ex))
        self.blocks.append({"k": "WHILE", "top": [top], "exit": ex, "ln": self.ln})

    def _s_WEND(self):
        b = self._top("WHILE", "WEND")
        self.blocks.pop()
        self._emit(self._jmp(b["top"], True))
        b["exit"][0] = self._here()

    def _s_DO(self):
        top = self._here()
        ex = [0]
        if self._acck("WHILE"):
            self._emit(_jz(self._expr(), ex))
        elif self._acck("UNTIL"):
            self._emit(_jnz(self._expr(), ex))
        self.blocks.append({"k": "DO", "top": [top], "exit": ex, "ln": self.ln})

    def _s_LOOP(self):
        b = self._top("DO", "LOOP")
        self.blocks.pop()
        top = b["top"]
        chk = self.io.check or _nop
        if self._acck("WHILE"):
            c = self._expr()

            def f():
                if c():
                    chk()
                    return top[0]
        elif self._acck("UNTIL"):
            c = self._expr()

            def f():
                if not c():
                    chk()
                    return top[0]
        else:
            f = self._jmp(top, True)
        self._emit(f)
        b["exit"][0] = self._here()

    def _s_EXIT(self):
        t = self._next()
        k = t[1] if t[0] == "kw" else None
        if k in ("SUB", "FUNCTION"):
            if self.cur is None or self.cur.func != (k == "FUNCTION"):
                self._err("EXIT %s outside %s" % (k, k))
            self._emit(_ret)
            return
        if k not in ("FOR", "WHILE", "DO", "SELECT"):
            self._err("EXIT FOR / WHILE / DO / SUB / FUNCTION expected")
        for b in reversed(self.blocks):
            if b["k"] == k:
                self._emit(self._jmp(b["exit"]))
                return
            if b["k"] in ("SUB", "FUNCTION"):
                break
        self._err("EXIT %s outside %s" % (k, k))

    def _s_SELECT(self):
        self._exp(("kw", "CASE"), "CASE")
        e = self._expr()
        g, s = self._hidden("c")

        def f():
            s(e())

        self._emit(f)
        self.blocks.append({"k": "SELECT", "g": g, "next": None, "ends": [], "first": True,
                            "exit": [0], "ln": self.ln})

    def _s_CASE(self):
        b = self._top("SELECT", "CASE")
        if not b["first"]:
            end = [0]
            b["ends"].append(end)
            self._emit(self._jmp(end))
        b["first"] = False
        if b["next"] is not None:
            b["next"][0] = self._here()
            b["next"] = None
        if self._acck("ELSE"):
            return
        tests = []
        while True:
            if self._acck("IS"):
                t = self._next()
                if t[0] != "op" or t[1] not in ("=", "<>", "<", ">", "<=", ">="):
                    self._err("Comparison expected")
                tests.append((t[1], self._expr(), None))
            else:
                v = self._expr()
                if self._acck("TO"):
                    tests.append(("TO", v, self._expr()))
                else:
                    tests.append(("=", v, None))
            if not self._acc(COMMA):
                break
        cell = [0]
        b["next"] = cell
        g = b["g"]

        def f():
            x = g()
            for op, v, v2 in tests:
                if op == "TO":
                    if v() <= x <= v2():
                        return None
                elif _cmp1(op, x, v()):
                    return None
            return cell[0]

        self._emit(f)

    def _end_select(self):
        b = self._top("SELECT", "END SELECT")
        self.blocks.pop()
        h = self._here()
        if b["next"] is not None:
            b["next"][0] = h
        for c in b["ends"]:
            c[0] = h
        b["exit"][0] = h

    def _s_SUB(self):
        self._def("SUB")

    def _s_FUNCTION(self):
        self._def("FUNCTION")

    def _def(self, kind):
        if self.imm:
            self._err("%s in direct mode" % kind)
        if self.cur is not None or self.blocks:
            self._err("%s inside a block" % kind)
        sub = self.subs[self._name()]
        if self._acc(LPAR):
            while not self._acc(RPAR):
                self._next()
        skip = [0]
        self._emit(self._jmp(skip))
        sub.entry = self._here()
        self.cur = sub
        self.blocks.append({"k": kind, "skip": skip, "ln": self.ln})

    def _end_sub(self, kind):
        b = self._top(kind, "END " + kind)
        self.blocks.pop()
        self._emit(_ret)
        b["skip"][0] = self._here()
        self.cur = None

    def _call_stmt(self, name):
        sub = self.subs[name]
        if sub.func:
            self._err("FUNCTION %s used as a statement" % name)
        if self._peek() == LPAR:
            args = self._args()
        elif self._end_stmt():
            args = []
        else:
            args = [self._expr()]
            while self._acc(COMMA):
                args.append(self._expr())
        if len(args) != len(sub.params):
            self._err("Wrong number of arguments: %s" % name)
        it = self

        def f():
            it.call(sub, [a() for a in args])

        self._emit(f)

    def _s_CALL(self):
        name = self._name()
        if name not in self.subs:
            self._err("Unknown SUB: %s" % name)
        self._call_stmt(name)

    def _s_RETURN(self):
        it = self
        if self.cur is not None and self.cur.func and not self._end_stmt():
            e = self._expr()

            def f():
                it.ret = e()
                return -1
        else:
            in_sub = self.cur is not None

            def f():
                if it.gs:
                    return it.gs.pop()
                if in_sub:
                    return -1
                raise BasicError("RETURN without GOSUB")
        self._emit(f)

    def _s_GOTO(self):
        t = self._next()
        if t[0] not in ("id", "num"):
            self._err("Label expected")
        self._goto(str(t[1]))

    def _s_GOSUB(self):
        t = self._next()
        if t[0] not in ("id", "num"):
            self._err("Label expected")
        cell = [0]
        self.fix.append(("c", cell, str(t[1]), self.ln))
        it = self
        back = self._here() + 1

        def f():
            if len(it.gs) > 200:
                raise BasicError("Too many nested GOSUBs")
            it.gs.append(back)
            return cell[0]

        self._emit(f)

    def _s_DIM(self):
        while True:
            name = self._name()
            if self._peek() == LPAR:
                dims = self._args()
                if not dims:
                    self._err("Subscript expected")
                key = name + "("
                if self.cur is not None:
                    self.cur.locals.add(key)
                loc = self.cur is not None
                it = self
                G = self.G
                d = _dflt(name)

                def f(dims=dims, key=key, loc=loc, d=d):
                    a = _mkarr([_ix(x()) for x in dims], d)
                    if loc:
                        it.L[key] = a
                    else:
                        G[key] = a

                self._emit(f)
            else:
                if self.cur is not None:
                    self.cur.locals.add(name)
                self._scal(name)
            if not self._acc(COMMA):
                return

    def _s_LOCAL(self):
        if self.cur is None:
            self._err("LOCAL outside SUB / FUNCTION")
        while True:
            self.cur.locals.add(self._name())
            if not self._acc(COMMA):
                return

    def _s_CONST(self):
        self._assign(self._name())

    def _s_DATA(self):
        while True:
            neg = self._acc(("op", "-"))
            t = self._next()
            if t[0] == "num":
                self.data.append(-t[1] if neg else t[1])
            elif t[0] == "str" and not neg:
                self.data.append(t[1])
            else:
                self._err("Number or string expected in DATA")
            if not self._acc(COMMA):
                return

    def _s_READ(self):
        lv = [self._lval()]
        while self._acc(COMMA):
            lv.append(self._lval())
        it = self

        def f():
            d = it.data
            for g, s, nm in lv:
                if it.dp >= len(d):
                    raise BasicError("Out of DATA")
                s(d[it.dp])
                it.dp += 1

        self._emit(f)

    def _s_RESTORE(self):
        cell = [0]
        if not self._end_stmt():
            t = self._next()
            self.fix.append(("d", cell, str(t[1]), self.ln))
        it = self

        def f():
            it.dp = cell[0]

        self._emit(f)

    def _s_RANDOMIZE(self):
        e = None if self._end_stmt() else self._expr()

        def f():
            random.seed(int(e()) if e else time.ticks_ms())

        self._emit(f)

    def _s_SWAP(self):
        g1, s1, _ = self._lval()
        self._exp(COMMA)
        g2, s2, _ = self._lval()

        def f():
            x = g1()
            s1(g2())
            s2(x)

        self._emit(f)

    def _s_CLS(self):
        it = self

        def f():
            it.io.cls()
            it.col = 0

        self._emit(f)

    def _s_SLEEP(self):
        e = self._expr()
        io = self.io

        def f():
            io.sleep(e())

        self._emit(f)

    # ---- graphics -------------------------------------------------------------
    def _gargs(self, n, m):
        a = [] if self._end_stmt() else [self._expr()]
        while self._acc(COMMA):
            a.append(self._expr())
        if not n <= len(a) <= m:
            self._err("Wrong number of arguments")
        return a

    def _gfx(self, meth, n, m, cpos):
        args = self._gargs(n, m)
        it = self
        io = self.io

        def f():
            v = [a() for a in args]
            while len(v) < m:
                v.append(None)
            if v[cpos] is None:
                v[cpos] = it.color
            getattr(io, meth)(*v)

        self._emit(f)

    def _s_GCLS(self):
        args = self._gargs(0, 1)
        io = self.io

        def f():
            io.gcls(args[0]() if args else None)

        self._emit(f)

    def _s_PSET(self):
        self._gfx("pset", 2, 3, 2)

    def _s_LINE(self):
        self._gfx("line", 4, 5, 4)

    def _s_BOX(self):
        self._gfx("box", 4, 6, 4)

    def _s_CIRCLE(self):
        self._gfx("circle", 3, 5, 3)

    def _s_GPRINT(self):
        self._gfx("gprint", 3, 4, 3)

    def _s_COLOR(self):
        e = self._expr()
        it = self

        def f():
            it.color = e()

        self._emit(f)


# ---- expression node factories -------------------------------------------------
def _ret():
    return -1


def _stop():
    raise KeyboardInterrupt


def _const(v):
    return lambda: v


def _neg(a):
    return lambda: -a()


def _nop():
    pass


def _next_fast(G, name, fast, top, chk):
    if chk is None:
        def f():
            stp = fast[1]
            v = G[name] + stp
            G[name] = v
            if (v <= fast[0]) if stp >= 0 else (v >= fast[0]):
                return top
    else:
        def f():
            stp = fast[1]
            v = G[name] + stp
            G[name] = v
            if (v <= fast[0]) if stp >= 0 else (v >= fast[0]):
                chk()
                return top
    return f


def _next_ins(acc, top, chk):
    g, s, gl, gs = acc

    def f():
        stp = gs()
        v = g() + stp
        s(v)
        if (v <= gl()) if stp >= 0 else (v >= gl()):
            chk()
            return top

    return f


def _jz(c, cell):
    def f():
        if not c():
            return cell[0]

    return f


def _jnz(c, cell):
    def f():
        if c():
            return cell[0]

    return f


def _logic(op, a, b):
    if op == "AND":
        return lambda: -1 if a() and b() else 0
    if op == "OR":
        return lambda: -1 if a() or b() else 0
    return lambda: -1 if (not a()) != (not b()) else 0


def _cmp1(op, x, y):
    if op == "=":
        return x == y
    if op == "<>":
        return x != y
    if op == "<":
        return x < y
    if op == ">":
        return x > y
    if op == "<=":
        return x <= y
    return x >= y


def _compare(op, a, b):
    if op == "=":
        return lambda: -1 if a() == b() else 0
    if op == "<>":
        return lambda: -1 if a() != b() else 0
    if op == "<":
        return lambda: -1 if a() < b() else 0
    if op == ">":
        return lambda: -1 if a() > b() else 0
    if op == "<=":
        return lambda: -1 if a() <= b() else 0
    return lambda: -1 if a() >= b() else 0


def _concat(a, b):
    return lambda: tostr(a()) + tostr(b())


def _arith(op, a, b):
    if op == "+":
        return lambda: a() + b()
    if op == "-":
        return lambda: a() - b()
    if op == "*":
        return lambda: a() * b()
    if op == "/":
        return lambda: a() / b()
    if op == "\\":
        return lambda: _idiv(a(), b())
    if op == "MOD":
        return lambda: _mod(a(), b())
    return lambda: _pow(a(), b())


def _bcall(fn, args):
    n = len(args)
    if n == 0:
        return fn
    if n == 1:
        a = args[0]
        return lambda: fn(a())
    if n == 2:
        a, b = args
        return lambda: fn(a(), b())
    return lambda: fn(*[x() for x in args])


def _mkarr(dims, d):
    if len(dims) == 1:
        return [d] * (dims[0] + 1)
    return [_mkarr(dims[1:], d) for _ in range(dims[0] + 1)]
