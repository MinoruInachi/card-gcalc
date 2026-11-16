# Python: script manager (list / new / edit / run / rename / delete / copy).
#
#   Enter    actions menu        F1 New    F2 Edit   F3 Run
#   F4 Rename  F5 Delete  F6 Copy (flash <-> SD)   ctrl+r run
import os
import gc
from cardgcalc import hal, gfx, ui, storage
from cardgcalc.i18n import T
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL, CTRL

SD_DIR = storage.SD + "/programs"

EXAMPLES = {
    "hello.py": '''# Hello: input/print demo
name = input("Your name? ")
print("Hello,", name + "!")
for i in range(1, 6):
    print(i, "squared is", i * i)
''',
    "primes.py": '''# Sieve of Eratosthenes
import time
N = 2000
t = time.ticks_ms()
sieve = bytearray(b"\x01" * (N + 1))
sieve[0] = sieve[1] = 0
for i in range(2, int(N ** 0.5) + 1):
    if sieve[i]:
        for j in range(i * i, N + 1, i):
            sieve[j] = 0
ps = [i for i in range(N + 1) if sieve[i]]
print(len(ps), "primes below", N)
print("last:", ps[-5:])
print("time:", time.ticks_diff(time.ticks_ms(), t), "ms")
''',
    "plot.py": '''# Graphics API: plot a function and draw on the screen
import math
import cardgcalc

cardgcalc.plot(lambda x: math.sin(x) * math.exp(-x / 8), 0, 20, wait=False)
cardgcalc.text("damped sine", 150, 120, cardgcalc.YELLOW)
cardgcalc.show()
cardgcalc.wait_key()

# simple animation: Esc / Ctrl+C stops
cardgcalc.cls()
x, y, dx, dy = 20, 20, 3, 2
while True:
    cardgcalc.fill_rect(0, 0, 240, 135, cardgcalc.BLACK)
    cardgcalc.circle(x, y, 6, cardgcalc.ORANGE, True)
    cardgcalc.text("Esc: stop", 2, 2, cardgcalc.GRAY)
    cardgcalc.show()
    x += dx
    y += dy
    if x < 6 or x > 233: dx = -dx
    if y < 6 or y > 128: dy = -dy
    cardgcalc.sleep_ms(20)
''',
    "turtle_star.py": '''# Turtle graphics
from turtle import *
speed(8)
colors = ["red", "orange", "green", "blue", "purple"]
for i in range(36):
    color(colors[i % 5])
    forward(55)
    left(170)
hideturtle()
''',
    "blink.py": '''# Blink an LED on Grove G1 (Esc / Ctrl+C to stop)
import cardgcalc
print("Blinking G1... Esc to stop")
n = 0
while True:
    cardgcalc.pin_out(cardgcalc.G1, n % 2)
    n += 1
    cardgcalc.sleep_ms(500)
''',
    "chart.py": '''# matplotlib.pyplot demo
import matplotlib.pyplot as plt
x = [i / 4 for i in range(-20, 21)]
plt.plot(x, [v * v / 10 for v in x], "b")
plt.scatter([-3, 0, 3], [2, 0, 2], color="r")
plt.grid(True)
plt.title("pyplot")
plt.show()
plt.bar([1, 2, 3, 4], [3, 5, 2, 6], color="orange")
plt.show()
''',
    "ulab_demo.py": '''# ulab (numpy-like arrays) + pyplot
from ulab import numpy as np
import matplotlib.pyplot as plt
x = np.linspace(0, 4 * np.pi, 200)
y = np.sin(x) * np.exp(-x / 6)
print("max", np.max(y), "mean", np.mean(y))
plt.plot(x, y, "b")
plt.plot(x, np.exp(-x / 6), "r")
plt.grid(True)
plt.title("damped sine")
plt.show()
d = np.array([2.1, 2.5, 3.0, 3.2, 3.3, 3.9, 4.1, 4.4, 5.0, 5.6])
plt.hist(d, bins=5)
plt.show()
''',
}


def _ensure_examples():
    marker = storage.path("examples_done")
    if storage.exists(marker):
        return
    try:
        if not [f for f in os.listdir(storage.PROGRAMS) if f.endswith(".py")]:
            for name, src in EXAMPLES.items():
                with open(storage.PROGRAMS + "/" + name, "w") as f:
                    f.write(src)
        with open(marker, "w") as f:
            f.write("1")
    except OSError as e:
        print("examples:", e)


def _scan():
    out = []
    for d, tag in ((storage.PROGRAMS, ""), (SD_DIR, "SD")):
        if tag and not storage.sd_mounted():
            continue
        try:
            names = sorted(f for f in os.listdir(d) if f.endswith(".py"))
        except OSError:
            continue
        for n in names:
            p = d + "/" + n
            try:
                size = os.stat(p)[6]
            except OSError:
                size = 0
            out.append((n, p, tag, size))
    return out


def _fmt_size(n):
    if n < 1024:
        return "%dB" % n
    return "%.1fK" % (n / 1024)


def _valid_name(s):
    s = s.strip()
    if not s:
        return None
    if not s.endswith(".py"):
        s += ".py"
    for c in s:
        if not (c.isalpha() or c.isdigit() or c in "_-."):
            return None
    return s


def new_script():
    s = ui.input_line("New script name", "", math=False, prompt="letters, digits, _ -")
    if s is None:
        return None
    n = _valid_name(s)
    if not n:
        ui.error("Invalid name")
        return None
    p = storage.PROGRAMS + "/" + n
    if storage.exists(p):
        ui.error(T("%s exists") % n)
        return None
    with open(p, "w") as f:
        f.write("# %s\n" % n)
    return p


def edit_and_run(path):
    from cardgcalc import editor

    while True:
        r = editor.edit(path)
        if r != "run":
            return
        run_script(path)


def rename(path):
    d, n = path.rsplit("/", 1)
    s = ui.input_line("Rename", n, math=False)
    if s is None:
        return
    nn = _valid_name(s)
    if not nn:
        ui.error("Invalid name")
        return
    try:
        os.rename(path, d + "/" + nn)
    except OSError as e:
        ui.error("Rename failed: %s" % e)


def delete(path):
    if ui.confirm(T("Delete %s?") % path.split("/")[-1]):
        try:
            os.remove(path)
        except OSError as e:
            ui.error("Delete failed: %s" % e)


def copy_file(src, dst):
    buf = bytearray(512)
    with open(src, "rb") as fi:
        with open(dst, "wb") as fo:
            while True:
                n = fi.readinto(buf)
                if not n:
                    break
                fo.write(buf if n == 512 else buf[:n])


def copy_other(item):
    n, p, tag, _ = item
    if tag:
        dst = storage.PROGRAMS + "/" + n
    else:
        if not storage.sd_mounted() and not storage.mount_sd():
            ui.error("No SD card")
            return
        try:
            os.mkdir(SD_DIR)
        except OSError:
            pass
        dst = SD_DIR + "/" + n
    if storage.exists(dst) and not ui.confirm(T("Overwrite %s?") % dst):
        return
    try:
        copy_file(p, dst)
        ui.message("Copied", "→ " + dst)
    except OSError as e:
        ui.error("Copy failed: %s" % e)


def actions(item):
    n, p, tag, _ = item
    opts = ["Run", "Edit", "Rename", "Delete", "Copy to flash" if tag else "Copy to SD"]
    i = ui.menu(n, opts)
    if i == 0:
        run_script(p)
    elif i == 1:
        edit_and_run(p)
    elif i == 2:
        rename(p)
    elif i == 3:
        delete(p)
    elif i == 4:
        copy_other(item)


def draw(items, sel, off, vis):
    f = gfx.font("normal")
    fb = gfx.fb()
    gfx.fill()
    ui.status_bar("Python", T("%d files") % len(items))
    top = ui.TOP + 2
    if not items:
        f.text(T("No scripts. F1: new script"), 10, top + 20, gfx.DIM)
    for r in range(vis):
        i = off + r
        if i >= len(items):
            break
        n, p, tag, size = items[i]
        y = top + r * 13
        if i == sel:
            fb.fill_rect(0, y - 1, ui.W, 13, gfx.SEL)
        f.text("py", 4, y + 1, gfx.YELLOW if i != sel else gfx.FG)
        f.text(f.clip(n, 150), 22, y + 1, gfx.FG)
        right = ("SD " if tag else "") + _fmt_size(size)
        f.text(right, ui.W - 6 - f.width(right), y + 1, gfx.ACCENT2 if tag else gfx.DIM)
    ui.softkeys(["New", "Edit", "Run", "Rename", "Delete", "Copy"])
    gfx.show()


def run_app():
    storage.ensure_dirs()
    _ensure_examples()
    sel = 0
    off = 0
    vis = (ui.BOT - ui.TOP - 2) // 13
    items = _scan()
    while True:
        if sel >= len(items):
            sel = max(0, len(items) - 1)
        if sel < off:
            off = sel
        if sel >= off + vis:
            off = sel - vis + 1
        draw(items, sel, off, vis)
        k = hal.wait_key()
        kk = k.nav()
        fk = ui.fkey(k)
        cur = items[sel] if items else None
        changed = True
        if kk == UP:
            sel = (sel - 1) % len(items) if items else 0
            changed = False
        elif kk == DOWN:
            sel = (sel + 1) % len(items) if items else 0
            changed = False
        elif kk == ESC or kk == LEFT:
            return
        elif fk == 0 or (k.mods & CTRL and k.base == "n"):
            p = new_script()
            if p:
                edit_and_run(p)
        elif cur is None:
            changed = False
        elif kk == ENTER or kk == RIGHT:
            actions(cur)
        elif fk == 1 or k.key == "e":
            edit_and_run(cur[1])
        elif fk == 2 or k.key == "r" or (k.mods & CTRL and k.base == "r"):
            run_script(cur[1])
        elif fk == 3:
            rename(cur[1])
        elif fk == 4 or kk in (BS, DEL):
            delete(cur[1])
        elif fk == 5:
            copy_other(cur)
        else:
            changed = False
        if changed:
            items = _scan()


def run():
    run_app()


def run_script(path):
    from cardgcalc import runner

    runner.run_file(path)
    gc.collect()
