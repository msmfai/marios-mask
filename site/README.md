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

## Trailer

Set `trailerYouTubeId` in `site-config.json` to the video's YouTube ID. Until
then, the page shows the configured poster with a “Trailer coming soon” label.
The player uses YouTube's privacy-enhanced `youtube-nocookie.com` embed and is
only created when the visitor asks to play it.

## Build and preview locally

From the repository root, run:

```sh
cargo build --manifest-path patcher/Cargo.toml --target wasm32-unknown-unknown --release --no-default-features --features web
wasm-bindgen patcher/target/wasm32-unknown-unknown/release/marios_mask_builder.wasm --target web --out-dir site/pkg --no-typescript
python3 -m http.server --directory site 8080
```

Then open `http://localhost:8080`.

The `project-pages` workflow rebuilds the browser patcher, validates the static
site, and deploys it whenever relevant files change on `main`.
