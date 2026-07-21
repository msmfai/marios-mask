# GitHub release boundary

## Outcome

Release tag `v0.1.0-alpha.1` from this **independent, clean-history source repository**.
It accepts two locally supplied, exact-revision ROMs and produces the
Brother's Mask Majora's Mask ROM without reading any sibling project. It must never
contain or ship:

- either input ROM or any generated ROM;
- extracted Nintendo models, textures, animation data, samples, or music;
- Mario voice WAV/AIFF files, MIDI files, save states, `.o2r` archives, or asset-bearing
  binary patches;
- build directories, toolchains, emulator captures, or private absolute paths.

The build uses a private ignored `.work/` directory. `tools/release_audit.py` checks
the public tree and all Git path history for the prohibited formats. CI runs the same
gate on every push and pull request.

## Preserve the clean repository

Run `python3 tools/release_audit.py --tree .` before every push. Keep this repository's
history independent from any private development monorepo: importing older private
history could expose extracted voice, music, ROM, or other generated game data even if
later commits delete it. Verify `release-manifest.sha256` and do not publish the
generated `mm-dsce-mario.z64` as a release asset.

Project-authored work is released under GPL-3.0-only. Third-party material retains the
terms recorded in `PROVENANCE.md`.

"Self-contained" here means no dependency on the surrounding private monorepo. A ROM
recompilation cannot honestly be dependency-free: the wrapper requires common host
tools (`bash`, Git, Python 3, a C/C++ toolchain, GNU make, `curl`, `rsync`, `ffmpeg`,
and the libraries named by the upstream builds) and fetches pinned public SM64/MM
decomp sources plus GNU build tools. It never fetches game data. Vendoring every
third-party dependency would increase both licensing risk and repository size, so the
release pins and verifies them instead.

## Why this is lower-risk, not a legal guarantee

The upstream decomp projects themselves require users to provide prior game copies;
this project follows that asset-extraction pattern. The SM64 project marks its source
repository CC0, while the MM repository does not currently present a repository
license. `PROVENANCE.md` records both exact source pins and separates extracted game
data from contributor-authored code.

That engineering boundary does not answer every legal question. Copyright exceptions,
anti-circumvention rules, backup-copy rules, and the legal effect of owning a cartridge
vary by jurisdiction and facts. A generated mod ROM is still based on Nintendo games,
and this project's patches may be analyzed as derivative material. GitHub also forbids
content that infringes third-party rights and operates a DMCA takedown process.

Accordingly:

- users must determine that dumping and modifying their copies is lawful where they
  live; cartridge ownership alone is not represented as sufficient;
- no Nintendo content or output ROM may be redistributed through this project;
- Nintendo, Mario, The Legend of Zelda, and Majora's Mask are identifiers of third-
  party products; this is an unofficial, non-commercial fan project with no Nintendo
  affiliation or endorsement;
- this document is an engineering distribution policy, not legal advice.

Primary references checked 2026-07-19:

- [SM64 decomp repository and supported ROM hashes](https://github.com/n64decomp/sm64)
- [Majora's Mask decomp repository and supported ROM hash](https://github.com/zeldaret/mm)
- [GitHub Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)
- [GitHub Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)
- [GitHub DMCA Takedown Policy](https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy)
- [US Copyright Office fair-use FAQ](https://www.copyright.gov/help/faq/faq-fairuse.html)
- [US Copyright Office: derivative works](https://www.copyright.gov/eco/help-limitation.html)
