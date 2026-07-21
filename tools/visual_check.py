#!/usr/bin/env python3
"""Visual cosmetic assertion: the Brother's Mask Mario must be GREEN, not red.

Boots the test ROM windowed (GL renderer), screenshots mid-walk, and asserts the frame
contains no red-dominant cluster (stock Mario's cap/shirt would produce one; Termina
Field has no other red at the spawn) plus a sane green presence. PNG is decoded via
sips -> BMP (no external Python deps).
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(HERE, "out", "mm-dsce-test.z64")
SHOTS = os.path.join(HERE, "out", "emu-shots")
INPUTBOT = os.path.join(HERE, "tools", "inputbot", "mupen64plus-input-script.dylib")


def bmp_pixels(path):
    """Middle band only: the HUD (hearts top, clock bottom) is legitimately red."""
    d = open(path, "rb").read()
    off = struct.unpack_from("<I", d, 10)[0]
    w, h = struct.unpack_from("<ii", d, 18)
    bpp = struct.unpack_from("<H", d, 28)[0] // 8
    row = (w * bpp + 3) & ~3
    hh = abs(h)
    for y in range(int(hh * 0.30), int(hh * 0.75)):
        for x in range(w):
            i = off + y * row + x * bpp
            b, g, r = d[i], d[i + 1], d[i + 2]
            yield r, g, b


def main():
    for f in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if f.endswith(".png"):
            os.remove(os.path.join(SHOTS, f))
    rules = "".join(f"{f} {f+15} L,R,Z 0 0\n" for f in range(600, 2300, 60))
    rules += "2400 2900 NONE 0 70\n"
    d = tempfile.mkdtemp(prefix="dsce-visual-")
    rp = os.path.join(d, "rules")
    open(rp, "w").write(rules)
    va = open(ROM + ".va").read().split("gDsceTelemetry=")[1].split()[0]
    env = dict(os.environ, CT_INPUT_SCRIPT=rp, CT_DSCE_ADDR=va,
               CT_SCREENSHOT_EVERY="2700", CT_MAX_FRAMES="2900")
    subprocess.run(["mupen64plus", "--nospeedlimit", "--windowed",
                    "--gfx", "mupen64plus-video-glide64mk2", "--input", INPUTBOT, ROM],
                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=600, check=False)
    shots = sorted(f for f in os.listdir(SHOTS) if f.endswith(".png"))
    if not shots:
        sys.exit("visual: no screenshot captured")
    png = os.path.join(SHOTS, shots[-1])
    bmp = os.path.join(d, "shot.bmp")
    subprocess.run(["sips", "-s", "format", "bmp", png, "--out", bmp],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    red = green = 0
    for r, g, b in bmp_pixels(bmp):
        if r > 140 and r > 3 * g and r > 3 * b:  # saturated red (cap/shirt), not brown dirt
            red += 1
        elif g > 70 and g > r + 15 and g > b + 15:  # difference-based: robust to the brightness dimmer
            green += 1
    print(f"visual: red-dominant={red} green-dominant={green} ({shots[-1]})")
    ok = red < 25 and green > 40  # red-absence is THE assertion; green floor scaled for the pulled-back SM64 camera
    print("[PASS] cosmetics: Mario is green, not red" if ok else
          f"[FAIL] cosmetics: expected green Mario (red={red} green={green})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
