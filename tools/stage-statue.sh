#!/bin/bash
# Stage the Peach statue: SM64 peach model + parts table + the statue-pose anim
# (tuning.yaml PeachAnim index at PeachFrame), gray-tinted lights (stone).
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SM64="${DSCE_SM64_TREE:-$HERE/.work/sm64}"
STAGED="$1"   # mm/src/dsce

mkdir -p "$STAGED/sm64_assets/actors/peach"
cp "$SM64/actors/peach/model.inc.c" "$STAGED/sm64_assets/actors/peach/"
cp "$SM64"/actors/peach/*.inc.c "$STAGED/sm64_assets/actors/peach/" 2>/dev/null || true
# texture inc.c files are generated in the sm64 build tree
cp "$SM64"/build/us/actors/peach/*.inc.c "$STAGED/sm64_assets/actors/peach/" 2>/dev/null || true

"$HERE/tools/gen_geo_parts.py" "$SM64/actors/peach/geo.inc.c" peach_geo_000098 \
    sDscePeachParts "$STAGED/dsce_peach_parts.inc"

python3 - "$SM64" "$STAGED" "$HERE/tuning.yaml" <<'PYEOF'
import re, sys
sm64, staged, yaml = sys.argv[1:4]
# anim index from tuning (PeachAnim), resolved through peach's anim table
idx = 9
for line in open(yaml):
    m = re.match(r'PeachAnim:\s*(\d+)', line)
    if m:
        idx = int(m.group(1))
table = open(f'{sm64}/actors/peach/anims/table.inc.c').read()
syms = re.findall(r'&(peach_seg5_anim_\w+)', table)
sym = syms[idx]
addr = sym.replace('peach_seg5_anim_', '')
src = open(f'{sm64}/actors/peach/anims/anim_{addr}.inc.c').read()
# IDO ordering: arrays first, struct after (same fix as gen_mario_anims)
arrays = re.findall(r'static const (?:u16|s16) \w+\[\] = \{.*?\};', src, re.S)
structs = re.findall(r'static const struct Animation .*?\};', src, re.S)
with open(f'{staged}/dsce_peach_anim.inc', 'w') as f:
    f.write(f'/* GENERATED: peach statue pose anim index {idx} ({sym}) */\n')
    f.write('\n'.join(arrays) + '\n' + '\n'.join(structs) + '\n')
    f.write(f'#define sDscePeachPoseAnim {sym}\n')
print(f'statue: pose anim {idx} ({sym}) staged')
PYEOF

# stone: gray-desaturate every peach lights group in the staged model copy
python3 - "$STAGED/sm64_assets/actors/peach/model.inc.c" <<'PYEOF'
import re, sys
path = sys.argv[1]
t = open(path).read()
def gray(m):
    vals = [int(x, 16) for x in m.group(2).replace(' ', '').replace('\n', '').split(',') if x]
    out = []
    for i in range(0, len(vals), 3):
        r, g, b = vals[i:i+3]
        y = (r * 30 + g * 59 + b * 11) // 100
        out += [y, y, y]
    return m.group(1) + ', '.join(f'0x{v:02x}' for v in out) + ', ' + m.group(3)
t2, n = re.subn(r'(gdSPDefLights1\(\s*)((?:0x[0-9a-fA-F]+,?\s*){6})(0x[0-9a-fA-F]+)',
                lambda m: gray(m), t)
# STONE: strip the texture from every combiner -- pure shaded rock (the textured parts
# under gray light read as a discolored princess, not a statue)
t2, nc = re.subn(r'gsDPSetCombineMode\(G_CC_\w+, G_CC_\w+\)',
                 'gsDPSetCombineMode(G_CC_SHADE, G_CC_SHADE)', t2)
open(path, 'w').write(t2)
print(f'statue: {n} light groups stoned, {nc} combiners -> shade-only')
PYEOF

# stone the TEXTURES too (the dress/crown carry the color; lights alone can't gray her)
python3 - "$STAGED/sm64_assets/actors/peach" <<'PYEOF'
import glob, re, sys
count = 0
for f in glob.glob(f'{sys.argv[1]}/*rgba16.inc.c'):
    t = open(f).read()
    by = [int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', t)]
    out = []
    for i in range(0, len(by) - 1, 2):
        tex = (by[i] << 8) | by[i + 1]
        r, g, b, a = (tex >> 11) & 31, (tex >> 6) & 31, (tex >> 1) & 31, tex & 1
        y = (r * 30 + g * 59 + b * 11) // 100
        tex = (y << 11) | (y << 6) | (y << 1) | a
        out.append(f'0x{tex >> 8:02x}')
        out.append(f'0x{tex & 0xFF:02x}')
    with open(f, 'w') as fh:
        for i in range(0, len(out), 16):
            fh.write(','.join(out[i:i + 16]) + ',\n')
    count += 1
print(f'statue: {count} textures stoned')
PYEOF
