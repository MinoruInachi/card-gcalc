#!/bin/sh
# Development helpers for a device running the card-gcalc firmware.
#
#   tools/dev.sh push [files...]  copy src/nc (or given src/ files) to the device
#                                 filesystem; they override the frozen copies
#   tools/dev.sh clean            remove the overriding copies (use frozen code)
#   tools/dev.sh reset            soft-reset (restarts the calculator)
#   tools/dev.sh repl             open the REPL
#   tools/dev.sh run file.py      run a local script on the device
# PORT defaults to the first /dev/cu.usbmodem* device.
set -e
cd "$(dirname "$0")/.."
PORT=${PORT:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)}
MP="mpremote connect $PORT"
cmd=$1; shift || true
case "$cmd" in
  push)
    if [ $# -eq 0 ]; then
      $MP mkdir :/nc 2>/dev/null || true
      $MP cp -r src/nc :/
    else
      for f in "$@"; do
        rel=${f#src/}
        d=$(dirname "$rel")
        [ "$d" != "." ] && $MP exec "import os
p=''
for s in '$d'.split('/'):
    p+='/'+s
    try: os.mkdir(p)
    except OSError: pass" 
        $MP cp "$f" ":/$rel"
      done
    fi ;;
  clean)
    $MP exec "import os
def rm(p):
    try:
        if os.stat(p)[0] & 0x4000:
            for f in os.listdir(p): rm(p+'/'+f)
            os.rmdir(p)
        else: os.remove(p)
    except OSError: pass
rm('/nc')" ;;
  reset) $MP soft-reset ;;
  repl) $MP repl ;;
  run) $MP run "$1" ;;
  *) sed -n '2,12p' "$0" ;;
esac
