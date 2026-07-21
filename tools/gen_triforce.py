#!/usr/bin/env python3
"""Generate the Brother's Mask cap emblem: a gold Triforce on Mario's original
alpha-masked white cap badge, as a raw rgba16 byte list (32x32).

Usage: gen_triforce.py <original_logo_png> <out_inc_c>
"""
import sys

from gen_mask_item_art import png_read

W = H = 32
WHITE = 0xFFFF
TRANSPARENT = 0xFFFE
GOLD = (31 << 11) | (26 << 6) | (2 << 1) | 1   # warm triforce gold
SHADOW = (24 << 11) | (19 << 6) | (1 << 1) | 1  # darker gold, bottom-left tris


def in_tri(px, py, ax, ay, bx, by, cx, cy):
    def side(x1, y1, x2, y2):
        return (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    d1, d2, d3 = side(ax, ay, bx, by), side(bx, by, cx, cy), side(cx, cy, ax, ay)
    neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (neg and pos)


def main():
    original, out = sys.argv[1:3]
    w, h, source = png_read(original)
    assert (w, h) == (W, H), f"expected a 32x32 Mario logo, got {w}x{h}"
    # Keep the donor ROM's exact alpha silhouette.  The former generator made every
    # background texel opaque white, turning the curved badge into a solid polygon.
    # The smaller Triforce fits inside the original badge rather than touching its rim.
    top = (16.0, 7.0)
    bl = (8.0, 24.0)
    br = (24.0, 24.0)
    ml = ((top[0] + bl[0]) / 2, (top[1] + bl[1]) / 2)   # left midpoint
    mr = ((top[0] + br[0]) / 2, (top[1] + br[1]) / 2)   # right midpoint
    mb = ((bl[0] + br[0]) / 2, bl[1])                   # bottom midpoint
    texels = []
    for y in range(H):
        for x in range(W):
            p = (x + 0.5, y + 0.5)
            if source[y * W + x][3] < 128:
                texels.append(TRANSPARENT)
            elif in_tri(*p, *top, *ml, *mr):
                texels.append(GOLD)      # top triangle
            elif in_tri(*p, *ml, *bl, *mb):
                texels.append(SHADOW)    # bottom-left
            elif in_tri(*p, *mr, *mb, *br):
                texels.append(GOLD)      # bottom-right
            else:
                texels.append(WHITE)
    with open(out, "w") as f:
        by = []
        for t in texels:
            by.append(f"0x{(t >> 8) & 0xFF:02x}")
            by.append(f"0x{t & 0xFF:02x}")
        for i in range(0, len(by), 16):
            f.write(",".join(by[i:i + 16]) + ",\n")
    opaque = sum(t & 1 for t in texels)
    print(f"gen_triforce: {W}x{H} rgba16, {opaque} opaque texels -> {out}")


if __name__ == "__main__":
    main()
