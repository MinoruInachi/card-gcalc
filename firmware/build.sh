#!/bin/sh
# Build the card-gcalc firmware.
#   firmware/build.sh [adv|cardputer|all] [make args...]
#     adv        M5Stack Cardputer-Adv (default)  -> build-CARD_GCALC
#     cardputer  M5Stack Cardputer                -> build-CARD_GCALC-CARDPUTER
#     all        both
#   The complete image to write at 0x0 is <build dir>/firmware.bin.
#   IDF_PATH: ESP-IDF v5.5.x checkout (default: /Volumes/bufext/esp/v5.5.4/esp-idf)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
MPY="$ROOT/deps/micropython"
MODEL=adv
case "$1" in
  adv|cardputer|all) MODEL=$1; shift ;;
esac
if [ "$MODEL" = all ]; then
  "$0" adv "$@"
  exec "$0" cardputer "$@"
fi
: "${IDF_PATH:=/Volumes/bufext/esp/v5.5.4/esp-idf}"
. "$IDF_PATH/export.sh" >/dev/null 2>&1
# Apply local MicroPython patches (idempotent).
"$HERE/patches/apply.sh"
make -C "$MPY/mpy-cross" -j8 >/dev/null
cd "$MPY/ports/esp32"
if [ "$MODEL" = cardputer ]; then
  B=build-CARD_GCALC-CARDPUTER
  set -- BOARD_VARIANT=CARDPUTER "$@"
else
  B=build-CARD_GCALC
fi
# Frozen modules are not regenerated when a source file is deleted, so drop
# the frozen output of modules that no longer exist in src/.
if [ -d "$B/frozen_mpy" ]; then
  stale=0
  for m in $(cd "$B/frozen_mpy" && find . -name '*.mpy'); do
    s="$ROOT/src/${m%.mpy}.py"
    # modules frozen from MicroPython itself (port modules, asyncio, upysh)
    # and the per-model board module
    case "$m" in ./asyncio/*|./uasyncio.mpy|./upysh.mpy|./cardgcalc_board.mpy) continue ;; esac
    [ -f "modules/${m%.mpy}.py" ] && continue
    if [ ! -f "$s" ] && [ ! -f "${s%.py}/__init__.py" ]; then
      rm -f "$B/frozen_mpy/$m"
      stale=1
    fi
  done
  if [ $stale = 1 ]; then rm -f "$B/frozen_content.c"; fi
fi
make BOARD_DIR="$HERE/boards/CARD_GCALC" USER_C_MODULES="$HERE/cmodules/micropython.cmake" -j8 "$@"
echo "card-gcalc ($MODEL): $MPY/ports/esp32/$B/firmware.bin"
