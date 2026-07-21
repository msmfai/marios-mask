#!/bin/bash
# Brother's Mask cosmetics, applied to the STAGED sm64 asset copies (regenerated each
# `make mod`, so no backups needed): recolor the cap/shirt/arms lights group to the
# tuning.yaml CapColor (the PC port's Luigi-fied green), and swap the cap's M-logo
# texture for a generated gold Triforce.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
STAGED="$1"   # path to the staged sm64_assets dir (mm/src/dsce/sm64_assets)
ORIGINAL_LOGO="$2" # user's extracted SM64 cap-logo PNG; supplies the alpha silhouette

val() { grep -E "^$1:" "$HERE/tuning.yaml" | head -1 | sed -E 's/^[^:]+:[[:space:]]*([0-9]+).*/\1/'; }
R=$(val CapColorR); G=$(val CapColorG); B=$(val CapColorB)
AR=$((R / 2)); AG=$((G / 2)); AB=$((B / 2))

python3 - "$STAGED/actors/mario/model.inc.c" "$AR" "$AG" "$AB" "$R" "$G" "$B" <<'PYEOF'
import re, sys
path, ar, ag, ab, r, g, b = sys.argv[1], *[int(x) for x in sys.argv[2:8]]
t = open(path).read()
new, n = re.subn(
    r'(static const Lights1 mario_red_lights_group = gdSPDefLights1\(\s*)0x[0-9a-fA-F]+, 0x[0-9a-fA-F]+, 0x[0-9a-fA-F]+,(\s*)0x[0-9a-fA-F]+, 0x[0-9a-fA-F]+, 0x[0-9a-fA-F]+,',
    rf'\g<1>0x{ar:02x}, 0x{ag:02x}, 0x{ab:02x},\g<2>0x{r:02x}, 0x{g:02x}, 0x{b:02x},',
    t)
assert n == 1, f"red lights group not found/matched ({n})"
open(path, 'w').write(new)
print(f"cosmetics: cap/shirt/arms lights -> ({r},{g},{b})")
PYEOF

"$HERE/tools/gen_triforce.py" "$ORIGINAL_LOGO" "$STAGED/actors/mario/mario_logo.rgba16.inc.c"

# scene-ambient blend needs the light groups mutable + linkable (the draw rescales them
# per frame from captured baselines)
sed -i '' 's/static const Lights1 mario_\([a-z0-9]*\)_lights_group/Lights1 mario_\1_lights_group/' \
    "$STAGED/actors/mario/model.inc.c"
echo "cosmetics: lights groups exported for ambient blend"
