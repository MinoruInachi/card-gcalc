#!/bin/sh
# Build and install card-gcalc plugins (see README.md "Plugins").
#
#   tools/plugin.sh build DIR          compile DIR/*.py to .mpy in build/plugins/<name>
#   tools/plugin.sh install DIR        build, then copy to /plugins/<name> on the device
#   tools/plugin.sh install-py DIR     copy the .py sources instead (easier to debug)
#   tools/plugin.sh sim DIR            copy the sources for the host simulator
#   tools/plugin.sh remove NAME        delete /plugins/NAME on the device
#
# DIR is a plugin directory (plugin.json + modules), e.g. plugins/basic.
# Precompiled .mpy modules load faster and need less RAM than .py sources.
# PORT defaults to the first /dev/cu.usbmodem* device.
set -e
cd "$(dirname "$0")/.."
MPYCROSS=deps/micropython/mpy-cross/build/mpy-cross
PORT=${PORT:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)}
MP="mpremote connect $PORT"

cmd=$1
src=${2%/}
name=$(basename "${src:-x}")

need_dir() {
  if [ ! -f "$src/plugin.json" ]; then
    echo "$src/plugin.json not found" >&2
    exit 1
  fi
}

# copy $src to $1, compiling .py files to .mpy when $2 = mpy
stage() {
  out=$1
  rm -rf "$out"
  mkdir -p "$out"
  (cd "$src" && find . -type f ! -name '.*' ! -path '*/__pycache__/*') | while read -r f; do
    f=${f#./}
    mkdir -p "$out/$(dirname "$f")"
    case "$f" in
      *.py)
        if [ "$2" = mpy ]; then
          "$MPYCROSS" -o "$out/${f%.py}.mpy" -s "$f" "$src/$f"
        else
          cp "$src/$f" "$out/$f"
        fi ;;
      *) cp "$src/$f" "$out/$f" ;;
    esac
  done
}

device_rm() {
  $MP exec "import os
def rm(p):
    try:
        if os.stat(p)[0] & 0x4000:
            for f in os.listdir(p): rm(p+'/'+f)
            os.rmdir(p)
        else: os.remove(p)
    except OSError: pass
rm('/plugins/$1')"
}

device_install() {
  device_rm "$name"
  $MP mkdir :/plugins 2>/dev/null || true
  $MP cp -r "$1" :/plugins/
  $MP soft-reset
  echo "installed /plugins/$name"
}

case "$cmd" in
  build)
    need_dir
    [ -x "$MPYCROSS" ] || { echo "run tools/setup.sh first (mpy-cross)" >&2; exit 1; }
    stage "build/plugins/$name" mpy
    echo "built build/plugins/$name" ;;
  install)
    need_dir
    [ -x "$MPYCROSS" ] || { echo "run tools/setup.sh first (mpy-cross)" >&2; exit 1; }
    stage "build/plugins/$name" mpy
    device_install "build/plugins/$name" ;;
  install-py)
    need_dir
    stage "build/plugins-py/$name" py
    device_install "build/plugins-py/$name" ;;
  sim)
    need_dir
    stage "sim_out/fs/plugins/$name" py
    echo "copied to sim_out/fs/plugins/$name" ;;
  remove)
    [ -n "$2" ] || { echo "usage: $0 remove NAME" >&2; exit 1; }
    device_rm "$2"
    $MP soft-reset
    echo "removed /plugins/$2" ;;
  *) sed -n '2,13p' "$0" ;;
esac
