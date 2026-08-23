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
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"project site: FAIL: {message}")


def main(require_built_patcher: bool = False) -> int:
    stable = json.loads((SITE / "stable.json").read_text(encoding="utf-8"))
    html = (SITE / "index.html").read_text(encoding="utf-8")
    patcher_script = (SITE / "patcher.js").read_text(encoding="utf-8")
    worker_script = (SITE / "patcher-worker.js").read_text(encoding="utf-8")

    require(stable["repository"] == "msmfai/marios-mask", "unexpected repository")
    require(re.fullmatch(r"\d+\.\d+\.\d+", stable["version"]) is not None, "invalid stable version")
    require(stable["tag"] == f"v{stable['version']}", "stable version and tag disagree")
    require(stable["assets"] == EXPECTED_ASSETS, "stable asset names disagree with release workflow")
    require("<h1>Mario's Mask</h1>" in html, "missing project title")
    require(html.count('class="hero-image"') == 1, "site must contain exactly one hero image")
    require("Termina, with Mario's movement" not in html, "marketing copy must not appear")
    require('class="description"' not in html, "description section must not appear")
    require("<footer" not in html, "footer must not appear")
    require("app.js" not in html, "marketing-page script must not be loaded")
    require("primary-download" not in html, "site must not link to downloadable builders")
    require("data-platform" not in html, "site must not offer platform builder downloads")
    require(html.count('type="file"') == 3, "browser patcher must request exactly three ROMs")
    require(html.count('name="mario-colour"') == 3, "all Mario colour options must remain")
    require("build-rom" in html and "download-rom" in html, "build and download controls must remain")
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
