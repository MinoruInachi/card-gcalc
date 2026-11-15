# Matrix: matrices A..F (up to 6x6), editor and operations.
from nc import gfx, ui, storage
from bcd import D
from nc.calc import linalg, numfmt
from nc.calc.dec import DC, num, simp, ZERO
from nc.calc.gridedit import Grid, result_list, fmt, evaluate
from nc.i18n import T

NAMES = "ABCDEF"
MAXN = 6


def _enc(v):
    return v  # storage.save_json encodes D / DC


def _dec(v):
    if isinstance(v, str) and v.startswith("c:"):  # old complex format
        _, re, im = v.split(":")
        return simp(DC(D(re), D(im)))
    if isinstance(v, (int, float)):
        return D(v)
    return v


class Store:
    def __init__(self):
        d = storage.load_json("matrix.json", None) or {}
        self.m = {}
        for n in NAMES + "R":
            v = d.get(n)
            self.m[n] = [[_dec(x) for x in row] for row in v] if v else None

    def save(self):
        storage.save_json("matrix.json", {n: ([[_enc(x) for x in row] for row in v] if v else None)
                                          for n, v in self.m.items()})


def _dimstr(m):
    return "%d×%d" % linalg.dims(m) if m else "empty"


class _MatModel:
    def __init__(self, name, mat):
        self.name = name
        self.mat = mat

    def rows(self):
        return len(self.mat)

    def cols(self):
        return len(self.mat[0]) if self.mat else 0

    def get(self, r, c):
        return self.mat[r][c]

    def set(self, r, c, v):
        self.mat[r][c] = ZERO if v is None else v

    def col_title(self, c):
        return str(c + 1)

    def row_label(self, r):
        return str(r + 1)

    def cell_name(self, r, c):
        return "%s[%d,%d]" % (self.name, r + 1, c + 1)


def _ask_int(title, val, lo, hi):
    """Integer input; an empty entry keeps the default `val`."""
    s = ui.input_line(title, "", prompt=T("Enter = %d") % val)
    if s is None:
        return None
    if not s.strip():
        return val
    try:
        v = evaluate(s)
        if v != int(v):
            raise ValueError
        v = int(v)
    except Exception:
        ui.error("Integer required")
        return None
    if not lo <= v <= hi:
        ui.error(T("Range %d..%d") % (lo, hi))
        return None
    return v


def ask_dims(m):
    r0, c0 = linalg.dims(m) if m else (2, 2)
    r = _ask_int(T("Rows (1-%d)") % MAXN, r0, 1, MAXN)
    if r is None:
        return None
    c = _ask_int(T("Columns (1-%d)") % MAXN, c0, 1, MAXN)
    if c is None:
        return None
    out = linalg.zeros(r, c)
    if m:
        for i in range(min(r, len(m))):
            for j in range(min(c, len(m[0]))):
                out[i][j] = m[i][j]
    return out


def edit(st, name):
    m = st.m[name]
    if not m:
        m = ask_dims(None)
        if m is None:
            return
        st.m[name] = m
    model = _MatModel(name, m)

    def fkey(fk, g):
        if fk == 0:
            nm = ask_dims(model.mat)
            if nm is not None:
                model.mat = nm
                st.m[name] = nm
        elif fk == 1:
            r, c = linalg.dims(model.mat)
            if r == c or ui.confirm(T("Make square %d×%d?") % (r, r)):
                model.mat = linalg.identity(r)
                st.m[name] = model.mat
        elif fk == 2:
            if ui.confirm(T("Clear %s?") % name):
                r, c = linalg.dims(model.mat)
                model.mat = linalg.zeros(r, c)
                st.m[name] = model.mat
        elif fk == 3:
            g.exact = not g.exact
        elif fk == 4:
            operations(st, name)
            model.mat = st.m[name]
        elif fk == 5:
            if ui.confirm(T("Delete matrix %s?") % name):
                st.m[name] = None
                return "deleted"
        return None

    g = Grid(T("Matrix %s") % name, model, colw=54, labelw=14, advance="right",
             keys=["Dim", "Ident", "Zero", "Exact", "Ops", "Delete"], on_fkey=fkey)
    try:
        g.run()
    finally:
        st.save()


def view(st, mat, title):
    """Show a result matrix; F1 stores it into A..F."""
    model = _MatModel("R", mat)
    st.m["R"] = mat

    def fkey(fk, g):
        if fk == 0:
            t = pick(st, "Store result to", allow_empty=True, exclude_r=True)
            if t is not None:
                st.m[t] = linalg.copy(mat)
                st.save()
                ui.message("Stored", T("Result stored in %s") % t, color=gfx.OK)
                return "stored"
        elif fk == 1:
            g.exact = not g.exact
        return None

    g = Grid(title, model, colw=54, labelw=14, readonly=True, keys=["Store", "Exact"], on_fkey=fkey)
    g.exact = True
    g.run()


def pick(st, title, allow_empty=False, exclude_r=False, sel=0):
    names = [n for n in NAMES if allow_empty or st.m[n]]
    if not exclude_r and st.m.get("R"):
        names.append("R")
    if not names:
        ui.error("No matrices defined")
        return None
    items = [(T("Mat %s") % n if n != "R" else T("Result"), _dimstr(st.m[n])) for n in names]
    i = ui.menu(title, items, min(sel, len(items) - 1))
    if i is None:
        return None
    return names[i]


OPS = ("det(X)", "Inverse X⁻¹", "Transpose Xᵀ", "Rank", "RREF", "X + Y", "X - Y", "X × Y",
       "k × X", "X ^ n", "Solve X·v = Y", "Trace")


def operations(st, cur=None):
    sel0 = NAMES.find(cur) if cur else 0
    while True:
        i = ui.menu("Matrix operations", [o.replace("ᵀ", "T") for o in OPS])
        if i is None:
            return
        x = pick(st, "X = ?", sel=max(0, sel0))
        if x is None:
            continue
        X = st.m[x]
        try:
            if i == 0:
                v = linalg.det(X)
                _scalar(st, "det(%s)" % x, v)
            elif i == 1:
                view(st, linalg.inverse(X), "%s⁻¹" % x)
            elif i == 2:
                view(st, linalg.transpose(X), T("%s transposed") % x)
            elif i == 3:
                _scalar(st, "rank(%s)" % x, linalg.rank(X))
            elif i == 4:
                view(st, linalg.rref(X)[0], "rref(%s)" % x)
            elif i in (5, 6, 7, 10):
                y = pick(st, "Y = ?", sel=1)
                if y is None:
                    continue
                Y = st.m[y]
                if i == 5:
                    view(st, linalg.tidy(linalg.add(X, Y)), "%s+%s" % (x, y))
                elif i == 6:
                    view(st, linalg.tidy(linalg.sub(X, Y)), "%s-%s" % (x, y))
                elif i == 7:
                    view(st, linalg.mul(X, Y), "%s×%s" % (x, y))
                else:
                    if len(Y[0]) != 1:
                        ui.error("Y must be a column\nvector (n×1)")
                        continue
                    status, v = linalg.solve(X, [row[0] for row in Y])
                    if status == "none":
                        ui.message("Solve", "No solution", color=gfx.ERR)
                    elif status == "inf":
                        ui.message("Solve", "Infinitely many solutions")
                        view(st, v, "rref [%s|%s]" % (x, y))
                    else:
                        view(st, [[a] for a in v], "%s·v=%s" % (x, y))
            elif i == 8:
                k = ui.input_number("k")
                if k is None:
                    continue
                view(st, linalg.tidy(linalg.scale(X, k)), "k×%s" % x)
            elif i == 9:
                n = ui.input_number("n (integer)")
                if n is None:
                    continue
                view(st, linalg.power(X, n), "%s^%s" % (x, fmt(n)))
            elif i == 11:
                r, c = linalg.dims(X)
                if r != c:
                    raise linalg.MatrixError("Dimension error")
                _scalar(st, "trace(%s)" % x, sum((num(X[j][j]) for j in range(r)), ZERO))
        except linalg.MatrixError as e:
            ui.error(str(e))
        except Exception as e:
            ui.error(str(e) or "Math error")


def _scalar(st, label, v):
    ex = numfmt.exact(v) if isinstance(v, D) else None
    result_list(label, [(label, v, ex)])


def run():
    st = Store()
    sel = 0
    try:
        while True:
            items = [(T("Mat %s") % n, _dimstr(st.m[n])) for n in NAMES] + ["Operations..."]
            i = ui.menu("Matrix", items, sel)
            if i is None:
                break
            sel = i
            if i == len(NAMES):
                operations(st)
            else:
                edit(st, NAMES[i])
    finally:
        st.save()
