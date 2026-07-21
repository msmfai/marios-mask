#!/usr/bin/env bash
# Public entry point: two user-supplied ROMs in, one locally built MM mod ROM out.
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
CALLER_PWD="$PWD"
SM64_SHA1="9bef1128717f958171a4afac3ed78ee2bb4e86ce"
MM_MD5="2a0a8acb61538235bc1094d297fb6556"
SM64_COMMIT="9921382a68bb0c865e5e45eb594d9c64db59b1af"
MM_COMMIT="f1a423cdcd2b159fd31662d2573af2b59edaa2cd"
WORK_DIR="${DSCE_WORK_DIR:-$PROJECT/.work}"
OUTPUT=""
JOBS="${JOBS:-}"
VERIFY_ONLY=0
LAUNDRY_HEALING=0
POSITIONAL=()
CREATED_ROM_LINKS=()
MM_MOD_STARTED=0

usage() {
    cat <<'EOF'
usage: tools/build_from_roms.sh [options] SM64_US.z64 MM_US.z64 [OUTPUT.z64]

Options:
  --verify-only       validate the two ROM revisions without cloning or building
  --laundry-healing   boot in Laundry Pool, full debug inventory/song, mask unowned
  --work-dir DIR      private dependency/build area (default: .work)
  --jobs N            parallel build jobs
  --output FILE       output path (same as the optional third positional argument)

Advanced: set DSCE_SM64_TREE, DSCE_MM_TREE, or DSCE_TOOLCHAIN to reuse local
checkouts/tooling. The default path clones pinned public decomp repositories into
.work; ROMs and extracted assets remain ignored local files and are never uploaded.
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "missing host dependency: $1 ($2)"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --verify-only) VERIFY_ONLY=1 ;;
        --laundry-healing) LAUNDRY_HEALING=1 ;;
        --work-dir) shift; [ "$#" -gt 0 ] || die "--work-dir needs a value"; WORK_DIR="$1" ;;
        --jobs) shift; [ "$#" -gt 0 ] || die "--jobs needs a value"; JOBS="$1" ;;
        --output) shift; [ "$#" -gt 0 ] || die "--output needs a value"; OUTPUT="$1" ;;
        -h|--help) usage; exit 0 ;;
        --) shift; while [ "$#" -gt 0 ]; do POSITIONAL+=("$1"); shift; done; break ;;
        -*) die "unknown option: $1" ;;
        *) POSITIONAL+=("$1") ;;
    esac
    shift
done

[ "${#POSITIONAL[@]}" -ge 2 ] && [ "${#POSITIONAL[@]}" -le 3 ] || { usage >&2; exit 2; }
[ -z "$OUTPUT" ] || [ "${#POSITIONAL[@]}" -eq 2 ] || die "choose --output or a third argument, not both"

SM64_ROM="${POSITIONAL[0]}"
MM_ROM="${POSITIONAL[1]}"
if [ -z "$OUTPUT" ]; then
    if [ "${#POSITIONAL[@]}" -eq 3 ]; then
        OUTPUT="${POSITIONAL[2]}"
    elif [ "$LAUNDRY_HEALING" -eq 1 ]; then
        OUTPUT="$PWD/mm-dsce-test-laundry-pool-nomask-debug.z64"
    else
        OUTPUT="$PWD/mm-dsce-mario.z64"
    fi
fi

# make -C changes directory to PROJECT, so every path passed through to Make must be
# anchored to the caller first. Without this, a relative --work-dir can build into one
# directory and the wrapper can silently copy a stale ROM from another.
absolute_path() {
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf '%s/%s\n' "$CALLER_PWD" "$1" ;;
    esac
}
WORK_DIR="$(absolute_path "$WORK_DIR")"
OUTPUT="$(absolute_path "$OUTPUT")"
[ -f "$SM64_ROM" ] || die "SM64 ROM not found: $SM64_ROM"
[ -f "$MM_ROM" ] || die "Majora's Mask ROM not found: $MM_ROM"
require_command awk "install standard POSIX command-line utilities"

sha1_file() {
    if command -v shasum >/dev/null 2>&1; then shasum -a 1 "$1" | awk '{print $1}'
    elif command -v sha1sum >/dev/null 2>&1; then sha1sum "$1" | awk '{print $1}'
    else die "need shasum or sha1sum"
    fi
}

md5_file() {
    if command -v md5 >/dev/null 2>&1; then md5 -q "$1"
    elif command -v md5sum >/dev/null 2>&1; then md5sum "$1" | awk '{print $1}'
    else die "need md5 or md5sum"
    fi
}

SM64_ACTUAL="$(sha1_file "$SM64_ROM")"
MM_ACTUAL="$(md5_file "$MM_ROM")"
[ "$SM64_ACTUAL" = "$SM64_SHA1" ] || die "unsupported SM64 ROM (need US SHA-1 $SM64_SHA1; got $SM64_ACTUAL)"
[ "$MM_ACTUAL" = "$MM_MD5" ] || die "unsupported MM ROM (need US compressed MD5 $MM_MD5; got $MM_ACTUAL)"
echo "ROM revisions OK: SM64 US + Majora's Mask US"
[ "$VERIFY_ONLY" -eq 0 ] || exit 0

for dependency in git python3 curl rsync ffmpeg tar cc c++ xml2-config; do
    require_command "$dependency" "see README.md, Alpha support and host requirements"
done
if ! python3 -c 'import pip, venv' >/dev/null 2>&1; then
    die "Python 3 needs the pip and venv modules (see README.md)"
fi

if [ "$(uname -s)" = Darwin ]; then
    require_command gmake "install GNU Make (for example: brew install make)"
    MAKE_BIN="gmake"
    if [ "$(uname -m)" = arm64 ]; then
        require_command brew "the pinned MM asset tool uses Homebrew libpng on macOS arm64"
        brew list libpng >/dev/null 2>&1 || die "missing host dependency: Homebrew libpng"
    fi
else
    require_command make "install GNU Make"
    MAKE_BIN="make"
fi
"$MAKE_BIN" --version 2>/dev/null | grep -q "GNU Make" || die "$MAKE_BIN is not GNU Make"

case "$JOBS" in
    '') JOBS="$(sysctl -n hw.ncpu 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)" ;;
    *[!0-9]*|0) die "--jobs must be a positive integer" ;;
esac

mkdir -p "$WORK_DIR"
SM64_TREE="$(absolute_path "${DSCE_SM64_TREE:-$WORK_DIR/sm64}")"
MM_TREE="$(absolute_path "${DSCE_MM_TREE:-$WORK_DIR/mm}")"
TOOLCHAIN="$(absolute_path "${DSCE_TOOLCHAIN:-$WORK_DIR/toolchain}")"

clone_pinned() {
    local url="$1" commit="$2" dest="$3" label="$4"
    if [ ! -d "$dest/.git" ]; then
        [ ! -e "$dest" ] || die "$label dependency path exists but is not a Git checkout: $dest"
        echo "Cloning pinned $label sources..."
        git clone --filter=blob:none "$url" "$dest"
        git -C "$dest" checkout --detach "$commit"
    fi
    local actual
    actual="$(git -C "$dest" rev-parse HEAD)"
    [ "$actual" = "$commit" ] || die "$label checkout must be $commit (found $actual at $dest)"
}

clone_pinned "https://github.com/n64decomp/sm64.git" "$SM64_COMMIT" "$SM64_TREE" "SM64"
clone_pinned "https://github.com/zeldaret/mm.git" "$MM_COMMIT" "$MM_TREE" "Majora's Mask"

cleanup() {
    local p
    if [ "$MM_MOD_STARTED" -eq 1 ]; then
        # `make mod` stages both tracked patches and ignored extracted audio/archive
        # files.  Recover all of them even when an early staging command fails.
        "$MAKE_BIN" -s -C "$PROJECT" restore-mm MM="$MM_TREE" >/dev/null || true
    fi
    for p in "${CREATED_ROM_LINKS[@]}"; do
        [ -L "$p" ] && rm "$p"
    done
}
trap cleanup EXIT INT TERM

absolute_file() { (cd "$(dirname "$1")" && printf '%s/%s\n' "$PWD" "$(basename "$1")"); }

stage_rom_link() {
    local source="$1" target="$2" kind="$3" expected="$4" actual
    mkdir -p "$(dirname "$target")"
    if [ -e "$target" ] || [ -L "$target" ]; then
        case "$kind" in
            sha1) actual="$(sha1_file "$target")" ;;
            md5) actual="$(md5_file "$target")" ;;
        esac
        [ "$actual" = "$expected" ] || die "existing baserom has the wrong revision: $target"
        return
    fi
    ln -s "$(absolute_file "$source")" "$target"
    CREATED_ROM_LINKS+=("$target")
}

stage_rom_link "$SM64_ROM" "$SM64_TREE/baserom.us.z64" sha1 "$SM64_SHA1"
stage_rom_link "$MM_ROM" "$MM_TREE/baseroms/n64-us/baserom.z64" md5 "$MM_MD5"

if ! "$TOOLCHAIN/bin/mips-linux-gnu-ld" -V 2>/dev/null | grep -q elf32btsmip || \
   ! "$TOOLCHAIN/bin/gnu-iconv" --version >/dev/null 2>&1; then
    "$MAKE_BIN" -C "$PROJECT" toolchain TOOLCHAIN="$TOOLCHAIN"
fi

# The pinned SM64 Makefile ignores an explicit CROSS path while detecting binutils:
# it calls `command -v mips-linux-gnu-ld` itself.  Put our private toolchain on PATH
# before invoking it, then require real generated files so an interrupted extraction
# cannot be mistaken for a complete build merely because it left a directory behind.
export PATH="$TOOLCHAIN/bin:$PATH"
command -v mips-linux-gnu-ld >/dev/null 2>&1 || die "private MIPS toolchain is not discoverable on PATH"

if [ ! -f "$SM64_TREE/actors/mario/model.inc.c" ] || \
   [ ! -f "$SM64_TREE/build/us/actors/mario/mario_logo.rgba16.inc.c" ] || \
   [ ! -f "$SM64_TREE/build/us/actors/peach/peach_dress.rgba16.inc.c" ]; then
    echo "Extracting SM64 assets from the supplied ROM..."
    # A pristine decomp checkout tracks the model C but not the PNGs.  Extract them
    # before asking the shell to enumerate conversion targets; otherwise the glob is
    # empty and a first-ever build fails even though an already-used checkout works.
    if ! compgen -G "$SM64_TREE/actors/mario/*.png" >/dev/null; then
        (cd "$SM64_TREE" && python3 extract_assets.py us)
    fi
    SM64_ASSET_TARGETS=()
    for source in "$SM64_TREE"/actors/mario/*.png "$SM64_TREE"/actors/peach/*.png; do
        [ -f "$source" ] || continue
        relative="${source#"$SM64_TREE"/}"
        SM64_ASSET_TARGETS+=("build/us/${relative%.png}.inc.c")
    done
    [ "${#SM64_ASSET_TARGETS[@]}" -gt 0 ] || die "SM64 extraction produced no Mario/Peach textures"
    # Generate only the extracted assets consumed by this mod.  Building the original
    # SM64 executable is unnecessary and would add a host-specific 32-bit compiler
    # requirement that has nothing to do with converting the user's ROM assets.
    "$MAKE_BIN" -C "$SM64_TREE" -j"$JOBS" VERSION=us \
        CROSS="$TOOLCHAIN/bin/mips-linux-gnu-" "${SM64_ASSET_TARGETS[@]}"
fi

MM_ASSET_SENTINEL="$MM_TREE/extracted/n64-us/assets/objects/object_osn/happy_mask_salesman_mask_03.ci8.png"
if [ ! -f "$MM_ASSET_SENTINEL" ]; then
    echo "Extracting Majora's Mask assets from the supplied ROM..."
    MM_BOOTSTRAP_ARGS=(
        "N_THREADS=$JOBS"
        "MIPS_BINUTILS_PREFIX=$TOOLCHAIN/bin/mips-linux-gnu-"
        "ICONV=$TOOLCHAIN/bin/gnu-iconv"
    )
    if [ "$(uname -s)" = Darwin ] && [ -x /usr/bin/clang ] && [ -x /usr/bin/clang++ ]; then
        # Avoid PATH-injected GCC wrappers that require a separate dsymutil on macOS.
        MM_BOOTSTRAP_ARGS+=("CC=/usr/bin/clang" "CXX=/usr/bin/clang++")
    fi
    if [ ! -x "$MM_TREE/.venv/bin/python3" ]; then
        "$MAKE_BIN" -C "$MM_TREE" venv "${MM_BOOTSTRAP_ARGS[@]}"
    fi
    "$MAKE_BIN" -C "$MM_TREE" -j"$JOBS" setup "${MM_BOOTSTRAP_ARGS[@]}"
    "$MAKE_BIN" -C "$MM_TREE" -j"$JOBS" assets "${MM_BOOTSTRAP_ARGS[@]}"
    [ -f "$MM_ASSET_SENTINEL" ] || die "Majora's Mask extraction completed without object_osn"
fi

echo "Building Brother's Mask ROM..."
MOD_ARGS=()
BUILT_NAME="mm-dsce.z64"
if [ "$LAUNDRY_HEALING" -eq 1 ]; then
    MOD_ARGS+=(TESTBOOT=1 TB_SCENE=LAUNDRY_POOL TB_GRANT_MASK=0 DEBUG=1)
    BUILT_NAME="mm-dsce-test-laundry-pool-nomask-debug.z64"
fi
MM_MOD_STARTED=1
"$MAKE_BIN" -C "$PROJECT" -j"$JOBS" mod \
    MM="$MM_TREE" SM64="$SM64_TREE" TOOLCHAIN="$TOOLCHAIN" OUT="$WORK_DIR/out" \
    "${MOD_ARGS[@]}"
MM_MOD_STARTED=0

BUILT="$WORK_DIR/out/$BUILT_NAME"
[ -f "$BUILT" ] || die "build completed without expected output: $BUILT"
mkdir -p "$(dirname "$OUTPUT")"
cp "$BUILT" "$OUTPUT"
if [ -f "$BUILT.va" ]; then
    cp "$BUILT.va" "$OUTPUT.va"
fi
if [ -f "$MM_TREE/build/n64-us/mm-n64-us.map" ]; then
    cp "$MM_TREE/build/n64-us/mm-n64-us.map" "$OUTPUT.map"
fi
echo "Built locally: $OUTPUT"
if [ "$LAUNDRY_HEALING" -eq 1 ]; then
    echo "Debug sidecars: $OUTPUT.va + $OUTPUT.map"
fi
echo "Do not upload or redistribute the output ROM."
