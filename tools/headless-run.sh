#!/usr/bin/env bash
# Headless emulation of the DSCE mod ROM: NO rendering (--gfx dummy), no audio, uncapped speed.
# The input-script plugin supplies deterministic inputs and peeks the gDsceTelemetry RDRAM block
# into a CSV. This is the unit of the high-throughput behavioural/metamorphic test rig.
#
# Usage: headless-run.sh <rules-file> <telemetry.csv> <max-frames> [savestate] [extra env...]
# The gDsceTelemetry VA is auto-read from the freshest linker map.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
RULES="$1"; CSV="$2"; MAXF="$3"; STATE="${4:-}"

MM_TREE="${DSCE_MM_TREE:-$HERE/.work/mm}"
VA=$(grep -oE '0x80[0-9a-f]+\s+gDsceTelemetry' "$MM_TREE/build/n64-us/mm-n64-us.map" | awk '{print substr($1,3)}')
[ -n "$VA" ] || { echo "no gDsceTelemetry in linker map -- run 'make mod' first" >&2; exit 1; }

ARGS=(--nospeedlimit --gfx dummy --audio dummy
      --input "$HERE/tools/inputbot/mupen64plus-input-script.dylib"
      "$HERE/out/mm-dsce.z64")
[ -n "$STATE" ] && ARGS=(--savestate "$STATE" "${ARGS[@]}")

CT_INPUT_SCRIPT="$RULES" CT_DSCE_ADDR="$VA" CT_TELEMETRY="$CSV" CT_MAX_FRAMES="$MAXF" \
    mupen64plus "${ARGS[@]}"
