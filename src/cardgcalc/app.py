# card-gcalc entry point.
import gc
from cardgcalc import hal


def main():
    hal.init()
    from cardgcalc import storage, settings, ui

    storage.ensure_dirs()
    hal.display.set_brightness(settings.get("brightness"))
    ui._hook_mods()
    if settings.get("sd_mount"):
        storage.mount_sd()
    gc.collect()
    from cardgcalc import home

    home.run()
