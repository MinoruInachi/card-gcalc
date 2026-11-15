# Home screen: icon grid launcher.
import gc
import sys
from nc import hal, gfx, ui, icons
from nc.i18n import T
from nc.hal import rgb, UP, DOWN, LEFT, RIGHT, ENTER, ESC

# (icon, label, module, tile colour)
APPS = (
    ("calc", "Calc", "nc.apps.calc", rgb(230, 120, 50)),
    ("graph", "Graph", "nc.apps.graph", rgb(220, 70, 80)),
    ("graph3d", "3D Graph", "nc.apps.graph3d", rgb(200, 60, 140)),
    ("table", "Table", "nc.apps.table", rgb(200, 150, 40)),
    ("equation", "Equation", "nc.apps.equation", rgb(60, 160, 120)),
    ("stats", "Stats", "nc.apps.stats", rgb(70, 120, 210)),
    ("matrix", "Matrix", "nc.apps.matrix", rgb(130, 90, 200)),
    ("basen", "Base Conv", "nc.apps.basen", rgb(40, 150, 170)),
    ("python", "Python", "nc.apps.python", rgb(50, 90, 160)),
    ("shell", "Shell", "nc.apps.shell", rgb(60, 70, 90)),
    ("files", "Files", "nc.apps.files", rgb(190, 130, 40)),
    ("gpio", "GPIO", "nc.apps.gpio", rgb(40, 140, 80)),
    ("settings", "Settings", "nc.apps.settings", rgb(110, 116, 130)),
)

COLS = 4
TW = 60
TH = 56
ROWS_VIS = 2


def draw(sel, top_row):
    gfx.fill()
    ui.status_bar("card-gcalc")
    f = gfx.font("small")
    for r in range(ROWS_VIS):
        for c in range(COLS):
            i = (top_row + r) * COLS + c
            if i >= len(APPS):
                break
            icon, label, _m, col = APPS[i]
            label = T(label)
            x = c * TW + (TW - icons.S) // 2
            y = ui.TOP + 4 + r * TH
            icons.draw(icon, x, y, col, i == sel)
            lab_col = gfx.YELLOW if i == sel else gfx.FG
            f.text(label, c * TW + (TW - f.width(label)) // 2, y + icons.S + 5, lab_col)
    # scroll indicator
    nrows = (len(APPS) + COLS - 1) // COLS
    if nrows > ROWS_VIS:
        fb = gfx.fb()
        h = ui.BOT - ui.TOP
        sh = h * ROWS_VIS // nrows
        sy = ui.TOP + (h - sh) * top_row // (nrows - ROWS_VIS)
        fb.fill_rect(hal.W - 2, sy, 2, sh, gfx.DIM)
    fb = gfx.fb()
    fb.fill_rect(0, ui.BOT, hal.W, hal.H - ui.BOT, gfx.PANEL)
    hint = "%d %s   %s" % (sel + 1, T(APPS[sel][1]), T(";,./ move  Enter open  fn+h keys"))
    f.text(hint, 3, ui.BOT + 2, gfx.DIM)
    gfx.show()


def launch(i):
    mod_name = APPS[i][2]
    gc.collect()
    try:
        __import__(mod_name)
        mod = sys.modules[mod_name]
        mod.run()
    except Exception as e:
        show_exception(e)
    finally:
        try:
            del sys.modules[mod_name]
        except KeyError:
            pass
        hal.keyboard.clear_mods()
        gc.collect()


def show_exception(e):
    import io

    buf = io.StringIO()
    sys.print_exception(e, buf)
    sys.print_exception(e)
    lines = buf.getvalue().split("\n")
    ui.text_view("Error", lines)


_sel = 0


def run():
    global _sel
    sel = _sel
    top = 0
    n = len(APPS)
    while True:
        row = sel // COLS
        if row < top:
            top = row
        if row >= top + ROWS_VIS:
            top = row - ROWS_VIS + 1
        draw(sel, top)
        k = hal.wait_key()
        kk = k.nav()
        if kk == RIGHT:
            sel = (sel + 1) % n
        elif kk == LEFT:
            sel = (sel - 1) % n
        elif kk == DOWN:
            sel = sel + COLS if sel + COLS < n else sel % COLS
        elif kk == UP:
            if sel - COLS >= 0:
                sel -= COLS
            else:
                last_row = (n - 1) // COLS
                sel = min(n - 1, last_row * COLS + sel % COLS)
        elif kk == ENTER or kk == " ":
            _sel = sel
            launch(sel)
        elif len(kk) == 1 and kk.isdigit():
            i = (int(kk) - 1) % 10
            if i < n:
                sel = i
                _sel = sel
                draw(sel, top if sel // COLS >= top else sel // COLS)
                launch(sel)
        elif k.base == "h" and k.mods & hal.FN:
            ui.show_keymap_help()
        elif k.key == ESC:
            pass
