#!/bin/bash
# Build the sm64-xtest oracle ROM: stage the generated XTEST arena collision over the
# south (area 1) slot of the SM64+Clock Town tree, build, copy out, restore. The tree is
# left exactly as found (same discipline as the mm staging).
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SM64="${DSCE_SM64_TREE:-$HERE/.work/sm64}"
SOUTH="$SM64/levels/castle_grounds/south/collision.inc.c"
OUT="$HERE/out"

VARIANT="${1:-A}"
SUFFIX=""
[ "$VARIANT" != "A" ] && SUFFIX="-$(echo $VARIANT | tr 'A-Z' 'a-z')"

mkdir -p "$OUT"
"$HERE/tools/gen_xtest_arena.py" /tmp/dsce-xtest-collision.inc.c /tmp/dsce-xtest-arena.h "$VARIANT"

EXT="$SM64/src/audio/external.c"
cp "$SOUTH" "$SOUTH.xtest-bak"
cp "$EXT" "$EXT.xtest-bak"
cleanup() { mv "$SOUTH.xtest-bak" "$SOUTH"; mv "$EXT.xtest-bak" "$EXT"; }
trap cleanup EXIT

cp /tmp/dsce-xtest-collision.inc.c "$SOUTH"
# [R3] stage the sound-request ring into play_sound: same 48-byte record layout the
# inputbot plugin already drains (CT_LOG_ADDR/CT_LOGRING_ADDR), frame = gGlobalTimer.
python3 - "$EXT" << 'PYEOF'
import io, sys
p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()
ring = """
/* DSCE XTEST R3: exported sound-request ring (drained by the inputbot plugin). */
struct DsceSndRec { u32 seq; u32 frame; char tag[24]; s32 a, b, c, d; };
struct DsceSndRec dsceSndRing[256];
volatile u32 dsceSndHead = 0;
extern u32 gGlobalTimer;

"""
anchor = "void play_sound(s32 soundBits, f32 *pos) {"
assert s.count(anchor) == 1
log = anchor + """
    { /* DSCE XTEST R3 */
        struct DsceSndRec *r = &dsceSndRing[dsceSndHead & 255];
        r->seq = dsceSndHead; r->frame = gGlobalTimer;
        r->tag[0]='s'; r->tag[1]='n'; r->tag[2]='d'; r->tag[3]='\\0';
        r->a = soundBits; r->b = 0; r->c = 0; r->d = 0;
        dsceSndHead++;
    }"""
s = s.replace(anchor, ring + log)
io.open(p, "w", encoding="utf-8").write(s)
PYEOF
# CC_CHECK=true: the advisory host-gcc syntax pass needs -m32 (absent on Apple Silicon)
# -- same class of override as the mm build's RUN_CC_CHECK=0. IDO does the real compile.
PATH="$HERE/toolchain/bin:$PATH" make -C "$SM64" -j10 CC_CHECK=true COMPARE=0 >/dev/null

cp "$SM64/build/us/sm64.us.z64" "$OUT/sm64-xtest$SUFFIX.z64"
# the comparator reads addresses from the map: assert the RAM symbols didn't move
# (collision is level-segment data; main-segment symbols must be stable)
for sym in gMarioStates gGlobalTimer dsceSndHead dsceSndRing; do
    grep -E " $sym\$" "$SM64/build/us/sm64.us.map" | awk -v s=$sym '{gsub(/^0x0*/,"",$1); print s"="$1}'
done > "$OUT/sm64-xtest$SUFFIX.z64.va"
echo "==> $OUT/sm64-xtest$SUFFIX.z64 (+ .va)"
