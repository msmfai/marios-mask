#!/usr/bin/env python3
"""Check the coupled version and recipe pins for a public release."""

from __future__ import annotations

import hashlib
import plistlib
import re
import tomllib
from pathlib import Path

import release_audit


ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    cargo = tomllib.loads((ROOT / "patcher/Cargo.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "patcher/Cargo.lock").read_text(encoding="utf-8"))
    notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    report = (ROOT / "patcher/recipe/REPORT.md").read_text(encoding="utf-8")
    library = (ROOT / "patcher/src/lib.rs").read_text(encoding="utf-8")
    with (ROOT / "packaging/macos/Info.plist").open("rb") as handle:
        macos = plistlib.load(handle)
    recipe = (ROOT / release_audit.RECIPE).read_bytes()

    require(version == cargo["package"]["version"], "VERSION and Cargo.toml disagree")
    package = next(
        entry for entry in lock["package"] if entry["name"] == "marios-mask-builder"
    )
    require(version == package["version"], "VERSION and Cargo.lock disagree")
    require(not version.endswith("-dev"), "release version still has the -dev suffix")
    require(
        macos["CFBundleVersion"] == version,
        "VERSION and macOS CFBundleVersion disagree",
    )
    require(
        macos["CFBundleShortVersionString"] == version,
        "VERSION and macOS CFBundleShortVersionString disagree",
    )
    require(
        notes.startswith(f"# Mario's Mask Alpha {version}\n"),
        "release notes title does not match VERSION",
    )

    digest = hashlib.sha256(recipe).hexdigest()
    require(
        digest == release_audit.EXPECTED_RECIPE_SHA256,
        "recipe SHA-256 does not match release_audit.py",
    )
    require(recipe[:8] == b"MMRECP01", "recipe header is invalid")
    output_sha256 = recipe[80:112].hex()
    require(output_sha256 in report, "recipe output SHA-256 is missing from REPORT.md")

    output_sha1 = re.search(r'const OUTPUT_SHA1: &str = "([0-9a-f]{40})";', library)
    require(output_sha1 is not None, "patcher output SHA-1 pin is missing")
    require(output_sha1.group(1) in report, "output SHA-1 is missing from REPORT.md")

    print(
        f"release contract OK: v{version}, recipe {digest}, "
        f"output SHA-256 {output_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
