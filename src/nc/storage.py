# File system helpers: data directory, SD card mount.
import os
from nc import hal

if hal.IS_DEVICE:
    DATA = "/data"
    PROGRAMS = "/programs"
    PLUGINS = "/plugins"
else:
    DATA = "sim_out/fs/nc"
    PROGRAMS = "sim_out/fs/programs"
    PLUGINS = "sim_out/fs/plugins"
SD = "/sd"
_sd = None


def _mkdirs(p):
    parts = p.split("/")
    cur = ""
    for i, part in enumerate(parts):
        if not part:
            if i == 0:
                cur = "/"
            continue
        cur = cur + part if cur.endswith("/") or cur == "" else cur + "/" + part
        try:
            os.mkdir(cur)
        except OSError:
            pass


def ensure_dirs():
    _mkdirs(DATA)
    _mkdirs(PROGRAMS)
    _mkdirs(PLUGINS)


def path(name):
    return DATA + "/" + name


def exists(p):
    try:
        os.stat(p)
        return True
    except OSError:
        return False


def isdir(p):
    try:
        return os.stat(p)[0] & 0x4000 != 0
    except OSError:
        return False


def mount_sd():
    """Mount the microSD card at /sd.  Returns True on success."""
    global _sd
    if not hal.IS_DEVICE:
        return False
    if sd_mounted():
        return True
    try:
        import machine
        from machine import Pin

        _sd = machine.SDCard(slot=2, sck=Pin(40), miso=Pin(39), mosi=Pin(14), cs=Pin(12), freq=20000000)
        os.mount(_sd, SD)
        return True
    except Exception as e:
        print("sd: mount failed", e)
        try:
            if _sd:
                _sd.deinit()
        except Exception:
            pass
        _sd = None
        return False


def umount_sd():
    global _sd
    try:
        os.umount(SD)
    except Exception:
        pass
    try:
        if _sd:
            _sd.deinit()
    except Exception:
        pass
    _sd = None


def sd_mounted():
    try:
        os.stat(SD)
        return SD.lstrip("/") in os.listdir("/")
    except OSError:
        return False


def df(p="/"):
    """(total_bytes, free_bytes) for the filesystem containing p."""
    try:
        s = os.statvfs(p)
        return s[0] * s[2], s[0] * s[3]
    except Exception:
        return None


def load_json(name, default=None):
    import json

    try:
        with open(path(name)) as f:
            v = json.load(f)
    except Exception:
        return default
    # calculator numbers: decimal markers (and old float data) -> bcd.D
    from nc.calc import dec

    return dec.from_json(v)


def save_json(name, obj):
    import json

    from nc.calc import dec

    try:
        obj = dec.to_json(obj)
        with open(path(name), "w") as f:
            json.dump(obj, f)
        return True
    except Exception as e:
        print("save_json failed", name, e)
        return False
