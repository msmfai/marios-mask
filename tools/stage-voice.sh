#!/bin/bash
# Swap Fierce Deity's voice samples (adult_link_*) for Mario clips, or restore them.
# Sources: the user's SM64 ROM extraction (installation contract). 20kHz mono s16 to
# match the donor SampleBank_0 entries, so no tracked XML changes are needed.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SM64_TREE="${DSCE_SM64_TREE:-$HERE/.work/sm64}"
MM_TREE="${DSCE_MM_TREE:-$HERE/.work/mm}"
SM64="$SM64_TREE/sound/samples"
DIR="$MM_TREE/extracted/n64-us/assets/audio/samples/SampleBank_0"
BAK="$DIR/.dsce-voice-backup"

pairs() {
    cat <<'MAP'
adult_link_attack1 sfx_mario/02_mario_yah.aiff
adult_link_attack2 sfx_mario/01_mario_jump_wah.aiff
adult_link_attack3 sfx_mario/00_mario_jump_hoo.aiff
adult_link_attack4 sfx_mario/02_mario_yah.aiff
adult_link_hup sfx_mario_peach/01_mario_hoohoo.aiff
adult_link_gasp1 sfx_mario/0A_mario_attacked.aiff
adult_link_strong_attack1 sfx_mario/04_mario_yahoo.aiff
adult_link_strong_attack2 sfx_mario/18_mario_waha.aiff
adult_link_falling1 sfx_mario_peach/00_mario_waaaooow.aiff
adult_link_falling2 sfx_mario/08_mario_whoa.aiff
MAP
}

case "$1" in
stage)
    [ -d "$SM64/sfx_mario" ] || { echo "ERROR: sm64 voice samples missing (extract the SM64 baserom)"; exit 1; }
    mkdir -p "$BAK"
    pairs | while read -r donor clip; do
        [ -f "$BAK/$donor.wav" ] || cp "$DIR/$donor.wav" "$BAK/$donor.wav"
        ffmpeg -v error -y -i "$SM64/$clip" -ac 1 -ar 20000 -sample_fmt s16 "$DIR/$donor.wav"
    done
    echo "voice: 10 Fierce Deity samples now speak Mario"
    ;;
restore)
    if [ -d "$BAK" ]; then
        pairs | while read -r donor clip; do
            [ -f "$BAK/$donor.wav" ] && cp "$BAK/$donor.wav" "$DIR/$donor.wav"
        done
        rm -rf "$BAK"
        echo "voice: donor samples restored"
    fi
    ;;
*) echo "usage: stage-voice.sh stage|restore"; exit 1 ;;
esac
