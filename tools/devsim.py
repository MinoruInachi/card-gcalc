#!/usr/bin/env python3
"""Drive the card-gcalc app on a real device with a key script and grab
screenshots of the frame buffer (same script syntax as tools/sim.py).

Usage: tools/devsim.py <module>[:func] "<key script>" [outdir=dev_out] [port]
Screenshots are written as <outdir>/<name>.png (3x scale).
"""
import base64
import glob
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from simshot import convert  # noqa: E402


def main():
    target = sys.argv[1]
    script = sys.argv[2] if len(sys.argv) > 2 else ""
    out = sys.argv[3] if len(sys.argv) > 3 else "dev_out"
    port = sys.argv[4] if len(sys.argv) > 4 else sorted(glob.glob("/dev/cu.usbmodem*"))[0]
    root = os.path.join(os.path.dirname(__file__), "..")
    os.makedirs(out, exist_ok=True)
    code = (
        "import sys\n"
        "sys.argv[:] = ['sim', %r, %r]\n"
        "exec(open('/simdrv.py').read(), {'__name__': '__main__'})\n" % (target, script)
    )
    subprocess.run(["mpremote", "connect", port, "cp", os.path.join(root, "tools/sim.py"), ":/simdrv.py"],
                   check=True, stdout=subprocess.DEVNULL)
    p = subprocess.run(["mpremote", "connect", port, "exec", code], capture_output=True, text=True)
    subprocess.run(["mpremote", "connect", port, "rm", ":/simdrv.py"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    name = None
    buf = []
    for line in p.stdout.splitlines():
        if line.startswith("@@SHOT "):
            name = line[7:].strip()
            buf = []
        elif line.startswith("@@END") and name:
            data = base64.b64decode("".join(buf))
            path = os.path.join(out, name + ".bin")
            with open(path, "wb") as f:
                f.write(data)
            print(convert(path, 3))
            name = None
        elif name:
            buf.append(line.strip())
        else:
            print(line)
    if p.stderr:
        print(p.stderr[-2000:], file=sys.stderr)


if __name__ == "__main__":
    main()
