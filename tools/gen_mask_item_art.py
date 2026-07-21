#!/usr/bin/env python3
"""Generate the Brother's Mask item art from the user's MM extraction:
  - 32x32 rgba32 pause/HUD icon, sourced from the Happy Mask Salesman backpack's
    Mario mask texture (the famous cameo), upscaled and centered
  - 128x16 ia4 item-name texture "BROTHER'S MASK" (built-in 5x7 pixel font)
  - a C header with the icon pixels for the in-world pickup billboard

Minimal PNG read/write (zlib + struct only; handles paletted+tRNS and gray/RGBA).

Usage: gen_mask_item_art.py <mask03_ci8_png> <out_icon_png> <out_name_png> <out_billboard_h>
"""
import struct
import sys
import zlib


def png_read(path):
    d = open(path, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n"
    pos, w, h, bitd, ctype, plte, trns, idat = 8, 0, 0, 0, 0, b"", b"", b""
    while pos < len(d):
        ln, typ = struct.unpack_from(">I4s", d, pos)
        body = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitd, ctype = struct.unpack_from(">IIBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    assert bitd == 8, f"bit depth {bitd} unsupported"
    stride = w * nch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]
        row = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = row[i - nch] if i >= nch else 0
            b = prev[i]
            c = prev[i - nch] if i >= nch else 0
            if f == 1:
                row[i] = (row[i] + a) & 0xFF
            elif f == 2:
                row[i] = (row[i] + b) & 0xFF
            elif f == 3:
                row[i] = (row[i] + (a + b) // 2) & 0xFF
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + pr) & 0xFF
        out += row
        prev = row
    px = []
    for i in range(w * h):
        if ctype == 3:
            idx = out[i]
            r, g, b = plte[idx * 3:idx * 3 + 3]
            a = trns[idx] if idx < len(trns) else 255
            px.append((r, g, b, a))
        elif ctype == 6:
            px.append(tuple(out[i * 4:i * 4 + 4]))
        elif ctype == 2:
            r, g, b = out[i * 3:i * 3 + 3]
            px.append((r, g, b, 255))
        else:
            v = out[i * nch]
            px.append((v, v, v, out[i * 2 + 1] if ctype == 4 else 255))
    return w, h, px


def png_write(path, w, h, px, gray_alpha=False):
    def chunk(typ, body):
        c = struct.pack(">I", len(body)) + typ + body
        return c + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b, a = px[y * w + x]
            if gray_alpha:
                raw += bytes((r, a))
            else:
                raw += bytes((r, g, b, a))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 4 if gray_alpha else 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + \
        chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")
    open(path, "wb").write(data)


FONT = {  # 5x7, rows of 5 bits, MSB left
    'B': [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E], 'R': [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E], 'T': [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    'H': [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11], 'E': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    'S': [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E], 'M': [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    'A': [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11], 'K': [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    "'": [0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00], ' ': [0, 0, 0, 0, 0, 0, 0],
}


def main():
    src, out_icon, out_name, out_bb = sys.argv[1:5]

    # source: the circus leader's own 32x32 icon (the user kept that look); resample 1:1
    w, h, px = png_read(src)
    icon = [(0, 0, 0, 0)] * (32 * 32)
    for y in range(32):
        for x in range(32):
            icon[y * 32 + x] = px[min(h - 1, y * h // 32) * w + min(w - 1, x * w // 32)]
    png_write(out_icon, 32, 32, icon)

    # name: 128x16 ia4-style (gray+alpha png; the asset pipeline quantizes)
    text = "BROTHER'S MASK"
    name = [(0, 0, 0, 0)] * (128 * 16)
    tx = (128 - len(text) * 6) // 2
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch, FONT[' '])
        for gy in range(7):
            for gx in range(5):
                if glyph[gy] & (0x10 >> gx):
                    x = tx + ci * 6 + gx
                    y = 4 + gy
                    name[y * 128 + x] = (255, 255, 255, 255)
    png_write(out_name, 128, 16, name)  # converter requires RGBA color type

    # billboard header: rgba16 C array (in-world pickup drawn from the code segment)
    with open(out_bb, "w") as f:
        f.write("/* GENERATED by gen_mask_item_art.py -- Brother's Mask pickup billboard, rgba16 32x32 */\n")
        f.write("static const unsigned short gDsceMaskPickupTex[32*32] = {\n")
        for y in range(32):
            row = []
            for x in range(32):
                r, g, b, a = icon[y * 32 + x]
                row.append(f"0x{((r >> 3) << 11) | ((g >> 3) << 6) | ((b >> 3) << 1) | (1 if a > 127 else 0):04x}")
            f.write("    " + ", ".join(row) + ",\n")
        f.write("};\n")
    print(f"mask item art: icon={out_icon} name={out_name} billboard={out_bb}")


if __name__ == "__main__":
    main()
