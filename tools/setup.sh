#!/bin/sh
# Check out the MicroPython v1.29.0 and ulab 6.12.1 submodules in deps/ and
# build the host tools (mpy-cross and the unix port with ulab used by the
# simulator).
set -e
cd "$(dirname "$0")/.."
git submodule update --init deps/micropython deps/ulab
make -C deps/micropython/mpy-cross -j8
make -C deps/micropython/ports/unix submodules
# C modules for the unix port: bcd (decimal numbers) and ulab
mkdir -p deps/unix_cmodules
ln -sfn ../../firmware/cmodules/bcd deps/unix_cmodules/bcd
ln -sfn ../ulab/code deps/unix_cmodules/ulab
make -C deps/micropython/ports/unix -j8 USER_C_MODULES="$PWD/deps/unix_cmodules"
make -C deps/micropython/ports/esp32 submodules || true
echo "done.  Firmware: firmware/build.sh   Simulator: see README.md"
