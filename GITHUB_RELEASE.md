# GitHub release boundary

## Outcome

Prepare tag `v0.1.0-alpha.1` from `github/brothers-mask/` as a **new-history source
repository**, not this monorepo or its Git history. That directory is self-contained relative to the
monorepo: it accepts two locally supplied, exact-revision ROMs and produces the
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

## Make the clean repository

To refresh the segregated release area from this monorepo:

```sh
python3 n64/tools/export_github.py /tmp/brothers-mask-source
cd /tmp/brothers-mask-source
git init
git add .
python3 tools/release_audit.py --tree .
git commit -m "Initial source-only release"
```

The exporter refuses to overwrite a non-empty destination. Refresh in a new directory,
review its manifest, then replace `github/brothers-mask/` deliberately.
Use a new empty GitHub repository. Do **not** add a GitHub remote to the monorepo, push
the `native` branch, or preserve its history: older commits contain extracted voice
and music files even if the current checkout later deletes them. Do not publish the
generated `mm-dsce-mario.z64` as a release asset.

Before publishing, inspect `release-manifest.sha256`, choose a license for code you
personally own, and obtain a qualified lawyer's review of the patch/source boundary.
The exporter intentionally does not invent a license or assign a copyright holder on
the owner's behalf.

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

For an actual public launch, have counsel apply the relevant country-specific law and
review Nintendo's current enforcement posture, the full patch, project branding, and
the proposed code license.
