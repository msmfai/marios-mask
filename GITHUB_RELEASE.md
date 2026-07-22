# GitHub release boundary

## Outcome

Release tag `v0.1.0-alpha.4` from this **independent, clean-history source repository**.
It accepts two locally supplied, exact-revision ROMs and produces the
Brother's Mask Majora's Mask ROM without reading any sibling project. It must never
contain or ship:

- either input ROM or any generated ROM;
- extracted Nintendo models, textures, animation data, samples, or music;
- Mario voice WAV/AIFF files, MIDI files, save states, `.o2r` archives, or asset-bearing
  binary patches;
- local build directories, unreviewed diagnostic captures, or private absolute paths.

Up to eight curated, release-build screenshots may live under `docs/screenshots/`.
They must contain no debug overlays, private paths, ROMs, saves, or extracted source
assets. Each screenshot is limited to 2 MiB by the release audit.

The standalone builder contains one small two-ROM reference delta. It cannot produce
the game unless both exact input ROMs are supplied. `tools/release_audit.py` permits
only that exact hashed recipe while rejecting direct ROMs and extracted media.

## Native builder downloads

The release workflow builds four compiled GUI downloads: Windows x86-64, Linux
x86-64, macOS Apple Silicon, and macOS Intel. Each download contains only the native
builder (an app bundle on macOS), not Python, WSL, a compiler, source trees, ROMs,
extracted game assets, saves, or generated ROMs.

## Preserve the clean repository

Run `python3 tools/release_audit.py --tree .` before every push. Keep this repository's
history independent from any private development monorepo: importing older private
history could expose extracted voice, music, ROM, or other generated game data even if
later commits delete it. Verify `release-manifest.sha256` and do not publish the
generated `mm-dsce-mario.z64` as a release asset.

Project-authored work is released under GPL-3.0-only. Third-party material retains the
terms recorded in `PROVENANCE.md`.

The GUI has no user-installed build dependencies and performs no network access. It
normalizes and validates the two local ROMs, decompresses Majora's Mask when needed,
then applies the embedded two-ROM reference delta.

Maintainers must follow [the release SOP](docs/MAINTAINER_RELEASE_SOP.md). It keeps
gameplay development in the private superset, requires an exact manifest of this
public tree, and makes a downloaded native package the final release gate.
