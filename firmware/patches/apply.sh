#!/bin/sh
# Apply the local MicroPython patches in this directory to deps/micropython
# (idempotent: patches that are already applied are skipped).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
MPY=$(cd "$HERE/../../deps/micropython" && pwd)
for p in "$HERE"/*.patch; do
  if git -C "$MPY" apply --check -R "$p" 2>/dev/null; then
    continue  # already applied
  fi
  git -C "$MPY" apply "$p" && echo "applied $(basename "$p")"
done
