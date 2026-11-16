# Plugins: apps installed on the file system, without rebuilding the firmware.
#
# A plugin is a directory /plugins/<id>/ (or /sd/plugins/<id>/) holding
#   plugin.json          manifest (below)
#   <module>.py / .mpy   entry module: run() starts the app; optional
#                        open_file(path) opens a file from the Files app
#   ...                  any other modules or data files
#
# plugin.json
#   {"api": 1, "name": "BASIC", "name_ja": "BASIC", "version": "1.0",
#    "module": "basic", "glyph": "BAS", "color": [200, 90, 40],
#    "files": [".bas"], "description": "Structured BASIC interpreter"}
#
#   api          plugin API version it was written for (must be <= API)
#   name         home-screen label (name_ja: Japanese label)
#   module       entry module (default: the directory name)
#   icon         a built-in icon name (cardgcalc.icons.DRAW), or
#   glyph        1-4 characters drawn on the home tile (default: id)
#   color        tile colour [r, g, b]
#   files        extensions opened with open_file(path) from Files
#
# While a plugin runs, its directory is first on sys.path and `current` is
# its manifest (with "id" and "dir" added).  The plugin's own modules are
# unloaded when it returns.  Plugins use the card-gcalc modules directly
# (cardgcalc.hal, cardgcalc.gfx, cardgcalc.ui, cardgcalc.console, cardgcalc.editor, cardgcalc.runner, cardgcalc.storage,
# cardgcalc); see README.md "Plugins".
import gc
import json
import os
import sys
from cardgcalc import storage, settings

API = 1
current = None


def _dirs():
    ds = [storage.PLUGINS]
    if storage.sd_mounted():
        ds.append(storage.SD + "/plugins")
    return ds


def scan(all=False):
    """Installed plugins as manifest dicts (flash before SD; the first one
    with a given id wins).  Disabled plugins are left out unless all=True."""
    out = []
    seen = set()
    for d in _dirs():
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            if n in seen:
                continue
            pd = d + "/" + n
            try:
                with open(pd + "/plugin.json") as f:
                    m = json.load(f)
            except Exception:
                continue
            if not isinstance(m, dict):
                continue
            seen.add(n)
            m["id"] = n
            m["dir"] = pd
            if not m.get("module"):
                m["module"] = n
            try:
                m["ok"] = int(m.get("api", 1)) <= API
            except (TypeError, ValueError):
                m["ok"] = False
            out.append(m)
    off = settings.get("plugins_off") or ()
    for m in out:
        m["enabled"] = m["ok"] and m["id"] not in off
    if all:
        return out
    return [m for m in out if m["enabled"]]


def label(m):
    return m.get("name_" + (settings.get("lang") or "en")) or m.get("name") or m["id"]


def color(m):
    from cardgcalc.hal import rgb

    c = m.get("color")
    try:
        return rgb(int(c[0]), int(c[1]), int(c[2]))
    except Exception:
        return rgb(100, 100, 120)


def draw_icon(m, x, y, sel=False):
    from cardgcalc import gfx, icons

    icons.tile(x, y, color(m), sel)
    f = icons.DRAW.get(m.get("icon"))
    if f:
        f(gfx.fb(), x, y)
        return
    g = str(m.get("glyph") or m["id"][:3].upper())[:4]
    for name in ("large", "medium", "normal", "small"):
        fn = gfx.font(name)
        if fn.width(g) <= icons.S - 4:
            break
    fn.text(g, x + (icons.S - fn.width(g)) // 2, y + (icons.S - fn.h) // 2, gfx.WHITE)


def launch(m, func="run", *args):
    """Import the plugin's entry module and call func(*args).  Errors are
    shown on the screen.  Returns func's result (None on error)."""
    global current
    from cardgcalc import hal

    sys.path.insert(0, m["dir"])
    current = m
    gc.collect()
    try:
        __import__(m["module"])
        mod = sys.modules[m["module"]]
        return getattr(mod, func)(*args)
    except Exception as e:
        _show_error(m, e)
    finally:
        current = None
        try:
            sys.path.remove(m["dir"])
        except ValueError:
            pass
        _unload(m["dir"])
        hal.keyboard.clear_mods()
        gc.collect()


def _unload(d):
    for k in list(sys.modules):
        f = getattr(sys.modules[k], "__file__", None)
        if f and f.startswith(d + "/"):
            del sys.modules[k]


def _show_error(m, e):
    import io
    from cardgcalc import ui

    buf = io.StringIO()
    sys.print_exception(e, buf)
    sys.print_exception(e)
    ui.text_view(label(m) + ": Error", buf.getvalue().split("\n"))


def handler(path):
    """The enabled plugin that opens files like `path` (by extension), or None."""
    p = path.lower()
    for m in scan():
        for ext in m.get("files") or ():
            if p.endswith(ext.lower()):
                return m
    return None


def open_file(path):
    m = handler(path)
    if m is not None:
        launch(m, "open_file", path)


def translator(ja):
    """T() for a plugin: its own {English: Japanese} table first, then the
    card-gcalc table."""
    from cardgcalc.i18n import T

    def tr(s):
        if settings.get("lang") == "ja" and isinstance(s, str):
            r = ja.get(s)
            if r is not None:
                return r
            i = s.find(": ")  # "Prefix: detail" -> translate the prefix
            if i > 0 and s[:i] in ja:
                return ja[s[:i]] + ": " + s[i + 2:]
        return T(s)

    return tr


# ---- Settings > Plugins ---------------------------------------------------
def _remove(p):
    try:
        if os.stat(p)[0] & 0x4000:
            for f in os.listdir(p):
                _remove(p + "/" + f)
            os.rmdir(p)
        else:
            os.remove(p)
    except OSError:
        pass


def _info(m):
    from cardgcalc import ui
    from cardgcalc.i18n import T

    lines = [
        "%s %s" % (label(m), m.get("version", "")),
        m.get("description_" + (settings.get("lang") or "en")) or m.get("description", ""),
        "",
        "%s: %s" % (T("Folder"), m["dir"]),
        "%s: %s.run()" % (T("Module"), m["module"]),
        "API: %s%s" % (m.get("api", 1), "" if m["ok"] else "  (" + T("needs newer firmware") + ")"),
    ]
    if m.get("files"):
        lines.append("%s: %s" % (T("Opens"), " ".join(m["files"])))
    ui.text_view("Plugin", lines)


def manage():
    """Settings > Plugins: list, enable / disable, info, delete."""
    from cardgcalc import ui
    from cardgcalc.i18n import T

    sel = 0
    while True:
        ps = scan(True)
        if not ps:
            ui.message("Plugins", [T("No plugins installed."), storage.PLUGINS + "/<name>/plugin.json"])
            return
        items = [(label(m), ("on" if m["enabled"] else "off") if m["ok"] else "API") for m in ps]
        i = ui.menu("Plugins", items, min(sel, len(ps) - 1))
        if i is None:
            return
        sel = i
        m = ps[i]
        opts = ["Disable" if m["enabled"] else "Enable", "Info", "Delete"]
        if not m["ok"]:
            # needs newer firmware: it cannot be enabled
            opts = opts[1:]
        j = ui.menu(label(m), opts)
        if j is not None and not m["ok"]:
            j += 1
        if j == 0:
            off = list(settings.get("plugins_off") or ())
            if m["id"] in off:
                off.remove(m["id"])
            else:
                off.append(m["id"])
            settings.set("plugins_off", off)
        elif j == 1:
            _info(m)
        elif j == 2:
            if ui.confirm("Delete plugin?", m["dir"] + "\n" + T("Enter: yes   Esc: no")):
                _remove(m["dir"])
