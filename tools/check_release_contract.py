#!/usr/bin/env python3
"""Check the coupled version and recipe pins for a public release."""

from __future__ import annotations

import hashlib
import plistlib
import re
from pathlib import Path

import release_audit


ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def package_version(document: str, header: str, name: str | None = None) -> str:
    for block in re.split(r"(?=^\[\[?[^\n]+\]\]?\s*$)", document, flags=re.MULTILINE):
        lines = block.splitlines()
        if not lines or lines[0].strip() != header:
            continue
        if name is not None and not re.search(
            rf'^name\s*=\s*"{re.escape(name)}"\s*$', block, flags=re.MULTILINE
        ):
            continue
        match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', block, flags=re.MULTILINE)
        require(match is not None, f"{header} version is missing")
        return match.group(1)
    raise AssertionError(f"{header} package {name or ''} is missing".rstrip())


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    cargo_version = package_version(
        (ROOT / "patcher/Cargo.toml").read_text(encoding="utf-8"), "[package]"
    )
    lock_version = package_version(
        (ROOT / "patcher/Cargo.lock").read_text(encoding="utf-8"),
        "[[package]]",
        "marios-mask-builder",
    )
    notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    report = (ROOT / "patcher/recipe/REPORT.md").read_text(encoding="utf-8")
    library = (ROOT / "patcher/src/lib.rs").read_text(encoding="utf-8")
    with (ROOT / "packaging/macos/Info.plist").open("rb") as handle:
        macos = plistlib.load(handle)
    recipe = (ROOT / release_audit.RECIPE).read_bytes()

    require(version == cargo_version, "VERSION and Cargo.toml disagree")
    require(version == lock_version, "VERSION and Cargo.lock disagree")
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
