#!/usr/bin/env bash
# One-time bootstrap: build mips-linux-gnu binutils (o32-capable) and GNU libiconv
# into the private toolchain directory.
# Why from source: the decomp links elf32-tradbigmips (o32); the nix mips64 binutils on this
# machine only carries elf64/n32 emulations, so `ld -r` on soundfonts fails "file in wrong
# format". mm/docs/BUILDING_MACOS.md suggests 2.35, but modern clang rejects its configure;
# 2.42 builds clean on Apple Silicon and still carries elf32btsmip for mips-linux-gnu.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${DSCE_TOOLCHAIN:-$(cd "$HERE/.." && pwd)/toolchain}"
BINUTILS_VER=2.42
ICONV_VER=1.18
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || echo 8)"

if "$PREFIX/bin/mips-linux-gnu-ld" -V 2>/dev/null | grep -q elf32btsmip && \
   "$PREFIX/bin/gnu-iconv" --version >/dev/null 2>&1; then
    echo "toolchain already built: MIPS binutils + GNU iconv"
    exit 0
fi

mkdir -p "$PREFIX"
WORK="$PREFIX/_build"  # kept on failure so the *.log files survive for diagnosis
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"

if ! "$PREFIX/bin/mips-linux-gnu-ld" -V 2>/dev/null | grep -q elf32btsmip; then
    echo "== fetching binutils $BINUTILS_VER =="
    curl -sL -O "https://ftp.gnu.org/gnu/binutils/binutils-$BINUTILS_VER.tar.bz2"
    tar xjf "binutils-$BINUTILS_VER.tar.bz2"
    mkdir binutils-build && cd binutils-build

    echo "== configuring binutils (target mips-linux-gnu) =="
    # Apple clang, explicitly: the nix gcc in this shell env fails its own -g conftest.
    export CC="${CC:-/usr/bin/cc}" CXX="${CXX:-/usr/bin/c++}"
    "../binutils-$BINUTILS_VER/configure" --target=mips-linux-gnu --prefix="$PREFIX" \
        --disable-gdb --disable-werror --disable-gprofng \
        --with-system-zlib >configure.log 2>&1 || {
        echo "binutils configure FAILED — tail of $PWD/configure.log:" >&2
        tail -20 configure.log >&2
        exit 1
    }

    echo "== building binutils (-j$JOBS) =="
    make -j"$JOBS" >build.log 2>&1 || {
        echo "binutils build FAILED:" >&2; tail -20 build.log >&2; exit 1;
    }
    make install >install.log 2>&1
    cd "$WORK"
fi

if ! "$PREFIX/bin/gnu-iconv" --version >/dev/null 2>&1; then
    echo "== fetching GNU libiconv $ICONV_VER =="
    curl -sL -O "https://ftp.gnu.org/pub/gnu/libiconv/libiconv-$ICONV_VER.tar.gz"
    tar xzf "libiconv-$ICONV_VER.tar.gz"
    mkdir iconv-build && cd iconv-build
    "../libiconv-$ICONV_VER/configure" --prefix="$PREFIX" >configure.log 2>&1 || {
        echo "libiconv configure FAILED — tail of $PWD/configure.log:" >&2
        tail -20 configure.log >&2
        exit 1
    }
    echo "== building GNU libiconv (-j$JOBS) =="
    make -j"$JOBS" >build.log 2>&1 || {
        echo "libiconv build FAILED:" >&2; tail -20 build.log >&2; exit 1;
    }
    make install >install.log 2>&1
    ln -sf iconv "$PREFIX/bin/gnu-iconv"
fi

cd "$PREFIX" && rm -rf "$WORK"

echo "== verifying o32 emulation =="
"$PREFIX/bin/mips-linux-gnu-ld" -V | sed -n '1p;/emulations/,+6p'
"$PREFIX/bin/mips-linux-gnu-ld" -V | grep -q elf32btsmip || {
    echo "ERROR: built ld lacks elf32btsmip" >&2
    exit 1
}
echo "OK: $PREFIX/bin/mips-linux-gnu-*"
"$PREFIX/bin/gnu-iconv" --version | sed -n '1p'
