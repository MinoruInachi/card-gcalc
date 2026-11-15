# Equation: polynomial roots, simultaneous linear equations, numeric solver.
from nc import hal, gfx, ui, state, storage
from bcd import D
from nc.calc import numfmt
from nc.calc.dec import DC, num, isreal, ZERO, ONE
from nc.calc.gridedit import Grid, result_list, form, fmt, evaluate
from nc.calc.expr import CalcError
from nc.i18n import T

_VARS = "xyzt"
_SUP = {2: "²", 3: "³", 4: "⁴"}


def _load():
    d = storage.load_json("equation.json", None) or {}
    return d


def _save(d):
    storage.save_json("equation.json", d)


# ---- polynomial --------------------------------------------------------------
class _CoefModel:
    def __init__(self, names, vals):
        self.names = names
        self.vals = vals

    def rows(self):
        return 1

    def cols(self):
        return len(self.names)

    def get(self, r, c):
        return self.vals[c]

    def set(self, r, c, v):
        self.vals[c] = ZERO if v is None else v

    def col_title(self, c):
        return self.names[c]

    def row_label(self, r):
        return ""


def _poly_text(deg):
    names = "abcde"[: deg + 1]
    parts = []
    for i, n in enumerate(names):
        p = deg - i
        if p == 0:
            parts.append(n)
        elif p == 1:
            parts.append(n + "x")
        else:
            parts.append(n + "x" + _SUP[p])
    return "+".join(parts) + "=0"


def polynomial(data):
    i = ui.menu("Polynomial degree", ["Degree 2  ax²+bx+c=0", "Degree 3  ax³+...=0", "Degree 4  ax⁴+...=0"])
    if i is None:
        return
    deg = i + 2
    key = "poly%d" % deg
    vals = [num(v) for v in (data.get(key) or ([1] + [0] * deg))]
    names = list("abcde"[: deg + 1])
    m = _CoefModel(names, vals)

    def fkey(fk, g):
        if fk == 0:
            _poly_solve(vals)
        elif fk == 4:
            for j in range(len(vals)):
                vals[j] = ZERO
        return None

    g = Grid("Polynomial", m, colw=(ui.W - 4) // len(names), labelw=4, advance="right",
             keys=["Solve", "", "", "", "Clear", ""], on_fkey=fkey, header=_poly_text(deg))
    try:
        g.run()
    finally:
        data[key] = [v if not isinstance(v, DC) else ZERO for v in vals]
        _save(data)


def _poly_solve(vals):
    from nc.calc import poly

    vals = [num(v) for v in vals]
    if vals[0] == 0:
        ui.error("Leading coefficient\nmust not be 0")
        return
    try:
        rs = poly.roots(vals)
    except Exception as e:
        ui.error(str(e))
        return
    exact = [None] * len(rs)
    if len(vals) == 3:
        ex = poly.exact_quadratic(*vals)
        if ex:
            exact = poly.match_exact(rs, ex)
    else:
        for j, z in enumerate(rs):
            if isinstance(z, D):
                exact[j] = numfmt.exact(z)
    rows = []
    for j, z in enumerate(rs):
        e = exact[j]
        if e is not None and e == fmt(z):
            e = None
        rows.append(("x%s" % "₁₂₃₄"[j], z, e))
    if len(vals) == 3:
        a, b, c = vals
        d = b * b - 4 * a * c
        rows.append(("Δ=b²-4ac", d))
        vx = -b / (2 * a)
        vy = c - b * b / (4 * a)
        rows.append(("vertex x", vx, numfmt.exact(vx) if isinstance(vx, D) else None))
        if isinstance(a, D):
            rows.append(("min y" if a > 0 else "max y", vy, numfmt.exact(vy) if isinstance(vy, D) else None))
    result_list("Roots", rows, header=_coef_header(vals))


def _coef_header(vals):
    return " ".join("%s=%s" % ("abcde"[j], fmt(v)) for j, v in enumerate(vals))


# ---- linear systems ----------------------------------------------------------
class _SysModel:
    def __init__(self, n, A, b):
        self.n = n
        self.A = A
        self.b = b

    def rows(self):
        return self.n

    def cols(self):
        return self.n + 1

    def get(self, r, c):
        return self.b[r] if c == self.n else self.A[r][c]

    def set(self, r, c, v):
        v = ZERO if v is None else v
        if c == self.n:
            self.b[r] = v
        else:
            self.A[r][c] = v

    def col_title(self, c):
        return "=" if c == self.n else _VARS[c]

    def row_label(self, r):
        return str(r + 1)


def linear(data):
    i = ui.menu("Unknowns", ["2 unknowns (x, y)", "3 unknowns (x, y, z)", "4 unknowns (x, y, z, t)"])
    if i is None:
        return
    n = i + 2
    key = "lin%d" % n
    saved = data.get(key)
    if saved:
        A, b = saved
        A = [[num(v) for v in row] for row in A]
        b = [num(v) for v in b]
    else:
        A = [[ZERO] * n for _ in range(n)]
        b = [ZERO] * n
    m = _SysModel(n, A, b)
    head = "+".join("%s%s" % ("abcd"[j], _VARS[j]) for j in range(n)) + "=k"

    def fkey(fk, g):
        if fk == 0:
            _lin_solve(n, A, b)
        elif fk == 4:
            for r in range(n):
                b[r] = ZERO
                for c in range(n):
                    A[r][c] = ZERO
        return None

    g = Grid("Linear system", m, colw=(ui.W - 14) // (n + 1), labelw=14, advance="right",
             keys=["Solve", "", "", "", "Clear", ""], on_fkey=fkey, header=head)
    try:
        g.run()
    finally:
        data[key] = [[[ZERO if isinstance(v, DC) else v for v in row] for row in A],
                     [ZERO if isinstance(v, DC) else v for v in b]]
        _save(data)


def _lin_solve(n, A, b):
    from nc.calc import linalg

    try:
        st, x = linalg.solve(A, b)
    except Exception as e:
        ui.error(str(e))
        return
    if st == "none":
        ui.message("Linear system", "No solution", color=gfx.ERR)
        return
    if st == "inf":
        ui.message("Linear system", "Infinitely many solutions")
        return
    rows = []
    for j in range(n):
        v = x[j]
        e = numfmt.exact(v) if isinstance(v, D) else None
        rows.append((_VARS[j], v, e))
    result_list("Solution", rows)


# ---- solver --------------------------------------------------------------------
def _balance(s):
    n = s.count("(") - s.count(")")
    return s + ")" * n if n > 0 else s


def _split_eq(s):
    """'lhs=rhs' -> (lhs, rhs) with balanced parentheses."""
    depth = 0
    cand = []
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "=":
            prev = s[i - 1] if i else ""
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if prev in "<>!" or nxt == "=":
                continue
            cand.append((depth, i))
    if not cand:
        return _balance(s), "0"
    cand.sort()
    i = cand[0][1]
    return _balance(s[:i]), _balance(s[i + 1:])


_E7 = D("1e-7")
_E9 = D("1e-9")


def find_roots(f, lo, hi, n=400, maxroots=12):
    """All roots of f in [lo, hi]: sign changes + touching zeros."""
    from nc.calc import fn as F

    lo = num(lo)
    hi = num(hi)
    xs = [lo + (hi - lo) * k / n for k in range(n + 1)]
    ys = []
    for x in xs:
        try:
            y = f(x)
            if not isreal(y):
                y = None
        except Exception:
            y = None
        ys.append(y)
    roots = []

    def add(r):
        for q in roots:
            if abs(q - r) <= _E7 * max(ONE, abs(r)):
                return
        roots.append(r)

    for k in range(n):
        a, b = ys[k], ys[k + 1]
        if a is None or b is None:
            continue
        if a == 0:
            add(xs[k])
            continue
        if (a < 0) != (b < 0):
            try:
                r = F.bracket_root(f, xs[k], xs[k + 1])
            except Exception:
                r = None
            if r is not None:
                add(r)
        if len(roots) >= maxroots:
            break
    if ys[n] == 0:
        add(xs[n])
    # touching roots (double roots): look near local extrema of f
    def touch(a, b):
        try:
            x0, fx = F.minimize(lambda x: abs(f(x)), a, b)
            if not isreal(fx):
                return
            if fx < _E9 * (1 + abs(x0)):
                # refine: a double root is a simple root of f'
                h = (b - a) / 4
                try:
                    r = F.bracket_root(lambda x: F.deriv(f, x), x0 - h, x0 + h, 80)
                    if r is not None and abs(f(r)) <= fx:
                        x0 = r
                except Exception:
                    pass
                add(F.clean(x0))
        except Exception:
            pass

    for k in range(1, n):
        a, b, c = ys[k - 1], ys[k], ys[k + 1]
        if a is None or b is None or c is None:
            continue
        if (b - a) * (c - b) <= 0 and abs(b) < abs(a) + abs(c):
            touch(xs[k - 1], xs[k + 1])
    if n > 1:
        touch(xs[0], xs[2])
        touch(xs[n - 2], xs[n])
    roots.sort()
    return roots


def solver(data):
    fields = [["Equation", data.get("solve_eq", "x²-2=0")],
              ["Lower x", data.get("solve_lo", "-10")],
              ["Upper x", data.get("solve_hi", "10")]]
    sel = 0
    while True:
        r = form("Solver (in x)", fields, submit="Solve", sel=sel)
        data["solve_eq"], data["solve_lo"], data["solve_hi"] = fields[0][1], fields[1][1], fields[2][1]
        _save(data)
        if r is None:
            return
        eq = fields[0][1].strip()
        if not eq:
            continue
        lhs, rhs = _split_eq(eq)
        ctx = state.ctx()
        try:
            f = ctx.function("(%s)-(%s)" % (lhs, rhs or "0"))
            lo = evaluate(fields[1][1])
            hi = evaluate(fields[2][1])
        except Exception as e:
            ui.error(str(e))
            continue
        if not (isreal(lo) and isreal(hi)) or lo >= hi:
            ui.error("Need lower < upper")
            sel = 1
            continue
        ui.busy("Solving...")
        roots = find_roots(f, lo, hi)
        if not roots:
            ui.message("Solver", ["No solution in", "[%s, %s]" % (fmt(lo), fmt(hi))], color=gfx.ERR)
            continue
        rows = []
        for j, x in enumerate(roots):
            ex = numfmt.exact(x) if isinstance(x, D) else None
            rows.append(("x%d" % (j + 1), x, ex if ex and ex != fmt(x) else None))
        result_list("Solutions", rows, header=eq)


def run():
    data = _load()
    sel = 0
    while True:
        i = ui.menu("Equation", ["Polynomial", "Linear system", "Solver  f(x)=g(x)"], sel)
        if i is None:
            break
        sel = i
        if i == 0:
            polynomial(data)
        elif i == 1:
            linear(data)
        else:
            solver(data)
    _save(data)
