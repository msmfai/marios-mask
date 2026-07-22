# Maintainer release SOP

This repository is the independent public subset of the private Mario's Mask
development repository. Gameplay development and ROM debugging happen in the private
superset. This repository publishes a small compiled builder that needs two exact
user-supplied ROMs; it never publishes a game ROM.

## Boundary

- Never import private Git history or point this repository at the private remote.
- Never add input/output ROMs, extracted models, textures, audio, saves, emulator
  captures, maps, symbol files, logs, toolchains, or build directories.
- The only game-derived binary permitted in source is the exact, hash-pinned two-ROM
  Zstandard reference recipe under `patcher/recipe/`.
- Public-builder and documentation work may happen here. Gameplay changes arrive only
  as an explicitly promoted, already-tested recipe.

## Prepare a release commit

1. Update the recipe from an approved `DEBUG=0` private release candidate.
2. Update its SHA-256 in `tools/release_audit.py`, the expected output SHA-1 in
   `patcher/src/lib.rs`, and the output SHA-256 in `RELEASE_V0.1_ALPHA.md`.
3. Update `VERSION`, `patcher/Cargo.toml`, release notes, and tag references together.
4. Prove the patcher reconstructs the approved candidate byte-for-byte from both
   accepted ROMs. Never weaken an input or output hash to make a candidate pass.
5. Run:

```sh
cargo fmt --manifest-path patcher/Cargo.toml -- --check
cargo test --manifest-path patcher/Cargo.toml --locked
python3 tools/release_audit.py --tree .
python3 tools/update_release_manifest.py
python3 tools/check_release_contract.py
```

6. Review the entire diff and commit it. The manifest is generated last and must
   exactly cover the publishable tree.

## Publish

Push the release commit and wait for the branch audit. Tag that exact tested commit
with a new `v...` prerelease tag and push the tag. Never move or reuse a published
tag. The tag workflow must finish all four packages before the release is considered
usable:

- Windows x86-64
- Linux x86-64
- macOS Apple Silicon
- macOS Intel

Finally, download the package for the current host from GitHub and build using both
supported inputs. Verify the generated ROM SHA-256 against the release gate. This is
the final test because it exercises what users actually receive.

If any gate fails, do not tag. If an already-published alpha is defective, publish a
new alpha version after fixing and repeating the procedure; do not rewrite history.
