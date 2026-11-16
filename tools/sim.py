# card-gcalc host simulator (run with unix MicroPython).
#
#   micropython tools/sim.py <module>[:func] "<key script>" [outdir]
#
# Key script: whitespace separated items
#   abc / "1+2"    type characters (quotes allow spaces: "a b")
#   ENTER ESC UP DOWN LEFT RIGHT BS DEL TAB SPACE F1..F10 HOME END PGUP PGDN
#   opt+s alt+c ctrl+s fn+1 shift+a   key with modifier(s)
#   @name          save a screenshot to <outdir>/<name>.bin (see tools/simshot.py)
#   #ms            sleep (no-op)
# When the script is exhausted a final screenshot "final" is saved and the
# simulator exits.
import sys

if sys.platform != "esp32":
    sys.path.insert(0, "src")
from cardgcalc import hal

OUT = "sim_out"
_shot_n = [0]


def save_shot(name):
    if hal.IS_DEVICE:
        # Device: stream the frame buffer over the REPL (see tools/devsim.py).
        import binascii
        import time

        import os

        # Detach the script console (os.dupterm) while streaming.
        try:
            prev = os.dupterm(None)
        except Exception:
            prev = None
        mv = memoryview(hal.display.buf)
        sys.stdout.write("\n@@SHOT %s\n" % name)
        for i in range(0, len(mv), 1536):
            sys.stdout.write(binascii.b2a_base64(mv[i : i + 1536]))
        sys.stdout.write("@@END\n")
        if prev is not None:
            os.dupterm(prev)
        return
    try:
        import os

        os.mkdir(OUT)
    except OSError:
        pass
    with open("%s/%s.bin" % (OUT, name), "wb") as f:
        f.write(hal.display.buf)
    print("[sim] shot", name)


def _char_key(ch):
    for row in hal._LAYOUT:
        for cap in row:
            if cap == " " and ch == " ":
                return hal.Key(" ", " ", 0)
            if len(cap) == 2 and cap[0] != "*" and cap not in (hal.BS,):
                if cap[0] == ch:
                    return hal.Key(ch, ch, 0)
                if cap[1] == ch:
                    return hal.Key(ch, cap[0], hal.SHIFT)
    return hal.Key(ch, ch, 0)


_MODS = {"opt": hal.OPT, "alt": hal.ALT, "ctrl": hal.CTRL, "fn": hal.FN, "shift": hal.SHIFT}
_NAMED = ("ENTER", "ESC", "UP", "DOWN", "LEFT", "RIGHT", "BS", "DEL", "TAB",
          "HOME", "END", "PGUP", "PGDN") + tuple("F%d" % i for i in range(1, 11))


def parse_script(s):
    items = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in " \n\t":
            i += 1
            continue
        if c == '"':
            j = s.index('"', i + 1)
            for ch in s[i + 1 : j]:
                items.append(("key", _char_key(ch)))
            i = j + 1
            continue
        j = i
        while j < n and s[j] not in " \n\t":
            j += 1
        w = s[i:j]
        i = j
        if w.startswith("@"):
            items.append(("shot", w[1:]))
        elif w.startswith("#"):
            items.append(("sleep", int(w[1:] or 0)))
        elif "+" in w and len(w) > 1 and w.split("+")[0] in _MODS:
            parts = w.split("+")
            base = parts[-1]
            mods = 0
            for m in parts[:-1]:
                mods |= _MODS[m]
            if base in _NAMED:
                key = base
            elif base == "SPACE":
                key = base = " "
            else:
                key = base
            if mods & hal.FN:
                key = hal._FN.get(base, key)
            if mods & hal.SHIFT and len(base) == 1:
                key = _char_key(base.upper() if base.isalpha() else base).key
                for row in hal._LAYOUT:
                    for cap in row:
                        if len(cap) == 2 and cap[0] == base:
                            key = cap[1]
            items.append(("key", hal.Key(key, base, mods)))
        elif w in _NAMED:
            items.append(("key", hal.Key(w, w, 0)))
        elif w == "SPACE":
            items.append(("key", hal.Key(" ", " ", 0)))
        else:
            for ch in w:
                items.append(("key", _char_key(ch)))
    return items


_items = []


def _idle():
    while _items:
        kind, v = _items.pop(0)
        if kind == "shot":
            save_shot(v)
            continue
        if kind == "sleep":
            if hal.IS_DEVICE:
                import time

                time.sleep_ms(v)
            continue
        hal.keyboard.queue.append(v)
        return
    save_shot("final")
    raise SystemExit(0)


def main():
    global OUT
    target = sys.argv[1] if len(sys.argv) > 1 else "cardgcalc.app:main"
    script = sys.argv[2] if len(sys.argv) > 2 else ""
    if script.startswith("@@"):
        # @@path : read the key script from a file (argv length is limited)
        with open(script[2:]) as f:
            script = f.read()
    if len(sys.argv) > 3:
        OUT = sys.argv[3]
    _items.extend(parse_script(script))
    hal.sim_idle = _idle
    hal.init()
    if hal.IS_DEVICE:
        # Feed scripted keys from the idle hook; real keys still work too.
        def _dev_idle():
            if not hal.keyboard.queue:
                _idle()

        hal.add_idle_hook(_dev_idle)
    from cardgcalc import storage

    storage.ensure_dirs()
    mod, _, fn = target.partition(":")
    m = __import__(mod, None, None, ["x"])
    for part in mod.split(".")[1:]:
        pass
    m = sys.modules[mod]
    try:
        getattr(m, fn or "run")()
    except SystemExit:
        pass
    save_shot("final")


if __name__ == "__main__":
    main()
