#!/usr/bin/env python3
"""Validate the intentionally static project splash-page configuration."""

from __future__ import annotations

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


def main() -> int:
    stable = json.loads((SITE / "stable.json").read_text(encoding="utf-8"))
    config = json.loads((SITE / "site-config.json").read_text(encoding="utf-8"))
    html = (SITE / "index.html").read_text(encoding="utf-8")
    script = (SITE / "app.js").read_text(encoding="utf-8")
    patcher_script = (SITE / "patcher.js").read_text(encoding="utf-8")
    worker_script = (SITE / "patcher-worker.js").read_text(encoding="utf-8")

    require(stable["repository"] == "msmfai/marios-mask", "unexpected repository")
    require(re.fullmatch(r"\d+\.\d+\.\d+", stable["version"]) is not None, "invalid stable version")
    require(stable["tag"] == f"v{stable['version']}", "stable version and tag disagree")
    require(stable["assets"] == EXPECTED_ASSETS, "stable asset names disagree with release workflow")
    require("Make your Mario's Mask ROM" in html, "missing browser patcher heading")
    require("primary-download" not in html, "site must not link to downloadable builders")
    require("data-platform" not in html, "site must not offer platform builder downloads")
    require("configureDownloads" not in script, "site must not configure builder downloads")
    require(html.count('type="file"') == 3, "browser patcher must request exactly three ROMs")
    require("never leave this device" in html, "missing local-processing privacy notice")
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
    require((SITE / "pkg" / "marios_mask_builder.js").is_file(), "generated WASM loader is missing")
    require((SITE / "pkg" / "marios_mask_builder_bg.wasm").is_file(), "generated WASM binary is missing")
    require("youtube-nocookie.com" in script, "trailer must use privacy-enhanced YouTube")
    require(isinstance(config["trailerYouTubeId"], str), "trailer ID must be a string")

    print(f"project site: PASS (stable v{stable['version']}, local browser patcher, Pages-ready)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
