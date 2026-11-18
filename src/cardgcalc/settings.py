# Persistent settings (JSON in /data/settings.json).
import json
from cardgcalc import storage

_PATH = "settings.json"
DEFAULTS = {
    "angle": "rad",  # rad | deg | grad
    "fmt": "norm",  # norm | fix | sci | eng
    "digits": 10,
    "complex": False,
    "mixedfrac": False,  # Calc: show fractions above 1 as mixed numbers
    "brightness": 70,
    "sd_mount": True,
    "autosave": True,
    "editor_tab": 4,
    "lang": "en",  # en | ja
}
_s = None


def _load():
    global _s
    _s = dict(DEFAULTS)
    try:
        with open(storage.path(_PATH)) as f:
            _s.update(json.load(f))
    except Exception:
        pass


def get(k, default=None):
    if _s is None:
        _load()
    return _s.get(k, default)


def set(k, v):
    if _s is None:
        _load()
    _s[k] = v
    save()


def save():
    try:
        with open(storage.path(_PATH), "w") as f:
            json.dump(_s, f)
    except Exception as e:
        print("settings: save failed", e)
