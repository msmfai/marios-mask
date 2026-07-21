# DSCE Brother's Mask — N64 ROM edition

> **v0.1.0-alpha.1 release candidate:** source-only, experimental, and not yet
> authorized for publication. See [RELEASE_V0.1_ALPHA.md](RELEASE_V0.1_ALPHA.md).

The **ROM recompilation version** of the Mario-in-MM mod: a modified Majora's Mask
ROM built from the ZeldaRET decomp and intended for N64-compatible hardware. This is
an experimental alpha; supported-host status and remaining validation work are below.

`github/brothers-mask/` is the standalone, clean-history GitHub release root. It has no
runtime or build dependency on another part of this monorepo and contains no ROM,
extracted texture/model/audio, generated ROM, or Mario voice file. The user supplies
two supported ROM revisions and every game asset is extracted locally during the
build. See [GITHUB_RELEASE.md](GITHUB_RELEASE.md) before publishing.

## Two ROMs in, one mod ROM out

Supported inputs:

- Super Mario 64 (US): SHA-1 `9bef1128717f958171a4afac3ed78ee2bb4e86ce`
- Majora's Mask (US, compressed): MD5 `2a0a8acb61538235bc1094d297fb6556`

```sh
tools/build_from_roms.sh \
  "/path/to/Super Mario 64 (USA).z64" \
  "/path/to/Majora's Mask (USA).z64" \
  "$PWD/mm-dsce-mario.z64"
```

The wrapper verifies both revisions, clones pinned SM64/MM decomp sources into the
ignored `.work/` directory, extracts assets locally, builds the mod, and copies only
the local output path requested. It never downloads a ROM and does not create a patch
containing Nintendo assets. The output ROM is for the user's local use; do not upload
or redistribute it.

On save storage with no player data that has not previously been offered this seed,
the release creates an optional File 1 named `Link`. It is the coherent post-tutorial
state: human Link at Dawn of the First Day in South Clock Town with Tatl, magic, the
Ocarina of Time, Deku Mask, Song of Time, Song of Healing, and the completed Clock
Tower intro flags. File 2 remains empty and ordinary New Game creation is unchanged.
Existing or suspicious/corrupt saves are never overwritten, and deleting the supplied
file does not recreate it on a later launch.

For a quick input check without cloning or building:

```sh
tools/build_from_roms.sh --verify-only SM64_US.z64 MM_US.z64
```

## Alpha support and host requirements

"Standalone" means this source tree does not read another part of the private
monorepo. It does **not** mean that a ROM recompilation has no host dependencies.
The end-to-end release build has been exercised on macOS 26.5.2 arm64. Linux and WSL
are supported by the pinned upstream build systems but have not yet passed this
release candidate's clean-build gate; native Windows is unsupported.

A full build needs network access for pinned source dependencies and these host tools:

- Bash, Git, Python 3 with `venv`/`pip`, `curl`, `rsync`, `ffmpeg`, `tar`, and common
  POSIX utilities;
- GNU Make (`gmake` on macOS) and a C/C++17 build toolchain;
- libpng, libxml2, and zlib development headers (`libpng-dev`/`libxml2-dev`/
  `zlib1g-dev` on Debian-like Linux; Homebrew `libpng`/`libxml2` on macOS).

The wrapper builds GNU binutils 2.42 and GNU libiconv 1.18 into the ignored private
work directory when needed. It fetches pinned upstream source trees and then runs the
pinned MM tree's declared bootstrap, which resolves version-ranged Python packages and
downloads the IDO static-recomp v1.2 tools. The build is reproducible in the recorded
release environment but is not yet a hermetic, lockfile-complete build. None of these
steps fetches either ROM or extracted game data. `--verify-only` needs only the two
local files and standard checksum tools.

This is an experimental alpha. Only the exact NTSC-US revisions above are accepted.
The macOS emulator path has the most testing; the mandatory real-console/EverDrive
gate remains open, and movement, camera, sound, save, and quest integration still need
broad play coverage. Back up saves before testing. After publication, report bugs in
GitHub Issues with the host OS, build command, scene, exact actions, and observed result;
never attach ROMs, extracted assets, saves, captures containing copyrighted media, or
other Nintendo data. Security-sensitive reports should use GitHub's private
vulnerability-reporting route rather than a public issue.

For the playable acquisition test, boot directly into Laundry Pool with the debug save
(Ocarina + Song of Healing available) but with the Brother's Mask deliberately absent:

```sh
tools/build_from_roms.sh --laundry-healing \
  SM64_US.z64 MM_US.z64 out/mm-dsce-test-laundry-pool-nomask-debug.z64
```

Stand near the stone Peach statue and play the Song of Healing. Touch the resulting
mask pickup; it auto-equips to C-Left, ready to transform. The `out/` directory and all
`.z64` files are ignored by Git. This canonical interactive-test preset always enables
the debug firehose and copies `.z64.va` plus `.z64.map` symbol sidecars next to the ROM;
ordinary non-test builds remain non-debug.

To run that debug ROM with automatic RetroArch capture and post-mortem diagnosis:

```sh
tools/run_debug_release.py
```

The launcher accepts only a `*-debug.z64` with its `.z64.va` telemetry symbols. Every
second it reads the in-ROM firehose and frozen sequencer flight recorder through
RetroArch's built-in read-only memory command (no savestates, writes, or emulator
changes). Once the first sequencer fault is frozen, it tells you that you can close
RetroArch immediately. When RetroArch closes, it builds a per-run ClickHouse database
plus `diagnosis.txt`/`diagnosis.json`. Each session is kept under the ignored path
`out/debug-runs/<UTC timestamp>/`; see [docs/FIREHOSE.md](docs/FIREHOSE.md) for its
strict layout and queries. This is deliberately host-side: the ROM never receives
filesystem access and ordinary release ROMs cannot invoke the logger. Python uses
only its standard library; a `clickhouse` executable is required for the requested
local database.

Debug instrumentation is compile-time composable. `DEBUG=0` forcibly removes every
group regardless of the other flags. A normal `DEBUG=1` build enables audio/sequence
and gameplay/quest evidence, with the redundant legacy ring and on-screen HUD off:

```sh
# Focused interactive debug: action, sound-resolution, and quest events only
gmake mod TESTBOOT=1 TB_SCENE=LAUNDRY_POOL TB_GRANT_MASK=0 DEBUG=1 \
  DBG_AUDIO=0 DBG_GAMEPLAY=1 DBG_LEGACY=0 DBG_HUD=0

# Full causal audio build, without unrelated gameplay events
gmake mod TESTBOOT=1 TB_SCENE=LAUNDRY_POOL TB_GRANT_MASK=0 DEBUG=1 \
  DBG_AUDIO=1 DBG_GAMEPLAY=0 DBG_LEGACY=0 DBG_HUD=0

# Ordinary release: all debug groups are forced out of the linked ROM
gmake mod DEBUG=0
```

Custom debug combinations receive a `-debug-dbgLAGH.z64` suffix, where the four bits
are legacy, audio, gameplay, and HUD. This prevents one probe set from silently
overwriting another. The post-link invariant audit requires every enabled group's
symbols and rejects symbols from every disabled group.

Each run also gets an isolated hardware-sensitivity profile: pure R4300 interpreter,
CXD4 LLE RSP, Angrylion software RDP with high/one-thread synchronization, original
timing, Expansion Pak enabled, and all overclock/TLB-ignore/run-ahead/rewind paths off.
The launcher hashes the RetroArch/core binaries and records the complete profile; it
never edits either binary or the user's global core options. See
[`docs/N64_INVARIANTS.md`](docs/N64_INVARIANTS.md) for the sourced rationale and the
mandatory real-console residual test.

The strict core profile is intentionally slower than ordinary Mupen settings even
when the ROM contains no debug logging. Use it for hardware-sensitivity validation;
do not attribute all of its performance cost to the firehose.

## Relationship to the PC mod

This implementation was developed from the PC-side reference mod, but the public build
does not read or import from that tree:

- `tuning.yaml`, the N64 integration code, and all converters needed by the release are
  versioned here.
- Mario assets and sounds are generated directly from the user's validated SM64 ROM.
- MM assets are generated directly from the user's validated MM ROM.
- The pinned MM checkout is a **pristine substrate**: changes live here as `patches/`
  plus `src/`, are applied during the build, and are reverted afterward.

## Layout

- `Makefile` — the machinery. `make rom` = vanilla ROM (proves the substrate),
  `make mod` = patched DSCE ROM, `make toolchain` = one-time binutils bootstrap.
- `toolchain/` — locally built `mips-linux-gnu` binutils (o32/elf32btsmip —
  REQUIRED; generic mips64 binutils without the o32 emulation cannot link this).
- `patches/` — decomp-side changes as unified diffs against `.work/mm` (Stage 0:
  empty; grows per the staged plan in N64_ROM_PATH.md §7).
- `src/` — new N64-side DSCE sources (the Mario moveset overlay lands here).
- `.work/` — ignored private dependency clones, extracted assets, and intermediate
  output created by the two-ROM wrapper.
- `out/` — built ROMs.
- `tools/check_n64_invariants.py` — mandatory post-link ROM/map/ELF/`dmadata` and
  debug-boundary audit; any violation fails `make mod`.

## Build

```sh
make toolchain   # once: fetches + builds mips-linux-gnu binutils into toolchain/
make rom         # vanilla n64-us ROM, MD5-compared against the baserom
make mod         # DSCE ROM: applies patches/, NON_MATCHING=1, output in out/
```

The manual commands above are lower-level developer entry points and require the MM,
SM64, and toolchain paths to be populated or supplied explicitly. New users should
use `tools/build_from_roms.sh`.

The behavioral test programs are included as source. They are optional and are not
used by the normal two-ROM build. To run them, install Mupen64Plus plus its development
headers, then build this repository's two source-only test plugins:

```sh
tools/inputbot/build.sh
```

The resulting `.dylib`/`.so` files, test ROMs, telemetry, screenshots, and emulator
state remain ignored. No emulator executable or compiled plugin is distributed.

Host quirks the Makefile already handles (discovered 2026-07-02, Apple Silicon):
- `RUN_CC_CHECK=0` — the host gcc syntax-check pass uses `-m32`, unsupported here.
- `ICONV=toolchain/bin/gnu-iconv` — GNU libiconv is built locally by `make toolchain`;
  BSD `/usr/bin/iconv` rejects bytes in some sources (`PreRender.c`).
- `MIPS_BINUTILS_PREFIX` → `toolchain/` binutils (o32-capable `elf32btsmip`; the
  nix mips64 binutils lacks that emulation and fails the soundfont partial links).
- `COMPARE=0` on `make rom` — this toolchain (binutils 2.42 + GNU libiconv 1.18)
  produces a **byte-different** ROM (retail MD5 mismatch). The mod builds
  `NON_MATCHING` anyway, so the correctness bar is *boots and plays*, not MD5;
  `make rom-match` exists if we ever chase byte-matching (would need the exact
  binutils/iconv the decomp CI pins).
