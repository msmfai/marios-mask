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
| Native builder runtime | Packages selected by `packaging/environment-*.yml` or `.github/workflows/binary-release.yml` from conda-forge and MSYS2 | Included only in platform download archives. Package metadata and licenses remain inside each runtime; no game data is present. |

The builder fetches the two upstream Git repositories and two GNU source archives
above. The pinned MM bootstrap additionally resolves its declared Python packages and
downloads IDO static-recomp v1.2. It does not fetch ROMs, keys, voice clips, or other
game media. Accepted inputs are SM64 US SHA-1
`9bef1128717f958171a4afac3ed78ee2bb4e86ce`, compressed MM US MD5
`2a0a8acb61538235bc1094d297fb6556`, and decompressed MM US MD5
`f46493eaa0628827dbd6ad3ecd8d65d6`. Byte-swapped `.v64` and little-endian `.n64`
copies are canonicalized before those hashes are checked.

When an upstream pin changes, update this file, the constants in
`tools/build_from_roms.sh`, and the patch compatibility tests in the same commit.
