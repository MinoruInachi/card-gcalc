# card-gcalc entry point.
import gc
from nc import hal


def main():
    hal.init()
    from nc import storage, settings, ui

    storage.ensure_dirs()
    hal.display.set_brightness(settings.get("brightness"))
    ui._hook_mods()
    if settings.get("sd_mount"):
        storage.mount_sd()
    gc.collect()
    from nc import home

    home.run()
