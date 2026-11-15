# Calculator expression engine.
#
# Calculator notation (as typed on card-gcalc) is parsed by a small recursive
# descent parser and translated into Python source which is then compiled
# with eval().  Supported notation:
#
#   numbers      12  3.5  .5  1.2E-3
#   operators    + - × ÷ * / ^ ** %(postfix) !(factorial) ² ³ ⁻¹ x^superscripts
#   implicit ×   2x  3(x+1)  (a)(b)  2sin(x)  xy
#   functions    sin( cos( ... sin⁻¹( √( ∛( ln( log( abs( ...
#   constants    π e i Ans
#   variables    any single letter except e and i (A, B, x, y, θ ...)
#   special      ∫(f,a,b)  d/dx(f,a)  Σ(f,k,a,b)  ∏(f,k,a,b)  solve(f,guess)
#   store        expr→A        (also  A=expr  at top level)
#
# A function argument written in terms of x (or k for Σ) becomes a lambda.
# Numbers are decimal (bcd.D, 15 significant digits): every literal becomes a
# named D constant so that 0.1 is exactly one tenth.
from bcd import D
from nc.calc import fn as F

SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-"}

# name -> python callable name in the namespace
FUNCS = {
    "sin": "sin", "cos": "cos", "tan": "tan",
    "asin": "asin", "acos": "acos", "atan": "atan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "asinh": "asinh", "acosh": "acosh", "atanh": "atanh",
    "sec": "sec", "csc": "csc", "cot": "cot",
    "ln": "ln", "log": "log", "log2": "log2", "exp": "exp",
    "sqrt": "sqrt", "√": "sqrt", "cbrt": "cbrt", "∛": "cbrt", "root": "root",
    "abs": "abs_", "floor": "floor", "ceil": "ceil", "round": "round_", "int": "int_",
    "ipart": "int_", "fpart": "fpart", "frac": "fpart", "sign": "sign", "sgn": "sign",
    "mod": "mod", "gcd": "gcd", "lcm": "lcm", "nPr": "nPr", "nCr": "nCr", "perm": "nPr", "comb": "nCr",
    "min": "min_", "max": "max_", "rand": "rand", "randint": "randint", "random": "rand",
    "gamma": "gamma", "erf": "erf", "erfc": "erfc", "hypot": "hypot", "atan2": "atan2",
    "deg": "todeg", "rad": "torad", "fact": "fact",
    "re": "re", "im": "im", "real": "re", "imag": "im", "conj": "conj", "arg": "arg", "angle": "arg",
    "mean": "mean", "sum": "sum_", "isprime": "isprime",
}
INVERSE = {"sin": "asin", "cos": "acos", "tan": "atan", "sinh": "asinh", "cosh": "acosh", "tanh": "atanh"}
# Special forms: first argument is a function of a bound variable.
SPECIAL = {"∫": "integ", "integ": "integ", "d/dx": "deriv", "deriv": "deriv", "Σ": "sigma", "∑": "sigma",
           "∏": "prod", "solve": "solve"}
CONSTS = {"π": "pi", "pi": "pi", "e": "e", "i": "i", "Ans": "v_Ans", "ans": "v_Ans", "∞": "inf"}

_NAMES = sorted(list(FUNCS) + list(SPECIAL) + list(CONSTS), key=lambda s: -len(s))
_IDCHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZθ_0123456789"


class CalcError(Exception):
    pass


# literal text -> constant name, constant name -> D value
LITS = {}
LITVAL = {}


def _lit(text):
    nm = LITS.get(text)
    if nm is None:
        nm = "_k%d" % len(LITS)
        LITS[text] = nm
        LITVAL[nm] = D(text)
    return nm


def var_py(name):
    if name == "θ":
        return "v_th"
    return "v_" + name


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == " ":
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            # exponent: E or ᴇ followed by [+-⁻]digit
            if j < n and s[j] in "Eᴇ":
                k = j + 1
                if k < n and s[k] in "+-⁻":
                    k += 1
                if k < n and s[k].isdigit():
                    while k < n and s[k].isdigit():
                        k += 1
                    num = s[i:j] + "e" + s[j + 1 : k].replace("⁻", "-")
                    toks.append(("num", num))
                    i = k
                    continue
            num = s[i:j]
            if num.count(".") > 1:
                raise CalcError("Syntax error")
            toks.append(("num", num))
            i = j
            continue
        if s.startswith("d/dx", i):
            toks.append(("special", "deriv"))
            i += 4
            continue
        if c in "∫Σ∑∏":
            toks.append(("special", SPECIAL[c]))
            i += 1
            continue
        if c in _IDCHARS or c in "π∞":
            j = i
            while j < n and (s[j] in _IDCHARS):
                j += 1
            if j == i:
                j = i + 1
            word = s[i:j]
            _split_word(word, toks)
            i = j
            # sin⁻¹ notation
            if s.startswith("⁻¹", i) and toks and toks[-1][0] == "func":
                f = toks[-1][1]
                for k, v in INVERSE.items():
                    if FUNCS[k] == f:
                        toks[-1] = ("func", FUNCS[v])
                        i += 2
                        break
            continue
        if c in "√∛":
            toks.append(("func", FUNCS[c]))
            i += 1
            continue
        if s.startswith("⁻¹", i):
            toks.append(("post", "inv"))
            i += 2
            continue
        if c in SUP:
            j = i
            while j < n and s[j] in SUP:
                j += 1
            toks.append(("sup", "".join(SUP[ch] for ch in s[i:j])))
            i = j
            continue
        if s.startswith("**", i):
            toks.append(("op", "^"))
            i += 2
            continue
        if c in "+-×÷*/^(),!%→=<>":
            if c == "×":
                c = "*"
            elif c == "÷":
                c = "/"
            elif c == "−":
                c = "-"
            toks.append(("op", c))
            i += 1
            continue
        if c == "−":
            toks.append(("op", "-"))
            i += 1
            continue
        raise CalcError("Syntax error: '%s'" % c)
    return toks


def _split_word(word, toks):
    """Split an identifier run into known names / single-letter variables."""
    p = 0
    n = len(word)
    while p < n:
        if word[p].isdigit():
            j = p
            while j < n and word[j].isdigit():
                j += 1
            toks.append(("num", word[p:j]))
            p = j
            continue
        for name in _NAMES:
            if word.startswith(name, p):
                if name in FUNCS:
                    toks.append(("func", FUNCS[name]))
                elif name in SPECIAL:
                    toks.append(("special", SPECIAL[name]))
                else:
                    toks.append(("const", CONSTS[name]))
                p += len(name)
                break
        else:
            ch = word[p]
            if ch == "_":
                raise CalcError("Syntax error")
            toks.append(("var", ch))
            p += 1


# ---------------------------------------------------------------------------
# Parser -> python source
# ---------------------------------------------------------------------------
class _Parser:
    def __init__(self, toks):
        self.t = toks
        self.p = 0
        self.vars = set()

    def peek(self):
        if self.p < len(self.t):
            return self.t[self.p]
        return (None, None)

    def take(self):
        tok = self.peek()
        self.p += 1
        return tok

    def accept(self, kind, val=None):
        k, v = self.peek()
        if k == kind and (val is None or v == val):
            self.p += 1
            return True
        return False

    def expect_close(self):
        # Missing closing parentheses at the end are allowed.
        if self.accept("op", ")"):
            return
        if self.peek()[0] is None:
            return
        raise CalcError("Syntax error")

    def parse_top(self):
        """Top level: expr [→ var]  |  var = expr"""
        # A=expr  (assignment) if form is <var> '=' ...
        if (
            len(self.t) >= 2
            and self.t[0][0] == "var"
            and self.t[1] == ("op", "=")
        ):
            name = self.t[0][1]
            self.p = 2
            e = self.expr()
            if self.peek()[0] is not None:
                raise CalcError("Syntax error")
            return e, name
        e = self.expr()
        store = None
        if self.accept("op", "→"):
            k, v = self.take()
            if k != "var":
                raise CalcError("Syntax error")
            store = v
        if self.peek()[0] is not None:
            raise CalcError("Syntax error")
        return e, store

    def expr(self):
        return self.compare()

    def compare(self):
        a = self.sum()
        k, v = self.peek()
        if k == "op" and v in "<>=":
            self.p += 1
            if v == "=":
                op = "=="
            else:
                op = v
                if self.accept("op", "="):
                    op += "="
            b = self.sum()
            return "(1 if %s%s%s else 0)" % (a, op, b)
        return a

    def sum(self):
        a = self.term()
        while True:
            k, v = self.peek()
            if k == "op" and v in "+-":
                self.p += 1
                b = self.term()
                a = "(%s%s%s)" % (a, v, b)
            else:
                return a

    def _starts_primary(self):
        k, v = self.peek()
        if k in ("num", "var", "const", "func", "special"):
            return True
        if k == "op" and v == "(":
            return True
        return False

    def term(self):
        a = self.unary()
        while True:
            k, v = self.peek()
            if k == "op" and v in "*/":
                self.p += 1
                b = self.unary()
                if v == "/":
                    a = "div(%s,%s)" % (a, b)
                else:
                    a = "(%s*%s)" % (a, b)
            elif self._starts_primary():
                b = self.power()
                a = "(%s*%s)" % (a, b)
            else:
                return a

    def unary(self):
        if self.accept("op", "-"):
            return "(-%s)" % self.unary()
        if self.accept("op", "+"):
            return self.unary()
        return self.power()

    def power(self):
        a = self.postfix()
        if self.accept("op", "^"):
            b = self.unary()
            return "pw(%s,%s)" % (a, b)
        return a

    def postfix(self):
        a = self.primary()
        while True:
            k, v = self.peek()
            if k == "op" and v == "!":
                self.p += 1
                a = "fact(%s)" % a
            elif k == "op" and v == "%":
                self.p += 1
                a = "(%s/100)" % a
            elif k == "sup":
                self.p += 1
                a = "pw(%s,%s)" % (a, v)
            elif k == "post" and v == "inv":
                self.p += 1
                a = "div(1,%s)" % a
            else:
                return a

    def args(self):
        out = []
        if self.accept("op", ")"):
            return out
        while True:
            out.append(self.expr())
            if self.accept("op", ","):
                continue
            self.expect_close()
            return out

    def primary(self):
        k, v = self.take()
        if k == "num":
            try:
                nm = _lit(v)
            except (ValueError, OverflowError):
                raise CalcError("Math error")
            self.vars.add("#" + nm)  # bound by Context._bind
            return nm
        if k == "var":
            self.vars.add(v)
            return var_py(v)
        if k == "const":
            if v == "v_Ans":
                self.vars.add("Ans")
            return v
        if k == "func":
            if self.accept("op", "("):
                a = self.args()
                return "%s(%s)" % (v, ",".join(a))
            # function applied without parentheses: sin 30, √2
            return "%s(%s)" % (v, self.power())
        if k == "special":
            return self.special(v)
        if k == "op" and v == "(":
            e = self.expr()
            self.expect_close()
            return "(%s)" % e
        if k is None:
            raise CalcError("Syntax error")
        raise CalcError("Syntax error")

    def special(self, name):
        if not self.accept("op", "("):
            raise CalcError("Syntax error")
        # Parse first argument separately so we can make it a lambda.
        inner = _Parser(self.t)
        inner.p = self.p
        body = inner.expr()
        self.p = inner.p
        rest = []
        while self.accept("op", ","):
            rest.append(self.peek())
            rest_expr_start = self.p
            rest[-1] = (rest_expr_start, self.expr())
        self.expect_close()
        if name in ("sigma", "prod"):
            # Σ(f, k, a, b)  or  Σ(f, a, b) with variable x
            if len(rest) == 3:
                tok = self.t[rest[0][0]]
                if tok[0] != "var":
                    raise CalcError("Syntax error")
                bv = tok[1]
                a, b = rest[1][1], rest[2][1]
            elif len(rest) == 2:
                bv = "x"
                a, b = rest[0][1], rest[1][1]
            else:
                raise CalcError("Argument error")
        else:
            bv = "x"
            if name == "integ" and len(rest) == 3:
                tok = self.t[rest[0][0]]
                if tok[0] == "var":
                    bv = tok[1]
                rest = rest[1:]
            want = {"integ": 2, "deriv": 1, "solve": (0, 1, 2)}[name]
            if isinstance(want, int) and len(rest) != want:
                if not (name == "deriv" and len(rest) == 0):
                    raise CalcError("Argument error")
            args = [r[1] for r in rest]
            inner.vars.discard(bv)
            self.vars |= inner.vars
            if name == "deriv" and not args:
                args = [var_py("x")]
                self.vars.add("x")
            return "%s(lambda %s:%s%s)" % (
                name, var_py(bv), body, "".join("," + a for a in args))
        inner.vars.discard(bv)
        self.vars |= inner.vars
        return "%s(lambda %s:%s,%s,%s)" % (name, var_py(bv), body, a, b)


def translate(src):
    """Calculator notation -> (python_source, store_var, used_vars)."""
    toks = tokenize(src)
    if not toks:
        raise CalcError("Syntax error")
    p = _Parser(toks)
    code, store = p.parse_top()
    return code, store, p.vars


def translate_expr(src):
    toks = tokenize(src)
    if not toks:
        raise CalcError("Syntax error")
    p = _Parser(toks)
    e = p.expr()
    if p.peek()[0] is not None:
        raise CalcError("Syntax error")
    return e, p.vars


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
class Context:
    """Evaluation context: variables + settings."""

    def __init__(self, variables=None, angle="rad", complex_mode=False):
        self.vars = variables if variables is not None else {}
        self.angle = angle
        self.complex = complex_mode
        self._ns = None
        self._ns_key = None

    def namespace(self):
        key = (self.angle, self.complex)
        if self._ns is None or self._ns_key != key:
            self._ns = F.namespace(self.angle, self.complex)
            self._ns_key = key
        return self._ns

    def _bind(self, ns, used):
        for v in used:
            if v[0] == "#":
                ns[v[1:]] = LITVAL[v[1:]]
            else:
                ns[var_py(v)] = self.vars.get(v, F.ZERO)

    def evaluate(self, src):
        """Evaluate a calculator line.  Stores into Ans and target var."""
        code, store, used = translate(src)
        ns = self.namespace()
        self._bind(ns, used)
        try:
            val = eval(code, ns)
        except CalcError:
            raise
        except ZeroDivisionError:
            raise CalcError("Math error: ÷0")
        except (ValueError, OverflowError):
            raise CalcError("Math error")
        except TypeError:
            raise CalcError("Argument error")
        except NameError as e:
            raise CalcError("Syntax error")
        val = F.check(val, self.complex)
        if store:
            self.vars[store] = val
        self.vars["Ans"] = val
        return val

    def function(self, src, var="x"):
        """Compile an expression of `var` into a Python callable f(v).

        The callable raises an exception for points outside the domain."""
        code, used = translate_expr(src)
        used.discard(var)
        ns = self.namespace()
        self._bind(ns, used)
        f = eval("lambda %s:%s" % (var_py(var), code), ns)
        return f

    def function2(self, src, v1="x", v2="y"):
        code, used = translate_expr(src)
        used.discard(v1)
        used.discard(v2)
        ns = self.namespace()
        self._bind(ns, used)
        return eval("lambda %s,%s:%s" % (var_py(v1), var_py(v2), code), ns)
