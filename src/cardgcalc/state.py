# Shared calculator state: variables (A-Z, x, Ans ...) and the evaluation
# context.  Variables persist across apps and reboots (/data/vars.json).
from cardgcalc import settings, storage
from cardgcalc.calc.expr import Context

_ctx = None


def ctx():
    global _ctx
    if _ctx is None:
        from bcd import D
        from cardgcalc.calc.dec import DC, simp

        v = storage.load_json("vars.json", {}) or {}
        for k in list(v):
            x = v[k]
            if isinstance(x, list) and len(x) == 2:  # old complex format
                v[k] = simp(DC(D(x[0]), D(x[1])))
            elif isinstance(x, (int, float)) and not isinstance(x, bool):
                v[k] = D(x)
            elif not hasattr(x, "imag") and not isinstance(x, D):
                del v[k]
        _ctx = Context(v)
        from cardgcalc.calc import frac

        for k, x in (storage.load_json("vars_q.json", {}) or {}).items():
            if isinstance(x, list) and len(x) == 2 and x[1]:
                q = frac.make(int(x[0]), int(x[1]))
                if isinstance(q, frac.Q):
                    _ctx.exact[k] = q
    _ctx.angle = settings.get("angle")
    _ctx.complex = settings.get("complex")
    return _ctx


def save_vars():
    if _ctx is None:
        return
    from bcd import D
    from cardgcalc.calc.dec import DC

    out = {}
    for k, v in _ctx.vars.items():
        if isinstance(v, (D, DC)):
            out[k] = v
    storage.save_json("vars.json", out)
    # exact fractions of the variables (Calc), while they still match
    q = {}
    for k in _ctx.exact:
        x = _ctx.exact_var(k)
        if x is _ctx.exact[k]:
            q[k] = [x.n, x.d]
    storage.save_json("vars_q.json", q)
