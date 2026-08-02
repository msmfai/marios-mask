# Project splash page

This directory is the undeployed GitHub Pages source for Mario's Mask.

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

## Preview locally

From the repository root, run:

```sh
python3 -m http.server --directory site 8080
```

Then open `http://localhost:8080`.

## Enable hosting later

The `project-pages` workflow is deliberately inert until both of these actions
are taken:

1. In **Settings → Pages**, set the publishing source to **GitHub Actions**.
2. Create the repository Actions variable `ENABLE_GITHUB_PAGES` with value
   `true`, then manually run the `project-pages` workflow.

Do not enable the variable until the public site is meant to go live.
