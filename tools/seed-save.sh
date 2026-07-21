#!/usr/bin/env bash
# Seed the current ROM build's mupen flash save with the canonical File-1 save (state/file1.fla,
# name "AAAAAAAA" created). mupen keys the save file by "<internal name>-<first 8 hex of ROM MD5>",
# so every rebuild starts empty and boot would hit name entry again (brittle). Deterministic seed:
# compute the name from the ROM and copy the canonical save over it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SAVEDIR="$HOME/Library/Application Support/Mupen64Plus/save"
CANON="$HERE/state/file1.fla"
[ -f "$CANON" ] || { echo "missing $CANON (canonical File-1 save)" >&2; exit 1; }
MD5=$(md5 -q "$HERE/out/mm-dsce.z64" | tr a-f A-F)
TARGET="ZELDA MAJORA'S MASK-${MD5:0:8}.fla"
cp "$CANON" "$SAVEDIR/$TARGET"
echo "seeded: $TARGET"
