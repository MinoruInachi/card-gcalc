#!/bin/sh
# Build the card-gcalc firmware.
#   IDF_PATH: ESP-IDF v5.5.x checkout (default: /Volumes/bufext/esp/v5.5.4/esp-idf)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
MPY="$ROOT/deps/micropython"
: "${IDF_PATH:=/Volumes/bufext/esp/v5.5.4/esp-idf}"
. "$IDF_PATH/export.sh" >/dev/null 2>&1
# Apply local MicroPython patches (idempotent).
for p in "$HERE"/patches/*.patch; do
  if git -C "$MPY" apply --check -R "$p" 2>/dev/null; then
    continue  # already applied
  fi
  git -C "$MPY" apply "$p" && echo "applied $(basename "$p")"
done
make -C "$MPY/mpy-cross" -j8 >/dev/null
cd "$MPY/ports/esp32"
# Frozen modules are not regenerated when a source file is deleted, so drop
# the frozen output of modules that no longer exist in src/.
B=build-CARD_GCALC
if [ -d "$B/frozen_mpy" ]; then
  stale=0
  for m in $(cd "$B/frozen_mpy" && find . -name '*.mpy'); do
    s="$ROOT/src/${m%.mpy}.py"
    # modules frozen from MicroPython itself (port modules, asyncio, upysh)
    case "$m" in ./asyncio/*|./uasyncio.mpy|./upysh.mpy) continue ;; esac
    [ -f "modules/${m%.mpy}.py" ] && continue
    if [ ! -f "$s" ] && [ ! -f "${s%.py}/__init__.py" ]; then
      rm -f "$B/frozen_mpy/$m"
      stale=1
    fi
  done
  if [ $stale = 1 ]; then rm -f "$B/frozen_content.c"; fi
fi
make BOARD_DIR="$HERE/boards/CARD_GCALC" USER_C_MODULES="$HERE/cmodules/micropython.cmake" -j8 "$@"
