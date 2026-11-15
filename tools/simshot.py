#!/usr/bin/env python3
"""Convert simulator screenshots (raw byte-swapped RGB565 240x135) to PNG.

Usage: tools/simshot.py [dir=sim_out] [scale=3]
Writes <name>.png next to each <name>.bin.
"""
import glob
import os
import sys

from PIL import Image

W, H = 240, 135


def convert(path, scale):
    data = open(path, "rb").read()
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            o = (y * W + x) * 2
            c = (data[o] << 8) | data[o + 1]  # big-endian (panel order)
            r = (c >> 11) & 0x1F
            g = (c >> 5) & 0x3F
            b = c & 0x1F
            px[x, y] = (r * 255 // 31, g * 255 // 63, b * 255 // 31)
    if scale != 1:
        img = img.resize((W * scale, H * scale), Image.NEAREST)
    out = os.path.splitext(path)[0] + ".png"
    img.save(out)
    return out


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "sim_out"
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    for p in sorted(glob.glob(os.path.join(d, "*.bin"))):
        print(convert(p, scale))


if __name__ == "__main__":
    main()
