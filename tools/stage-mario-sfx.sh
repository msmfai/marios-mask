#!/bin/bash
# Mint SM64's real SFX into the MM audio build (PC parity: real samples, exact mapping).
# stage: render via gen_mario_sfx.py, copy WAVs into the extracted samplebank, insert
#   XML entries (untracked files -- backed up), install Soundfont_41 + seq_0 channels +
#   table rows + spec include (tracked files -- the mod build's git-checkout reverts
#   them), and drop the shim's generated map header into $(MM)/src/dsce/.
# restore: undo the untracked-file edits (tracked ones are reverted by the build).
#
# Validation break switches (firehose rig, docs/FIREHOSE.md):
#   DSCE_BREAK_POOL=1   skip the permanent-pool budget (audio bug #1: total sfx mute)
#   DSCE_BREAK_FONT=1   skip the dispatch-handler font heal
#   (DSCE_BREAK_DUR / DSCE_BREAK_DELAY live in gen_mario_sfx.py)
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MM="${DSCE_MM_TREE:-$HERE/.work/mm}"
SM64="${DSCE_SM64_TREE:-$HERE/.work/sm64}"
GEN="$HERE/out/msfx"
SBDIR="$MM/extracted/n64-us/assets/audio/samples/SampleBank_0"
SBXML="$MM/extracted/n64-us/assets/audio/samplebanks/SampleBank_0.xml"
SFXML="$MM/extracted/n64-us/assets/audio/soundfonts/Soundfont_0.xml"

insert_frag() {
    python3 "$HERE/tools/insert_frag.py" "$1" "$2" "$3" "$4"
}

case "$1" in
stage)
    "$HERE/tools/gen_mario_sfx.py" "$SM64" "$GEN" "$GEN/dsce_msfx_map.h"
    for w in "$GEN"/dsce_*.wav; do cp "$w" "$SBDIR/"; done
    [ -f "$SBXML.msfx-bak" ] || cp "$SBXML" "$SBXML.msfx-bak"
    insert_frag "$SBXML" "$GEN/samples.xml.frag" '</SampleBank>' '<Sample Name="DSCE_'
    cp "$GEN/Soundfont_41.xml" "$(dirname "$SFXML")/Soundfont_41.xml"
    cp "$GEN/Soundfont_42.xml" "$(dirname "$SFXML")/Soundfont_42.xml"
    # Keep the vanilla headers as the final [1, 0] suffix. Sequence font operands
    # are reverse selectors, so inserting between 1 and 0 would redirect every
    # native enemy `font 1` command into a generated Mario font.
    insert_frag "$MM/assets/audio/sequences/seq_0.prg.seq" "$GEN/seq_include.frag" \
        '#include "Soundfont_1.h"' 'Soundfont_41.h'
    grep -q 'Soundfont_42.o' "$MM/spec/spec" || python3 - "$MM/spec/spec" << 'PYSPEC'
import io, sys
p = sys.argv[1]
s = io.open(p).read()
a = '    include "$(BUILD_DIR)/assets/audio/soundfonts/Soundfont_40.o"'
assert a in s
io.open(p, 'w').write(s.replace(a, a + '\n' + a.replace('_40', '_41')
    + '\n' + a.replace('_40', '_42'), 1))
PYSPEC
    grep -q 'CHAN_PL_DSCE_' "$MM/include/tables/sfx/playerbank_table.h" || \
        cat "$GEN/playerbank.frag" >> "$MM/include/tables/sfx/playerbank_table.h"
    # Voicebank has eight game-side-only entries behind `#ifndef _LANGUAGE_ASEQ`.
    # Appending after that block gives every generated voice a C id eight slots
    # beyond its sequence dispatch index. Insert before the block so both views
    # assign the same ordinal to every generated channel.
    insert_frag "$MM/include/tables/sfx/voicebank_table.h" "$GEN/voicebank.frag" \
        '#ifndef _LANGUAGE_ASEQ' 'CHAN_VO_DSCE_'
    "$HERE/tools/check_sfx_dispatch_alignment.py" \
        "$MM/include/tables/sfx/playerbank_table.h" "$GEN/playerbank.frag" \
        "$MM/include/tables/sfx/voicebank_table.h" "$GEN/voicebank.frag"
    # Keep the generated channels inside .startseq/.endseq. Appending them after
    # .endseq made the object file larger while leaving Sequence_0_Size at the
    # vanilla 0xC740. The audio heap consequently allocated only 0xC740 bytes and
    # loaded Soundfont_2 over the generated Mario channels at 0xC740..0xCB0F.
    insert_frag "$MM/assets/audio/sequences/seq_0.prg.seq" "$GEN/seq.frag" \
        '.endseq Sequence_0' 'CHAN_PL_DSCE_'
    # Restore both vanilla bank and one-shot-effect mode before every dispatch.
    # Restoring only the font left a generated normal-instrument selector live, so
    # subsequent vanilla effect ids played as grotesquely pitched instruments.
    if [ "${DSCE_BREAK_FONT:-0}" = "1" ]; then
        echo "msfx: FONT HEAL SKIPPED (validation)"
    else
        insert_frag "$MM/assets/audio/sequences/seq_0.prg.seq" "$GEN/seq_heal_player.frag" \
            '/* 0x00F5 [0xD8 0x00               ] */ vibdepth    0' 'DSCE-HEAL-P'
        python3 - "$MM/assets/audio/sequences/seq_0.prg.seq" << 'PYHEAL'
import io, sys
p = sys.argv[1]
s = io.open(p).read()
a = "/* 0xB2D3 [0xD8 0x00               ] */ vibdepth    0"
if "DSCE-HEAL-V" not in s:
    assert a in s
    s = s.replace(a, "    fontinstr Soundfont_0_ID, FONTANY_INSTR_SFX // DSCE-HEAL-V\n" + a, 1)
    io.open(p, 'w').write(s)
PYHEAL
    fi
    # budget Soundfonts 41/42 + 8KB headroom into the PERMANENT audio pool. The firehose
    # measured the pool 98.4% full when sized to exact fit; exhaustion here is audio
    # bug #1 (TOTAL sfx mute). DSCE_BREAK_POOL=1 skips the budget for rig validation.
    if [ "${DSCE_BREAK_POOL:-0}" = "1" ]; then
        echo "msfx: POOL BUDGET SKIPPED (validation)"
    else
        grep -q 'Soundfont_42_SIZE' "$MM/src/audio/session_init.c" || python3 - "$MM/src/audio/session_init.c" << 'PYSESS'
import io, sys
p = sys.argv[1]
s = io.open(p).read()
a = '#define SFX_SOUNDFONTS_SIZE (Soundfont_0_SIZE + Soundfont_1_SIZE + Soundfont_2_SIZE)'
assert a in s
io.open(p, 'w').write(s.replace(a,
    '#define SFX_SOUNDFONTS_SIZE (Soundfont_0_SIZE + Soundfont_1_SIZE + Soundfont_2_SIZE'
    ' + Soundfont_41_SIZE + Soundfont_42_SIZE + 0x2000)'
    ' /* DSCE: mario effect fonts + 8KB headroom (bug-1 insurance) */', 1))
PYSESS
    fi
    cp "$GEN/dsce_msfx_map.h" "$MM/src/dsce/dsce_msfx_map.h"
    echo "msfx: $(ls "$GEN"/dsce_*.wav | wc -l | tr -d ' ') SM64 sounds staged"
    ;;
restore)
    rm -f "$SBDIR"/dsce_*.wav "$(dirname "$SFXML")/Soundfont_41.xml" \
        "$(dirname "$SFXML")/Soundfont_42.xml"
    [ -f "$SBXML.msfx-bak" ] && mv "$SBXML.msfx-bak" "$SBXML"
    [ -f "$SFXML.msfx-bak" ] && mv "$SFXML.msfx-bak" "$SFXML"
    echo "msfx: restored"
    ;;
*) echo "usage: stage-mario-sfx.sh stage|restore"; exit 1 ;;
esac
