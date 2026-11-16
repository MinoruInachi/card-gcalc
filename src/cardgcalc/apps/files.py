# Files: browse the internal flash and the microSD card.
#
#   Enter    open dir / file actions     BS / ← (fn+,)   parent dir
#   F1 SD mount/unmount  F2 New dir  F3 Copy  F4 Rename  F5 Delete  F6 Info
import os
import gc
from cardgcalc import hal, gfx, ui, storage
from cardgcalc.i18n import T
from cardgcalc.hal import UP, DOWN, LEFT, RIGHT, ENTER, ESC, BS, DEL

ROOT = "/" if hal.IS_DEVICE else "sim_out/fs"
TEXT_EXT = (".py", ".txt", ".json", ".csv", ".md", ".cfg", ".ini", ".log")


def join(d, n):
    if d.endswith("/"):
        return d + n
    return d + "/" + n


def parent(d):
    if d == ROOT or d == "/":
        return d
    p = d[: d.rfind("/")]
    if not p:
        return "/"
    if len(p) < len(ROOT):
        return ROOT
    return p


def fmt_size(n):
    if n < 1024:
        return "%dB" % n
    if n < 1024 * 1024:
        return "%.1fK" % (n / 1024)
    return "%.1fM" % (n / 1048576)


def listing(d):
    dirs = []
    files = []
    try:
        for ent in os.ilistdir(d):
            name = ent[0]
            if ent[1] & 0x4000:
                dirs.append((name, True, 0))
            else:
                if len(ent) > 3:
                    sz = ent[3]
                else:
                    try:
                        sz = os.stat(join(d, name))[6]
                    except OSError:
                        sz = 0
                files.append((name, False, sz))
    except OSError as e:
        ui.error(T("Cannot list %s") % d + "\n%s" % e)
    dirs.sort()
    files.sort()
    out = []
    if d != ROOT and d != "/":
        out.append(("..", True, 0))
    return out + dirs + files


def copy_any(src, dst):
    if storage.isdir(src):
        try:
            os.mkdir(dst)
        except OSError:
            pass
        for ent in os.ilistdir(src):
            copy_any(join(src, ent[0]), join(dst, ent[0]))
        return
    buf = bytearray(1024)
    with open(src, "rb") as fi:
        with open(dst, "wb") as fo:
            while True:
                n = fi.readinto(buf)
                if not n:
                    break
                fo.write(buf if n == len(buf) else buf[:n])


def remove_any(p):
    if storage.isdir(p):
        for ent in os.ilistdir(p):
            remove_any(join(p, ent[0]))
        os.rmdir(p)
    else:
        os.remove(p)


def view(p):
    try:
        with open(p, "rb") as f:
            data = f.read(16384)
    except OSError as e:
        ui.error(str(e))
        return
    name = p.split("/")[-1]
    binary = b"\x00" in data[:512]
    if not binary:
        try:
            text = data.decode()
        except Exception:
            binary = True
    if binary:
        lines = []
        for o in range(0, min(len(data), 1024), 8):
            chunk = data[o: o + 8]
            hx = " ".join("%02x" % b for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append("%04x %-23s %s" % (o, hx, asc))
        ui.text_view(name + " (" + T("hex") + ")", lines)
    else:
        ui.text_view(name, text.replace("\r", "").split("\n"))
    del data
    gc.collect()


def info(d):
    lines = []
    for label, path in (("Flash", ROOT), ("SD", storage.SD)):
        if path == storage.SD and not storage.sd_mounted():
            lines.append("SD: " + T("not mounted"))
            continue
        r = storage.df(path)
        if r:
            tot, free = r
            lines.append(T("%s: %s free / %s") % (T(label), fmt_size(free), fmt_size(tot)))
    gc.collect()
    lines.append(T("RAM free: %s") % fmt_size(gc.mem_free()))
    lines.append(T("Dir:") + " " + d)
    ui.message("Storage", lines)


class Files:
    def __init__(self):
        self.d = ROOT
        self.sel = 0
        self.off = 0
        self.items = []
        self.clip = None  # (path, move?)
        self.refresh()

    def refresh(self):
        self.items = listing(self.d)
        if self.sel >= len(self.items):
            self.sel = max(0, len(self.items) - 1)
        gc.collect()

    def path(self, i=None):
        if i is None:
            i = self.sel
        return join(self.d, self.items[i][0])

    def draw(self):
        f = gfx.font("normal")
        fb = gfx.fb()
        gfx.fill()
        ui.status_bar("Files", "SD" if storage.sd_mounted() else "")
        # path line
        fb.fill_rect(0, ui.TOP, ui.W, 11, gfx.PANEL2)
        p = self.d
        if self.clip:
            p = T("MOVE" if self.clip[1] else "COPY") + " " + self.clip[0].split("/")[-1] + " → " + T("paste: F3")
        f.text(f.clip(p, ui.W - 4), 2, ui.TOP, gfx.YELLOW if self.clip else gfx.FG)
        top = ui.TOP + 13
        rowh = 12
        vis = (ui.BOT - top) // rowh
        if self.sel < self.off:
            self.off = self.sel
        if self.sel >= self.off + vis:
            self.off = self.sel - vis + 1
        for r in range(vis):
            i = self.off + r
            if i >= len(self.items):
                break
            name, isdir, sz = self.items[i]
            y = top + r * rowh
            if i == self.sel:
                fb.fill_rect(0, y - 1, ui.W, rowh, gfx.SEL)
            if isdir:
                fb.fill_rect(4, y + 2, 4, 2, gfx.YELLOW)
                fb.fill_rect(4, y + 3, 9, 6, gfx.YELLOW)
                right = T("<DIR>") if name != ".." else ""
            else:
                fb.rect(5, y + 1, 7, 9, gfx.DIM)
                right = fmt_size(sz)
            f.text(f.clip(name, ui.W - 30 - f.width(right)), 17, y, gfx.FG)
            if right:
                f.text(right, ui.W - 4 - f.width(right), y, gfx.DIM)
        if not self.items:
            f.text(T("(empty)"), 20, top + 4, gfx.DIM)
        ui.softkeys(["SD", "Mkdir", "Paste" if self.clip else "Copy", "Rename", "Delete", "Info"])
        gfx.show()

    def open(self):
        if not self.items:
            return
        name, isdir, _ = self.items[self.sel]
        if name == "..":
            self.up()
            return
        p = self.path()
        if isdir:
            self.d = p
            self.sel = 0
            self.off = 0
            self.refresh()
            return
        opts = ["Open"]
        from cardgcalc import plugins

        ph = plugins.handler(name)
        if ph is not None:
            opts.insert(0, "Open with: " + plugins.label(ph))
        is_py = name.endswith(".py")
        is_text = name.endswith(TEXT_EXT)
        if is_py:
            opts += ["Run", "Edit"]
        elif is_text:
            opts += ["Edit"]
        opts += ["Copy", "Move", "Rename", "Delete"]
        i = ui.menu(name, opts)
        if i is None:
            return
        act = opts[i]
        if act.startswith("Open with: "):
            plugins.launch(ph, "open_file", p)
        elif act == "Open":
            view(p)
        elif act == "Run":
            from cardgcalc import runner

            runner.run_file(p)
        elif act == "Edit":
            from cardgcalc import editor

            while editor.edit(p) == "run":
                from cardgcalc import runner

                runner.run_file(p)
        elif act == "Copy":
            self.clip = (p, False)
        elif act == "Move":
            self.clip = (p, True)
        elif act == "Rename":
            self.rename()
        elif act == "Delete":
            self.delete()
        self.refresh()

    def up(self):
        if self.d == ROOT or self.d == "/":
            return
        old = self.d.split("/")[-1]
        self.d = parent(self.d)
        self.refresh()
        self.sel = 0
        for i, it in enumerate(self.items):
            if it[0] == old:
                self.sel = i

    def rename(self):
        if not self.items or self.items[self.sel][0] == "..":
            return
        p = self.path()
        s = ui.input_line("Rename", self.items[self.sel][0], math=False)
        if not s or "/" in s:
            return
        try:
            os.rename(p, join(self.d, s))
        except OSError as e:
            ui.error("Rename failed: %s" % e)
        self.refresh()

    def delete(self):
        if not self.items or self.items[self.sel][0] == "..":
            return
        name, isdir, _ = self.items[self.sel]
        if not ui.confirm(T("Delete %s?") % (name + (T(" (and contents)") if isdir else ""))):
            return
        try:
            remove_any(self.path())
        except OSError as e:
            ui.error("Delete failed: %s" % e)
        self.refresh()

    def mkdir(self):
        s = ui.input_line("New directory", "", math=False)
        if not s or "/" in s:
            return
        try:
            os.mkdir(join(self.d, s))
        except OSError as e:
            ui.error("mkdir failed: %s" % e)
        self.refresh()

    def copy_or_paste(self):
        if self.clip is None:
            if self.items and self.items[self.sel][0] != "..":
                self.clip = (self.path(), False)
            return
        src, move = self.clip
        name = src.split("/")[-1]
        dst = join(self.d, name)
        if dst == src:
            self.clip = None
            return
        if self.d == src or self.d.startswith(src + "/"):
            # a folder cannot be copied or moved into itself
            ui.error(T("Cannot paste a folder into itself"))
            return
        if storage.exists(dst) and not ui.confirm(T("Overwrite %s?") % name):
            return
        ui.busy("Moving..." if move else "Copying...")
        try:
            if move:
                try:
                    os.rename(src, dst)  # same filesystem
                except OSError:
                    copy_any(src, dst)
                    remove_any(src)
            else:
                copy_any(src, dst)
        except OSError as e:
            ui.error("Failed: %s" % e)
        self.clip = None
        self.refresh()

    def toggle_sd(self):
        if storage.sd_mounted():
            if self.d.startswith(storage.SD):
                self.d = ROOT
            storage.umount_sd()
            ui.message("SD card", "Unmounted")
        else:
            ui.busy("Mounting SD...")
            if storage.mount_sd():
                self.d = storage.SD
                self.sel = 0
            else:
                ui.error("No SD card / mount failed")
        self.refresh()

    def run(self):
        while True:
            self.draw()
            k = hal.wait_key()
            kk = k.nav()
            fk = ui.fkey(k)
            n = len(self.items)
            if kk == UP:
                self.sel = (self.sel - 1) % n if n else 0
            elif kk == DOWN:
                self.sel = (self.sel + 1) % n if n else 0
            elif kk == "PGUP":
                self.sel = max(0, self.sel - 8)
            elif kk == "PGDN":
                self.sel = min(max(0, n - 1), self.sel + 8)
            elif kk == ENTER or kk == RIGHT:
                self.open()
            elif kk == LEFT or kk == BS:
                self.up()
            elif kk == ESC:
                if self.clip:
                    self.clip = None
                else:
                    return
            elif fk == 0:
                self.toggle_sd()
            elif fk == 1:
                self.mkdir()
            elif fk == 2:
                self.copy_or_paste()
            elif fk == 3:
                self.rename()
            elif fk == 4 or kk == DEL:
                self.delete()
            elif fk == 5:
                info(self.d)


def run():
    Files().run()
