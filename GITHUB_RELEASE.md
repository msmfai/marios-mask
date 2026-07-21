# GitHub release boundary

## Outcome

Release tag `v0.1.0-alpha.2` from this **independent, clean-history source repository**.
It accepts two locally supplied, exact-revision ROMs and produces the
Brother's Mask Majora's Mask ROM without reading any sibling project. It must never
contain or ship:

- either input ROM or any generated ROM;
- extracted Nintendo models, textures, animation data, samples, or music;
- Mario voice WAV/AIFF files, MIDI files, save states, `.o2r` archives, or asset-bearing
  binary patches;
- local build directories, emulator captures, or private absolute paths.

The build uses a private ignored `.work/` directory. `tools/release_audit.py` checks
the public tree and all Git path history for the prohibited formats. CI runs the same
gate on every push and pull request.

## Native builder downloads

The release workflow builds four GUI archives: Windows x86-64, Linux x86-64,
macOS Apple Silicon, and macOS Intel. Each carries the host tools used by the builder.
The Windows archive uses a private native MSYS2 environment; it never invokes WSL.
The packages contain project source, build tools, package metadata, and licenses, but
no ROM, extracted game asset, save, or generated ROM. The same game-data audit runs
against every assembled archive before it can be attached to a release.

## Preserve the clean repository

Run `python3 tools/release_audit.py --tree .` before every push. Keep this repository's
history independent from any private development monorepo: importing older private
history could expose extracted voice, music, ROM, or other generated game data even if
later commits delete it. Verify `release-manifest.sha256` and do not publish the
generated `mm-dsce-mario.z64` as a release asset.

Project-authored work is released under GPL-3.0-only. Third-party material retains the
terms recorded in `PROVENANCE.md`.

The GUI has no user-installed build dependencies. During the first build it fetches
the two pinned public decomp source trees and caches them for later builds. It never
fetches game data. `PROVENANCE.md` records the exact source and input revision pins.
