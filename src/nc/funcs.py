# Shared function definitions for the Graph and Table apps.
#
# Up to six functions Y1..Y6, each:
#   {"expr": str, "expr2": str, "enabled": bool, "type": "y" | "r" | "param"}
#     y     : y = f(x)            expr = f(x)
#     r     : polar r = f(θ)      expr = r(θ)
#     param : x = X(t), y = Y(t)  expr = X(t), expr2 = Y(t)
# plus the view window and the table settings.  Stored in /nc/funcs.json.
# All numbers (view window, table start/step, function values) are decimal
# (bcd.D) so that x steps such as 0.1 stay exact.
import bcd
from bcd import D
from nc import storage, state, settings
from nc.calc.dec import DC

N = 6
_FILE = "funcs.json"
_data = None

TYPES = ("y", "r", "param")
TYPE_NAMES = {"y": "y=f(x)", "r": "r=f(θ)", "param": "x(t),y(t)"}


def default_view():
    v = {"xmin": D(-10), "xmax": D(10), "ymin": D(-5), "ymax": D(5), "xscl": D(1), "yscl": D(1)}
    v.update(default_t())
    return v


def default_t():
    if settings.get("angle") == "deg":
        return {"tmin": D(0), "tmax": D(360), "tstep": D(3)}
    if settings.get("angle") == "grad":
        return {"tmin": D(0), "tmax": D(400), "tstep": D(3)}
    return {"tmin": D(0), "tmax": 2 * bcd.pi, "tstep": bcd.pi / 60}


def _defaults():
    fs = []
    for i in range(N):
        fs.append({"expr": "", "expr2": "", "enabled": True, "type": "y"})
    fs[0]["expr"] = "sin(x)"
    fs[1]["expr"] = "x²÷4-2"
    return {"funcs": fs, "view": default_view(), "table": {"start": D(0), "step": D(1)}}


def data():
    global _data
    if _data is None:
        d = storage.load_json(_FILE, None)
        base = _defaults()
        if isinstance(d, dict):
            fs = d.get("funcs")
            if isinstance(fs, list):
                for i in range(min(N, len(fs))):
                    if isinstance(fs[i], dict):
                        base["funcs"][i].update(fs[i])
            for k in ("view", "table"):
                if isinstance(d.get(k), dict):
                    for kk, vv in d[k].items():
                        if kk in base[k] and isinstance(vv, (D, int)) and not isinstance(vv, bool):
                            base[k][kk] = D(vv)
        _data = base
    return _data


def save():
    if _data is not None:
        storage.save_json(_FILE, _data)


def funcs():
    return data()["funcs"]


def view():
    return data()["view"]


def table():
    return data()["table"]


def label(i):
    f = funcs()[i]
    if f["type"] == "r":
        return "r%d" % (i + 1)
    if f["type"] == "param":
        return "P%d" % (i + 1)
    return "Y%d" % (i + 1)


def describe(i):
    """One-line description of function i, e.g. 'Y1=sin(x)'."""
    f = funcs()[i]
    if f["type"] == "param":
        return "X%d=%s, Y%d=%s" % (i + 1, f["expr"], i + 1, f["expr2"])
    return "%s=%s" % (label(i), f["expr"])


def is_set(i):
    f = funcs()[i]
    if f["type"] == "param":
        return bool(f["expr"].strip() and f["expr2"].strip())
    return bool(f["expr"].strip())


def active(kind=None):
    """Indices of enabled, non-empty functions (optionally of one type)."""
    out = []
    for i, f in enumerate(funcs()):
        if f["enabled"] and is_set(i) and (kind is None or f["type"] == kind):
            out.append(i)
    return out


def compile(i):
    """Compile function i.

    Returns f(x) for 'y', r(θ) for 'r', (X(t), Y(t)) for 'param'.
    Raises CalcError on a syntax error."""
    f = funcs()[i]
    ctx = state.ctx()
    t = f["type"]
    if t == "r":
        return ctx.function(f["expr"], "θ")
    if t == "param":
        return ctx.function(f["expr"], "t"), ctx.function(f["expr2"], "t")
    return ctx.function(f["expr"], "x")


_TINY = D("1e-12")


def real(v):
    """Function value as D, or None (undefined / non-real)."""
    if isinstance(v, D):
        return v
    if isinstance(v, DC):
        if abs(v.imag) > _TINY * max(1, abs(v.real)):
            return None
        return v.real
    if isinstance(v, bool):
        return D(int(v))
    if isinstance(v, int):
        return D(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            return None
        return D(v)
    if isinstance(v, complex):
        return real(DC(D(v.real), D(v.imag)))
    return None


def safe(f):
    """Wrap f so that it returns a D, or None outside its domain / for
    non-real values."""

    def g(x):
        try:
            return real(f(x))
        except Exception:
            return None

    return g


_UNIT = {"deg": 1, "grad": 2}


def polar(r, theta):
    """(x, y) of the polar point (r, θ) with θ in the current angle unit."""
    u = _UNIT.get(settings.get("angle"), 0)
    return r * bcd.cos(theta, u), r * bcd.sin(theta, u)
