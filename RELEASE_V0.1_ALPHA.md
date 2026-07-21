# v0.1.0-alpha.1 release gate

This repository is an **alpha, source-only ROM builder**. It is not a ROM release.
Users provide the two supported NTSC-US ROMs locally; generated ROMs and extracted game
data must remain local and must not be uploaded or redistributed through this project.

The release candidate is ready to tag only when every automated gate in
`GITHUB_RELEASE.md` passes from a clean, new-history export and the repository owner has
completed the license and qualified-legal-review gates. A GitHub prerelease for this
version may contain GitHub's generated source archives only—no manually attached game
ROM, binary patch containing game assets, save, capture, audio, MIDI, or emulator bundle.

Version: `0.1.0-alpha.1`  
Proposed tag: `v0.1.0-alpha.1`  
Status: not yet authorized for publication

## Candidate checklist

- [ ] Clean export passes `python3 tools/release_audit.py --tree .`.
- [ ] Audit still passes after `git init`, the candidate commit, and a full-history scan.
- [ ] `release-manifest.sha256` verifies and exactly covers the candidate files.
- [ ] Incorrect ROM revisions are rejected; both documented revisions are accepted.
- [ ] Two clean builds are byte-identical and pass invariant/checksum gates.
- [ ] Focused mask, acquisition, ocarina, collision, and audio-sequence tests pass.
- [ ] README dependencies, supported hosts, alpha limitations, and reporting route are accurate.
- [ ] License/third-party notices are reviewed and approved by the owner.
- [ ] Qualified counsel approves the proposed source and wording boundary.
- [ ] Owner explicitly authorizes the final push, tag, and GitHub prerelease.

See `GITHUB_RELEASE.md`, `PROVENANCE.md`, and `README.md` for the detailed public
boundary, provenance, host requirements, and known limitations. Behavioral harness
source is included; generated ROMs, compiled plugins, and run evidence remain local.
