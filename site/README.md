# Project splash page

This directory is the GitHub Pages source for Mario's Mask. It includes a
browser-local WebAssembly build of the same three-ROM patcher shipped in the
desktop downloads. ROM data is read and processed only in the visitor's
browser.

## Stable release

`stable.json` is the only source of truth for the version presented as stable.
Update its version, tag, and asset names only after the corresponding GitHub
release has all four audited builder packages. This explicit pin prevents an
experimental prerelease from silently replacing the public download.

## Build and preview locally

From the repository root, run:

```sh
cargo build --manifest-path patcher/Cargo.toml --target wasm32-unknown-unknown --release --no-default-features --features web
wasm-bindgen patcher/target/wasm32-unknown-unknown/release/marios_mask_builder.wasm --target web --out-dir site/pkg --no-typescript
python3 -m http.server --directory site 8080
```

Then open `http://localhost:8080`.

The `project-pages` workflow rebuilds and validates the browser patcher when
relevant files change. Its manual deployment jobs publish either an exact
release patcher or the currently checked-in source.

## Speedrun leaderboard

The Pages deployment also publishes `speedruns.html`. Add accepted runs to
`speedruns.json` in leaderboard order. Each entry has exactly three strings:

```json
{
  "username": "RunnerName",
  "time": "1:23:45",
  "version": "0.12.1"
}
```

## README screenshot refresh

The hero, Brother's Mask inventory, underwater swimming, and bomb screenshots
reflect the current build.

The remaining legacy screenshots to replace are:

- the mysterious stone door wobbling;
- the area beyond the door in Peach's Castle;
- Mario reacting to Dinolfos fire breath.

The outdated Clock Town traversal image has been removed from the public README;
that section still needs a fresh current-build screenshot.
