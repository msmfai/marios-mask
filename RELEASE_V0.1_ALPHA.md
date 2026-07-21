# v0.1.0-alpha.1 release gate

This repository is an **alpha, source-only ROM builder**. It is not a ROM release.
Users provide the two supported NTSC-US ROMs locally; generated ROMs and extracted game
data must remain local and must not be uploaded or redistributed through this project.

The release is ready to tag when every automated gate in `GITHUB_RELEASE.md` passes
from the clean, independent repository. A GitHub prerelease for this
version may contain GitHub's generated source archives only—no manually attached game
ROM, binary patch containing game assets, save, capture, audio, MIDI, or emulator bundle.

Version: `0.1.0-alpha.1`  
Proposed tag: `v0.1.0-alpha.1`  
Status: authorized for public alpha release

## Candidate checklist

- [x] Clean export passes `python3 tools/release_audit.py --tree .`.
- [x] Audit still passes after repository initialization, the candidate commit, and a full-history scan.
- [x] `release-manifest.sha256` verifies and exactly covers the candidate files.
- [x] Incorrect ROM revisions are rejected; both documented revisions are accepted.
- [x] Two builds are byte-identical and pass invariant/checksum gates.
- [x] Focused mask, acquisition, ocarina, collision, and audio-sequence tests pass.
- [x] README dependencies, supported hosts, alpha limitations, and reporting route are accurate.
- [x] GPL-3.0-only and third-party provenance notices are included.
- [x] Owner explicitly authorized the public repository and copyleft release.

Validated release-ROM SHA-256 for the documented macOS build environment:
`6a3c66b66ee31f0bf271c1c17001b46c0e18bcf9e697f1d605acba91c96349db`.

See `GITHUB_RELEASE.md`, `PROVENANCE.md`, and `README.md` for the detailed public
boundary, provenance, host requirements, and known limitations. Behavioral harness
source is included; generated ROMs, compiled plugins, and run evidence remain local.
