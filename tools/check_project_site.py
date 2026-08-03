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

    require(stable["repository"] == "msmfai/marios-mask", "unexpected repository")
    require(re.fullmatch(r"\d+\.\d+\.\d+", stable["version"]) is not None, "invalid stable version")
    require(stable["tag"] == f"v{stable['version']}", "stable version and tag disagree")
    require(stable["assets"] == EXPECTED_ASSETS, "stable asset names disagree with release workflow")
    require("Download the latest stable version" in html, "missing primary download heading")
    require("youtube-nocookie.com" in script, "trailer must use privacy-enhanced YouTube")
    require(isinstance(config["trailerYouTubeId"], str), "trailer ID must be a string")

    print(f"project site: PASS (stable v{stable['version']}, trailer-ready, deployment gated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
