# Provenance and content classes

This file describes what the public repository contains. `LICENSE` applies to the
project-authored material identified below; third-party material retains its own terms.

| Content | Source / pin | Public-tree treatment |
|---|---|---|
| SM64 decomp code under `src/sm64/` | `n64decomp/sm64` commit `9921382a68bb0c865e5e45eb594d9c64db59b1af`; upstream labels the repository CC0-1.0 | Included as source; no extracted assets included. The upstream dedication cannot grant rights it does not own. |
| MM build substrate | `zeldaret/mm` commit `f1a423cdcd2b159fd31662d2573af2b59edaa2cd` | Not vendored. Cloned locally by the user; input ROM extracts missing assets. Upstream currently has no detectable repository license, so this project claims no right to relicense it. |
| Cross-binutils | GNU binutils 2.42 from `https://ftp.gnu.org/gnu/binutils/` | Source archive fetched and built only in the ignored local toolchain directory. Not committed or redistributed. |
| Character conversion | GNU libiconv 1.18 from `https://ftp.gnu.org/pub/gnu/libiconv/` | Source archive fetched and built only in the ignored local toolchain directory. Not committed or redistributed. |
| MM Python/build tools | Requirements declared by pinned `zeldaret/mm` commit; IDO static-recomp release `v1.2` | Resolved/downloaded into `.work/mm` during the local upstream bootstrap. Version ranges are not a complete lockfile; resolved versions belong in release evidence and nothing is redistributed. |
| Headless-test plugins | Project-authored `tools/inputbot/*.c` | Source included so public tests do not read the private monorepo. Compiled plugins and Mupen64Plus itself are not included. |
| `patches/0001-dsce-hooks.patch` | Original mod changes expressed against the pinned MM tree, with patch context | Project-authored changes are GPL-3.0-only. Context remains attributable to the pinned upstream source. |
| `src/dsce/`, `tools/`, `tuning.yaml`, documentation | Project-authored integration and build material, except where a file header says otherwise | Included under GPL-3.0-only. |
| ROMs, generated ROMs, extracted model/texture/animation/audio, MIDI, emulator saves | Nintendo game inputs or locally derived build/test output | Never included; rejected by export and CI audit. |
| Standalone builder | Project-authored Rust code plus the crates locked by `patcher/Cargo.lock` | Compiled into one native executable. Downloads contain no Python runtime, compiler, decomp source tree, or game ROM. |
| Two-ROM reference recipe | Deterministic Zstandard reference delta against decompressed MM followed by SM64 | Included as a 1.3 MiB encoded delta. It requires both exact input ROMs and is not a directly usable ROM or extracted media file. |

The released standalone builder performs no network access and does not fetch or
carry either decomp tree. Accepted inputs are SM64 US SHA-1
`9bef1128717f958171a4afac3ed78ee2bb4e86ce`, compressed MM US SHA-1
`d6133ace5afaa0882cf214cf88daba39e266c078`, and decompressed MM US SHA-1
`7f5630dbc4d5d61d6276213210c4d5cdd83a47d6`. Byte-swapped `.v64` and
little-endian `.n64` copies are canonicalized before those hashes are checked.

When an upstream pin changes, update this file, the constants in
`tools/build_from_roms.sh`, and the patch compatibility tests in the same commit.
