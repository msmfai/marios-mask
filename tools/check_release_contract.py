#!/usr/bin/env python3
"""Fail fast when public-release version, pins, ignores, or source syntax drift."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def assignment(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=[\"']?([^\"'\n]+)[\"']?$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"missing {name} assignment")
    return match.group(1)


def main() -> int:
    failures: list[str] = []
    version = read("VERSION").strip()
    if not re.fullmatch(r"0\.\d+\.\d+-alpha\.\d+", version):
        failures.append(f"VERSION is not the expected alpha SemVer form: {version!r}")
    tag = f"v{version}"

    documents = {
        "README.md": read("README.md"),
        "RELEASE_NOTES.md": read("RELEASE_NOTES.md"),
        "RELEASE_V0.1_ALPHA.md": read("RELEASE_V0.1_ALPHA.md"),
        "GITHUB_RELEASE.md": read("GITHUB_RELEASE.md"),
        "PROVENANCE.md": read("PROVENANCE.md"),
    }
    license_text = read("LICENSE")
    for marker in ("GNU GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007"):
        if marker not in license_text:
            failures.append(f"LICENSE is not the expected GPL-3.0 text: missing {marker!r}")
    for name in ("PROVENANCE.md",):
        if "GPL-3.0-only" not in documents[name]:
            failures.append(f"{name} does not declare GPL-3.0-only")
    for name in ("RELEASE_V0.1_ALPHA.md",):
        if version not in documents[name]:
            failures.append(f"{name} does not identify version {version}")
    for name in ("RELEASE_V0.1_ALPHA.md", "GITHUB_RELEASE.md"):
        if tag not in documents[name]:
            failures.append(f"{name} does not identify tag {tag}")

    ignored = {line.strip() for line in read(".gitignore").splitlines() if line.strip() and not line.startswith("#")}
    for pattern in ("out/", ".work/", "__pycache__/", "*.pyc", "*.n64", "*.rom", "*.v64", "*.z64", "toolchain/", "src/dsce_config.h", "src/dsce_tuning.h"):
        if pattern not in ignored:
            failures.append(f".gitignore is missing release boundary pattern {pattern}")

    workflow = read(".github/workflows/release-audit.yml")
    for required in ("fetch-depth: 0", "tools/release_audit.py", "tools/check_release_contract.py"):
        if required not in workflow:
            failures.append(f"release workflow is missing {required!r}")

    binary_workflow = read(".github/workflows/binary-release.yml")
    for required in (
        "windows-2025",
        "macos-15-intel",
        "macos-15",
        "ubuntu-22.04",
        "cargo build --release --manifest-path patcher/Cargo.toml --locked",
        "20971520",
        "packaging/audit_binary_package.py",
    ):
        if required not in binary_workflow:
            failures.append(f"binary workflow is missing {required!r}")

    for relative in (
        "patcher/Cargo.lock",
        "patcher/Cargo.toml",
        "patcher/recipe/marios-mask-alpha2.mm2p",
        "patcher/src/lib.rs",
        "patcher/src/main.rs",
        "packaging/macos/Info.plist",
        "docs/screenshots/README.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
    ):
        if not (ROOT / relative).is_file():
            failures.append(f"standalone GUI release dependency is missing: {relative}")

    cargo_manifest = read("patcher/Cargo.toml")
    if f'version = "{version}"' not in cargo_manifest:
        failures.append("patcher/Cargo.toml version does not match VERSION")

    readme = documents["README.md"]
    for required in ("Releases", ".z64", ".v64", ".n64", ".zip", ".gz"):
        if required not in readme:
            failures.append(f"short README is missing user-facing promise {required!r}")

    declared_screenshots = (
        ("[Screenshot: Mario standing in Clock Town", "docs/screenshots/hero-clock-town"),
        ("[Screenshot: The Brother's Mask", "docs/screenshots/brothers-mask"),
        ("[Screenshot: Mario performing", "docs/screenshots/mario-movement"),
        ("[Screenshot: The Mario's Mask Builder", "docs/screenshots/builder"),
    )
    for placeholder, image_path in declared_screenshots:
        if placeholder not in readme and image_path not in readme:
            failures.append(f"README is missing screenshot placeholder or image {image_path!r}")

    release_notes = documents["RELEASE_NOTES.md"]
    for required in ("Which download do I choose?", "Windows 10 or 11", "Apple Silicon", "How to use it"):
        if required not in release_notes:
            failures.append(f"RELEASE_NOTES.md is missing friendly release text {required!r}")
    if "--notes-file RELEASE_NOTES.md" not in binary_workflow:
        failures.append("binary workflow does not publish the friendly release notes")

    outside_needles = (
        '/Users/',
        '/private/',
        'gitlab/',
        'HERE/../mm',
        'HERE/../sm64',
        'HERE/../tools/inputbot',
        'ROOT.parent / "tools" / "inputbot"',
        'os.path.join(HERE, "..", "tools", "inputbot"',
    )
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in {".git", ".work", "out", "target", "toolchain", "__pycache__"} for part in path.relative_to(ROOT).parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for needle in outside_needles:
            if needle in content:
                failures.append(f"outside-repository reference {needle!r}: {path.relative_to(ROOT)}")

    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", ".work", "out", "toolchain", "__pycache__"} for part in path.relative_to(ROOT).parts):
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (SyntaxError, UnicodeError) as error:
            failures.append(f"Python syntax/encoding: {path.relative_to(ROOT)}: {error}")

    for path in sorted(ROOT.rglob("*.sh")):
        if any(part in {".git", ".work", "out", "toolchain"} for part in path.relative_to(ROOT).parts):
            continue
        checked = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True)
        if checked.returncode:
            detail = checked.stderr.strip() or f"exit {checked.returncode}"
            failures.append(f"shell syntax: {path.relative_to(ROOT)}: {detail}")

    if failures:
        print("release contract FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"release contract OK: {tag}; pins, ignores, workflow, and source syntax agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
