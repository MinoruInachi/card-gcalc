# Settings: angle unit, number format, complex mode, brightness, SD card,
# plugins, memory / storage info, about, reset.
import gc
import os
import sys
from cardgcalc import hal, gfx, ui, storage
from cardgcalc import settings as S
from cardgcalc import i18n
from cardgcalc.i18n import T
from cardgcalc.hal import LEFT, RIGHT, ENTER, ESC

VERSION = "0.4"


def _onoff(v):
    return "on" if v else "off"


def _fmt_size(n):
    if n < 1024:
        return "%dB" % n
    if n < 1048576:
        return "%.1fK" % (n / 1024)
    return "%.2fM" % (n / 1048576)


def brightness():
    v = S.get("brightness")
    f = gfx.font("normal")
    while True:
        gfx.fill()
        ui.status_bar("Brightness")
        fb = gfx.fb()
        t = "%d %%" % v
        f.text(t, (ui.W - f.width(t)) // 2, 40, gfx.FG)
        fb.rect(20, 60, 200, 14, gfx.DIM)
        fb.fill_rect(22, 62, 196 * v // 100, 10, gfx.ACCENT)
        t = f.clip(T("fn+, fn+/ (or , /): -/+   Enter: OK"), ui.W - 8)
        f.text(t, (ui.W - f.width(t)) // 2, 90, gfx.DIM)
        gfx.show()
        hal.display.set_brightness(v)
        k = hal.wait_key()
        kk = k.nav()
        if kk == LEFT or kk == "-":
            v = max(5, v - 5)
        elif kk == RIGHT or kk in ("+", "="):
            v = min(100, v + 5)
        elif kk == ENTER:
            S.set("brightness", v)
            return
        elif kk == ESC:
            hal.display.set_brightness(S.get("brightness"))
            return


def number_format():
    opts = ["Norm", "Fix", "Sci", "Eng"]
    cur = {"norm": "Norm", "fix": "Fix", "sci": "Sci", "eng": "Eng"}.get(S.get("fmt"))
    i = ui.choose("Number format", opts, cur)
    if i is None:
        return
    mode = ("norm", "fix", "sci", "eng")[i]
    if mode == "norm":
        S.set("fmt", mode)
        S.set("digits", 10)
        return
    lo, hi = (0, 9) if mode == "fix" else (1, 10)
    n = ui.input_number("Digits (0-9)" if mode == "fix" else "Significant digits (1-10)",
                        max(lo, min(hi, S.get("digits"))))
    if n is None:
        return  # cancelled: keep the current format
    S.set("fmt", mode)
    S.set("digits", max(lo, min(hi, int(n))))


def memory_info():
    gc.collect()
    lines = []
    free = gc.mem_free()
    used = gc.mem_alloc()
    lines.append(T("RAM  free %s  used %s") % (_fmt_size(free), _fmt_size(used)))
    root = "/" if hal.IS_DEVICE else "."
    r = storage.df(root)
    if r:
        lines.append(T("Flash fs  %s free / %s") % (_fmt_size(r[1]), _fmt_size(r[0])))
    if storage.sd_mounted():
        r = storage.df(storage.SD)
        if r:
            lines.append(T("SD card   %s free / %s") % (_fmt_size(r[1]), _fmt_size(r[0])))
    else:
        lines.append(T("SD card   not mounted"))
    try:
        n = len([f for f in os.listdir(storage.PROGRAMS) if f.endswith(".py")])
        lines.append(T("Scripts   %d in %s") % (n, storage.PROGRAMS))
    except OSError:
        pass
    b = hal.battery_pct()
    if b is not None:
        lines.append(T("Battery   %d %%") % b)
    ui.text_view("Memory & storage", lines)


def about():
    impl = sys.implementation
    lines = [
        "card-gcalc %s" % VERSION,
        T("Graphing calculator for"),
        hal.MODEL_NAME,
        "",
        "MicroPython %s" % ".".join(str(v) for v in impl[1][:3]),
        "%s" % getattr(impl, "_machine", sys.platform),
        "",
        T("Fonts: X11 misc-fixed (public domain)"),
        T("Japanese: k8x12 (Num Kadoma)"),
    ]
    try:
        import machine

        lines.append(T("CPU %d MHz") % (machine.freq() // 1000000))
    except Exception:
        pass
    ui.text_view("About", lines)


def reset_all():
    if not ui.confirm("Reset all data?", T("Settings, variables, functions,") + "\n"
                      + T("lists, matrices, history") + "\n" + T("Enter: yes   Esc: no")):
        return
    try:
        for f in os.listdir(storage.DATA):
            try:
                os.remove(storage.DATA + "/" + f)
            except OSError:
                pass
    except OSError:
        pass
    S._s = None  # reload defaults
    try:
        from cardgcalc import state

        state._ctx = None
    except Exception:
        pass
    hal.display.set_brightness(S.get("brightness"))
    ui.message("Reset", "All data cleared.")


def toggle_sd():
    if storage.sd_mounted():
        storage.umount_sd()
        ui.message("SD card", "Unmounted")
    else:
        ui.busy("Mounting SD...")
        if storage.mount_sd():
            ui.message("SD card", T("Mounted at") + " " + storage.SD)
        else:
            ui.error("No SD card / mount failed")


def language():
    cur = i18n.lang()
    names = list(i18n.LANG_NAMES)
    cur_name = names[i18n.LANGS.index(cur)] if cur in i18n.LANGS else None
    j = ui.choose("Language / 言語", names, cur_name)
    if j is not None:
        S.set("lang", i18n.LANGS[j])


def run():
    sel = 0
    while True:
        ang = {"rad": "Radian", "deg": "Degree", "grad": "Gradian"}.get(S.get("angle"), "?")
        fm = S.get("fmt")
        fmt = fm[:1].upper() + fm[1:] + ("" if fm == "norm" else " %d" % S.get("digits"))
        lname = dict(zip(i18n.LANGS, i18n.LANG_NAMES)).get(i18n.lang(), "?")
        items = [
            ("Language / 言語", lname),
            ("Angle unit", ang),
            ("Number format", fmt),
            ("Complex results", _onoff(S.get("complex"))),
            ("Brightness", "%d%%" % S.get("brightness")),
            ("SD auto-mount", _onoff(S.get("sd_mount"))),
            ("SD card", "mounted" if storage.sd_mounted() else "-"),
            ("Plugins", ""),
            ("Memory & storage", ""),
            ("About", ""),
            ("Reset all data", ""),
        ]
        i = ui.menu("Settings", items, sel)
        if i is None:
            return
        sel = i
        if i == 0:
            language()
        elif i == 1:
            opts = ["Radian", "Degree", "Gradian"]
            j = ui.choose("Angle unit", opts, ang)
            if j is not None:
                S.set("angle", ("rad", "deg", "grad")[j])
        elif i == 2:
            number_format()
        elif i == 3:
            S.set("complex", not S.get("complex"))
        elif i == 4:
            brightness()
        elif i == 5:
            S.set("sd_mount", not S.get("sd_mount"))
        elif i == 6:
            toggle_sd()
        elif i == 7:
            from cardgcalc import plugins

            plugins.manage()
        elif i == 8:
            memory_info()
        elif i == 9:
            about()
        elif i == 10:
            reset_all()
