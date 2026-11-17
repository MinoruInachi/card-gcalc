#!/bin/sh
# Flash the card-gcalc firmware.  Usage: firmware/flash.sh [adv|cardputer] [PORT]
#   adv        M5Stack Cardputer-Adv (default)
#   cardputer  M5Stack Cardputer
#
# The firmware uses the ESP32-S3 USB-Serial/JTAG for its REPL, so esptool can
# reset the chip into the bootloader by itself.  If that ever fails (e.g. a
# different firmware is installed), enter download mode by hand: hold G0 while
# switching power on, release G0, then run this script again.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
B="$HERE/../deps/micropython/ports/esp32/build-CARD_GCALC"
case "$1" in
  adv) shift ;;
  cardputer) B="$B-CARDPUTER"; shift ;;
esac
PORT=${1:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)}
python3 -m esptool --chip esp32s3 --port "$PORT" --before default-reset --after hard-reset \
  --baud 921600 write-flash -z \
  0x0 "$B/bootloader/bootloader.bin" \
  0x8000 "$B/partition_table/partition-table.bin" \
  0x10000 "$B/micropython.bin"
