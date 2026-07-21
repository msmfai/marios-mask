#!/bin/bash
# The Brother's Mask item art: generate from the user's MM extraction and append to the
# icon/name yar archives (extracted/ is not git-tracked -> backup/restore, like the voice
# swap). Also generates the pickup-billboard header into the mod staging dir.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MM="${DSCE_MM_TREE:-$HERE/.work/mm}"
ICON_DIR="$MM/extracted/n64-us/assets/archives/icon_item_static"
NAME_DIR="$MM/extracted/n64-us/assets/archives/item_name_static"
SRC="$MM/extracted/n64-us/assets/objects/object_osn/happy_mask_salesman_mask_03.ci8.png"

case "$1" in
stage)
    DEST="$2"  # mm/src/dsce
    [ -f "$SRC" ] || { echo "ERROR: MM extraction missing (object_osn)"; exit 1; }
    # billboard + name; the pause icon is the circus leader's own (user kept that look)
    "$HERE/tools/gen_mask_item_art.py" "$ICON_DIR/circus_leader_mask_icon.rgba32.png" \
        /tmp/dsce_unused_icon.png \
        "$NAME_DIR/item_name_brothers_mask_eng.ia4.png" \
        "$DEST/dsce_mask_pickup_tex.h"
    for f in "$ICON_DIR/icon_item_static_yar.c" "$NAME_DIR/item_name_static.c"; do
        [ -f "$f.dsce-bak" ] || cp "$f" "$f.dsce-bak"
        cp "$f.dsce-bak" "$f"   # always append onto the pristine copy (idempotent)
    done
    cat >> "$NAME_DIR/item_name_static.c" <<'NAME'

u64 gItemNameBrothersMaskENGTex[] = { // DSCE: appended -> CmpDma index 120
#include "assets/archives/item_name_static/item_name_brothers_mask_eng.ia4.inc.c"
};
NAME
    echo "mask item: icon+name appended to archives"
    ;;
restore)
    for f in "$ICON_DIR/icon_item_static_yar.c" "$NAME_DIR/item_name_static.c"; do
        [ -f "$f.dsce-bak" ] && mv "$f.dsce-bak" "$f"
    done
    rm -f "$NAME_DIR/item_name_brothers_mask_eng.ia4.png"
    echo "mask item: archives restored"
    ;;
*) echo "usage: stage-mask-item.sh stage <destdir>|restore"; exit 1 ;;
esac
