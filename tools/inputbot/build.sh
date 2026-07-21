#!/usr/bin/env bash
# Build the optional headless-test plugins from source. No emulator binary is bundled.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CC_BIN="${CC:-cc}"

case "$(uname -s)" in
    Darwin)
        DEFAULT_INCLUDE="/opt/homebrew/include/mupen64plus"
        SHARED_FLAGS=(-dynamiclib -undefined dynamic_lookup)
        ;;
    Linux)
        DEFAULT_INCLUDE="/usr/include/mupen64plus"
        SHARED_FLAGS=(-shared -fPIC)
        ;;
    *)
        echo "unsupported host for headless-test plugins: $(uname -s)" >&2
        exit 1
        ;;
esac

INCLUDE_DIR="${MUPEN64PLUS_INCLUDE:-$DEFAULT_INCLUDE}"
for header in m64p_types.h m64p_plugin.h m64p_common.h; do
    [ -f "$INCLUDE_DIR/$header" ] || {
        echo "missing $INCLUDE_DIR/$header" >&2
        echo "install Mupen64Plus development headers or set MUPEN64PLUS_INCLUDE" >&2
        exit 1
    }
done

"$CC_BIN" "${SHARED_FLAGS[@]}" -O2 -I"$INCLUDE_DIR" \
    -o "$HERE/mupen64plus-input-script.dylib" "$HERE/input_script_plugin.c" -lm
"$CC_BIN" "${SHARED_FLAGS[@]}" -O2 -I"$INCLUDE_DIR" \
    -o "$HERE/mupen64plus-video-null.dylib" "$HERE/video_null_plugin.c"

echo "built optional test plugins in $HERE"
