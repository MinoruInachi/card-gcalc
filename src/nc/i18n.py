# UI translation.
#
#   from nc.i18n import T
#   T("Settings")  -> "設定" when the language setting is "ja"
#
# Strings are looked up by their exact English text in nc.lang_ja, which is
# generated from lang/*.tsv by tools/mklang.py.  The table is a pair of
# sorted constant tuples (kept in flash when frozen) searched by bisection,
# so it costs no RAM.  Untranslated strings are returned unchanged.
from nc import settings

LANGS = ("en", "ja")
LANG_NAMES = ("English", "日本語")
_mod = None


def lang():
    return settings.get("lang") or "en"


def T(s):
    if not s or settings.get("lang") != "ja" or not isinstance(s, str):
        return s
    r = _lookup(s)
    if r is None:
        # "Prefix: detail" -> translate the prefix only
        i = s.find(": ")
        if i > 0:
            r = _lookup(s[:i])
            if r is not None:
                return r + ": " + s[i + 2:]
        return s
    return r


def _lookup(s):
    global _mod
    if _mod is None:
        from nc import lang_ja as m

        _mod = m
    keys = _mod.KEYS
    lo = 0
    hi = len(keys) - 1
    while lo <= hi:
        mid = (lo + hi) >> 1
        k = keys[mid]
        if k == s:
            return _mod.VALS[mid]
        if k < s:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def Tf(fmt, *args):
    """Translate a format string, then apply % args."""
    return T(fmt) % args
