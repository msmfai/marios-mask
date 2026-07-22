#!/usr/bin/env python3
"""Fail fast when public-release version, pins, ignores, or source syntax drift."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "release-manifest.sha256"
MANIFEST_SKIP_PARTS = {".git", ".work", "__pycache__", "out", "target", "toolchain"}
MANIFEST_SKIP_FILES = {
    "src/dsce_config.h",
    "src/dsce_tuning.h",
    "tools/inputbot/mupen64plus-input-script.dylib",
    "tools/inputbot/mupen64plus-input-script.so",
    "tools/inputbot/mupen64plus-video-null.dylib",
    "tools/inputbot/mupen64plus-video-null.so",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def assignment(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=[\"']?([^\"'\n]+)[\"']?$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"missing {name} assignment")
    return match.group(1)


def verify_manifest() -> list[str]:
    failures: list[str] = []
    declared: dict[str, str] = {}
    for number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/].*)", line)
        if not match:
            failures.append(f"release-manifest.sha256:{number}: invalid entry")
            continue
        digest, relative = match.groups()
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in declared:
            failures.append(f"release-manifest.sha256:{number}: unsafe or duplicate path {relative!r}")
            continue
        declared[relative] = digest

    actual = {
        path.relative_to(ROOT).as_posix(): path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and path != MANIFEST
        and not MANIFEST_SKIP_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.relative_to(ROOT).as_posix() not in MANIFEST_SKIP_FILES
    }
    missing = sorted(actual.keys() - declared.keys())
    extra = sorted(declared.keys() - actual.keys())
    if missing:
        failures.append(f"release manifest is missing: {', '.join(missing)}")
    if extra:
        failures.append(f"release manifest names absent files: {', '.join(extra)}")
    for relative in sorted(actual.keys() & declared.keys()):
        digest = hashlib.sha256(actual[relative].read_bytes()).hexdigest()
        if digest != declared[relative]:
            failures.append(f"release manifest hash mismatch: {relative}")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(verify_manifest())
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
        "patcher/recipe/marios-mask-alpha3.mm2p",
        "patcher/src/lib.rs",
        "patcher/src/main.rs",
        "packaging/macos/Info.plist",
        "docs/screenshots/README.md",
        "docs/MAINTAINER_RELEASE_SOP.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        "tools/update_release_manifest.py",
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
    for required in ("fresh save data", "File 1", "File 2 begins a completely new game"):
        if required not in readme:
            failures.append(f"README is missing fresh-save convenience wording {required!r}")

    declared_screenshots = (
        "docs/screenshots/hero.png",
        "docs/screenshots/clock-town.png",
        "docs/screenshots/peach-statue.png",
        "docs/screenshots/brothers-mask.png",
        "docs/screenshots/mario-swimming.png",
    )
    for image_path in declared_screenshots:
        if image_path not in readme:
            failures.append(f"README is missing public screenshot {image_path!r}")
        if not (ROOT / image_path).is_file():
            failures.append(f"README screenshot does not exist: {image_path!r}")

    release_notes = documents["RELEASE_NOTES.md"]
    for required in ("Choose your download", "Windows 10 or 11", "Apple Silicon", "Build Mario's Mask"):
        if required not in release_notes:
            failures.append(f"RELEASE_NOTES.md is missing friendly release text {required!r}")
    for required in ("fresh save data", "File 1", "File 2 begins a completely new game", "Day 1"):
        if required not in release_notes:
            failures.append(f"RELEASE_NOTES.md is missing fresh-save convenience wording {required!r}")
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
