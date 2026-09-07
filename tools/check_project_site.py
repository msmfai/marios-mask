#!/usr/bin/env python3
"""Validate the intentionally static project splash-page configuration."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
EXPECTED_ASSETS = {
    "windows": "MariosMaskBuilder-windows-x86_64.zip",
    "macAppleSilicon": "MariosMaskBuilder-macos-apple-silicon.zip",
    "macIntel": "MariosMaskBuilder-macos-intel.zip",
    "linux": "MariosMaskBuilder-linux-x86_64.tar.gz",
    "android": "MariosMaskBuilder-android.apk",
    "web": "MariosMaskBuilder-web.html",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"project site: FAIL: {message}")


def main(require_built_patcher: bool = False) -> int:
    stable = json.loads((SITE / "stable.json").read_text(encoding="utf-8"))
    html = (SITE / "index.html").read_text(encoding="utf-8")
    styles = (SITE / "styles.css").read_text(encoding="utf-8")
    patcher_script = (SITE / "patcher.js").read_text(encoding="utf-8")
    worker_script = (SITE / "patcher-worker.js").read_text(encoding="utf-8")
    controls_diagram = (SITE / "n64-controller.svg").read_text(encoding="iso-8859-1")
    speedruns_html = (SITE / "speedruns.html").read_text(encoding="utf-8")
    speedruns_script = (SITE / "speedruns.js").read_text(encoding="utf-8")
    speedruns = json.loads((SITE / "speedruns.json").read_text(encoding="utf-8"))

    require(stable["repository"] == "msmfai/marios-mask", "unexpected repository")
    require(re.fullmatch(r"\d+\.\d+\.\d+", stable["version"]) is not None, "invalid stable version")
    require(stable["tag"] == f"v{stable['version']}", "stable version and tag disagree")
    require(stable["assets"] == EXPECTED_ASSETS, "stable asset names disagree with release workflow")
    require("<h1>Mario's Mask</h1>" in html, "missing project title")
    require(html.count('class="hero-image"') == 1, "site must contain exactly one hero image")
    require('src="hero.png"' in html and (SITE / "hero.png").is_file(), "hero image must be local")
    require("Termina, with Mario's movement" not in html, "marketing copy must not appear")
    require('class="description"' not in html, "description section must not appear")
    require("<footer" not in html, "footer must not appear")
    require("app.js" not in html, "marketing-page script must not be loaded")
    require("primary-download" not in html, "site must not link to downloadable builders")
    require("data-platform" not in html, "site must not offer platform builder downloads")
    require(html.count('type="file"') == 3, "browser patcher must request exactly three ROMs")
    require(
        "Use NTSC Nintendo 64 ROMs for all three games." in html,
        "browser patcher must clearly require NTSC ROMs",
    )
    require(
        "NTSC ROM — revision 1.0, 1.1, or 1.2" in html,
        "Ocarina ROM input must list supported revisions",
    )
    require(
        "Ocarina of Time may be revision 1.0, 1.1, or 1.2." not in html,
        "supported Ocarina revisions belong on its ROM input, not in the blurb",
    )
    require(html.count('name="mario-colour"') == 3, "all Mario colour options must remain")
    for title in ("Game ROMs", "Mario's appearance", "Mario controls", "Build your ROM"):
        require(title in html, f"patcher section is missing title {title}")
    require(
        'class="canonical-note"' in html and "Canonical appearance" in html,
        "canonical-green notice must remain prominent",
    )
    require(
        html.count('data-mario-part=') == 6,
        "custom Mario palette must expose all six model material groups",
    )
    require(
        html.count('type="color"') == 6,
        "only the six Custom palette entries may be editable",
    )
    require(
        html.count('disabled></label>') == 6,
        "custom colour inputs must remain disabled until Custom is confirmed",
    )
    require(
        'class="palette-list green-palette"' in html
        and 'class="palette-list red-palette"' in html,
        "both presets must show their complete read-only palettes",
    )
    for part in ("Overalls", "Cap &amp; shirt", "Gloves", "Shoes", "Skin", "Hair &amp; moustache"):
        require(part in html, f"custom Mario palette is missing {part}")
    require("selectedPalette()" in patcher_script, "builder must submit the complete Mario palette")
    require(
        'id="palette-confirmation"' in html
        and "confirmNonCanonicalPalette" in patcher_script
        and 'paletteConfirmation.showModal()' in patcher_script
        and 'confirmPalette.addEventListener("click"' in patcher_script
        and 'paletteConfirmation.close("confirm")' in patcher_script
        and "PALETTE_ACKNOWLEDGEMENT_KEY" in patcher_script
        and "localStorage.setItem(PALETTE_ACKNOWLEDGEMENT_KEY" in patcher_script,
        "non-canonical palettes must require explicit confirmation",
    )
    require("data.palette.flat()" in worker_script, "worker must forward all six RGB colours")
    require("build-rom" in html and "download-rom" in html, "build and download controls must remain")
    require('href="speedruns.html"' in html, "patcher must link to the speedrun leaderboard")
    require(
        all(f'<th scope="col">{heading}</th>' in speedruns_html for heading in ("Username", "Time", "Version")),
        "speedrun leaderboard must show username, time and version",
    )
    require(isinstance(speedruns, list), "speedrun leaderboard data must be a list")
    require(
        all(
            isinstance(run, dict)
            and set(run) == {"username", "time", "version"}
            and all(isinstance(value, str) and value.strip() for value in run.values())
            and re.fullmatch(r"\d+:\d{2}:\d{2}(?:\.\d+)?", run["time"]) is not None
            and re.fullmatch(r"\d+\.\d+\.\d+", run["version"]) is not None
            for run in speedruns
        ),
        "every speedrun must have a username and valid time/version",
    )
    require(
        "newer versions always rank above" in speedruns_html
        and "compareVersionsDescending" in speedruns_script
        and "timeInSeconds(left.time) - timeInSeconds(right.time)" in speedruns_script,
        "leaderboard must rank newer versions first and then faster times",
    )
    require(
        'fetch("speedruns.json")' in speedruns_script and "textContent = value" in speedruns_script,
        "leaderboard must load local data without injecting markup",
    )
    require(
        html.count('src="n64-controller.svg"') == 2,
        "Mario controls diagram must be shown on the patcher",
    )
    for label in ("Player 1", "Player 2", "D-pad", "Camera orbit / zoom", "Alt camera"):
        require(label in html, f"controls diagram is missing {label}")
    require(
        '<div><dt><b>3</b>C-Up</dt><dd>Enhanced Mode</dd></div>' in html
        and '<div><dt><b>10</b>C-Left / Down / Right</dt><dd>Items</dd></div>' in html
        and '<div><dt><b>8</b>R</dt><dd>Z-target</dd></div>' in html,
        "controls diagram must show the current C-Up enhanced-mode and R target scheme",
    )
    for song in ("Song of Mushroom Melodies", "Song of Borrowed Voices"):
        require(song in html, f"soundtrack controls are missing {song}")
    for sequence in ("R + C←", "Stick↓ + A", "Z + C↓", "Stick↑ + C↑"):
        require(sequence in html, f"soundtrack controls are missing input {sequence}")
    require(
        html.count('class="soundtrack-matrix"') == 1
        and "<caption>" not in html
        and html.count("Zelda instruments") == 2
        and html.count("Mario instruments") == 2,
        "soundtrack matrix must show all four music and instrument states",
    )
    require(
        "https://www.svgrepo.com/svg/84805/n64-game-control" in controls_diagram
        and "CC0 1.0" in controls_diagram,
        "N64 controller asset must retain its CC0 provenance",
    )
    require(
        '<div><dt><b>9</b>Control stick</dt><dd>Alt camera</dd></div>' in html,
        "Player 2 alternate camera must use control marker 9",
    )
    require(
        (SITE / "controls-proof.html").is_file()
        and (SITE / "controls-proof.js").is_file()
        and (SITE / "controls-proof.css").is_file(),
        "draggable controls proof must remain available",
    )
    require("background: var(--surface)" not in styles, "patcher must not use a card background")
    require("border: 1px solid var(--line)" not in styles, "options must not use card borders")
    require("Content-Security-Policy" in html, "missing content security policy")
    require("script-src 'self'" in html, "scripts must be restricted to this site")
    require("connect-src 'self'" in html, "network connections must be restricted to this site")
    require("'unsafe-inline'" not in html, "inline script or style must not be enabled")
    require("XMLHttpRequest" not in patcher_script, "patcher must not upload with XMLHttpRequest")
    require("WebSocket" not in patcher_script, "patcher must not open WebSockets")
    require("sendBeacon" not in patcher_script, "patcher must not transmit with sendBeacon")
    require('fetch("stable.json")' in patcher_script, "patcher may only fetch local release metadata")
    require("fetch(" not in worker_script, "ROM worker must make no network requests")
    require('./pkg/marios_mask_builder.js' in worker_script, "worker must load the local WASM patcher")
    loader_exists = (SITE / "pkg" / "marios_mask_builder.js").is_file()
    wasm_exists = (SITE / "pkg" / "marios_mask_builder_bg.wasm").is_file()
    require(loader_exists == wasm_exists, "generated browser patcher is incomplete")
    if require_built_patcher:
        require(loader_exists, "generated WASM loader is missing")
        require(wasm_exists, "generated WASM binary is missing")

    mode = "built" if require_built_patcher else "source"
    print(f"project site: PASS (stable v{stable['version']}, minimal local patcher, {mode} check)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-built-patcher",
        action="store_true",
        help="require the generated JavaScript loader and WebAssembly binary",
    )
    arguments = parser.parse_args()
    raise SystemExit(main(arguments.require_built_patcher))
