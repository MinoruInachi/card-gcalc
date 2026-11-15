#!/bin/sh
# Fetch MicroPython v1.29.0 and ulab 6.12.1 into deps/ and build the host
# tools (mpy-cross and the unix port with ulab used by the simulator).
set -e
cd "$(dirname "$0")/.."
if [ ! -d deps/micropython ]; then
  mkdir -p deps
  git clone --depth 1 -b v1.29.0 https://github.com/micropython/micropython.git deps/micropython
fi
if [ ! -d deps/ulab ]; then
  git clone --depth 1 -b 6.12.1 https://github.com/v923z/micropython-ulab.git deps/ulab
fi
make -C deps/micropython/mpy-cross -j8
make -C deps/micropython/ports/unix submodules
# C modules for the unix port: bcd (decimal numbers) and ulab
mkdir -p deps/unix_cmodules
ln -sfn ../../firmware/cmodules/bcd deps/unix_cmodules/bcd
ln -sfn ../ulab/code deps/unix_cmodules/ulab
make -C deps/micropython/ports/unix -j8 USER_C_MODULES="$PWD/deps/unix_cmodules"
make -C deps/micropython/ports/esp32 submodules || true
echo "done.  Firmware: firmware/build.sh   Simulator: see README.md"
