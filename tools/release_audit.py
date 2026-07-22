#!/usr/bin/env python3
"""Fail if a proposed public tree contains ROMs or extracted game media."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


FORBIDDEN_SUFFIXES = {
    ".7z",
    ".a",
    ".aif",
    ".aiff",
    ".bin",
    ".bps",
    ".dll",
    ".dylib",
    ".elf",
    ".exe",
    ".gz",
    ".iso",
    ".jpg",
    ".jpeg",
    ".mid",
    ".midi",
    ".n64",
    ".o",
    ".o2r",
    ".png",
    ".rar",
    ".rom",
    ".so",
    ".tar",
    ".v64",
    ".wav",
    ".xdelta",
    ".zip",
    ".z64",
}
FORBIDDEN_PARTS = {
    ".work", "__pycache__", "assets", "build", "extracted", "out", "state", "target", "test", "toolchain"
}
FORBIDDEN_FILES = {"src/dsce_config.h", "src/dsce_tuning.h"}
RECIPE = "patcher/recipe/marios-mask-alpha2.mm2p"
RECIPE_SHA256 = "c8d9a5c97084417e1367e418cfcbc8290edfff79c1c07d14872bf431902e5cad"
SCREENSHOT_PREFIX = ("docs", "screenshots")
SCREENSHOT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024
MAGIC = {
    b"RIFF": "RIFF/WAV media",
    b"MThd": "MIDI media",
    b"PK\x03\x04": "ZIP archive",
    b"\x1f\x8b\x08": "gzip archive",
    b"7z\xbc\xaf\x27\x1c": "7-Zip archive",
    b"Rar!": "RAR archive",
    b"\x7fELF": "ELF executable/object",
    b"\xcf\xfa\xed\xfe": "Mach-O executable/object",
    b"\xfe\xed\xfa\xcf": "Mach-O executable/object",
    b"MZ": "PE/DOS executable",
    bytes.fromhex("80371240"): "big-endian N64 ROM",
    bytes.fromhex("37804012"): "byte-swapped N64 ROM",
    bytes.fromhex("40123780"): "little-endian N64 ROM",
}
REQUIRED = {
    ".gitignore",
    "GITHUB_RELEASE.md",
    "LICENSE",
    "PROVENANCE.md",
    "README.md",
    "RELEASE_NOTES.md",
    "RELEASE_V0.1_ALPHA.md",
    "VERSION",
    "docs/MAINTAINER_RELEASE_SOP.md",
    "patcher/Cargo.lock",
    "patcher/Cargo.toml",
    RECIPE,
    "patcher/src/lib.rs",
    "patcher/src/main.rs",
    "docs/screenshots/README.md",
    "tools/build_from_roms.sh",
    "tools/update_release_manifest.py",
}


def is_curated_screenshot(path: str) -> bool:
    rel = Path(path)
    return rel.parts[:2] == SCREENSHOT_PREFIX and rel.suffix.lower() in SCREENSHOT_SUFFIXES


def forbidden_path(path: str) -> str | None:
    rel = Path(path)
    if is_curated_screenshot(path):
        return None
    if rel.as_posix() in FORBIDDEN_FILES:
        return "generated build header"
    if rel.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"forbidden game/media extension {rel.suffix}"
    if FORBIDDEN_PARTS.intersection(rel.parts):
        return "generated, extracted, or private-input directory"
    return None


def ignored_local_path(path: str) -> bool:
    """Known ignored build products that may exist locally but must never be tracked."""
    rel = Path(path)
    if rel.as_posix() in FORBIDDEN_FILES:
        return True
    return rel.parent.as_posix() == "tools/inputbot" and rel.suffix.lower() in {".dylib", ".so"}


def historical_objects(tree: Path) -> list[tuple[str, str]]:
    if not (tree / ".git").exists():
        return []
    proc = subprocess.run(
        ["git", "-C", str(tree), "rev-list", "--objects", "--all"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [tuple(line.split(" ", 1)) for line in proc.stdout.splitlines() if " " in line]


def indexed_paths(tree: Path) -> list[str]:
    """Return the independent release repository's staged/tracked paths, if initialized."""
    if not (tree / ".git").exists():
        return []
    proc = subprocess.run(
        ["git", "-C", str(tree), "ls-files", "--cached", "-z"],
        check=True,
        capture_output=True,
    )
    return [part.decode("utf-8") for part in proc.stdout.split(b"\0") if part]


def inspect_payload(label: str, data: bytes) -> str | None:
    if is_curated_screenshot(label):
        if len(data) > MAX_SCREENSHOT_BYTES:
            return f"curated screenshot exceeds {MAX_SCREENSHOT_BYTES} bytes"
        valid_magic = (
            data.startswith(b"\x89PNG\r\n\x1a\n")
            or data.startswith(b"\xff\xd8\xff")
            or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        )
        if not valid_magic:
            return "curated screenshot does not match PNG, JPEG, or WebP format"
        return None
    if label == RECIPE:
        digest = hashlib.sha256(data).hexdigest()
        if not data.startswith(bytes.fromhex("28b52ffd")):
            return "two-ROM recipe is not a Zstandard reference patch"
        if len(data) > 4 * 1024 * 1024:
            return "two-ROM recipe exceeds the 4 MiB release limit"
        if digest != RECIPE_SHA256:
            return f"unexpected two-ROM recipe SHA-256 {digest}"
        return None
    for signature, description in MAGIC.items():
        if data.startswith(signature):
            return f"detected {description}"
    if b"\0" in data:
        return "binary NUL byte in source-only release"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "non-UTF-8 binary payload in source-only release"
    return None


def audit(tree: Path) -> list[str]:
    failures: list[str] = []
    present: set[str] = set()
    screenshots = 0
    for path in sorted(tree.rglob("*")):
        rel_path = path.relative_to(tree)
        if ".git" in rel_path.parts or FORBIDDEN_PARTS.intersection(rel_path.parts):
            continue
        if path.is_symlink():
            failures.append(f"{rel_path}: symbolic links are not allowed in the public source tree")
            continue
        if not path.is_file():
            continue
        rel = rel_path.as_posix()
        # Local builds intentionally live in ignored private directories. They are
        # not publication candidates; the index/history checks below still reject
        # them if anyone ever stages or commits one.
        if ignored_local_path(rel):
            continue
        present.add(rel)
        if is_curated_screenshot(rel):
            screenshots += 1
        reason = forbidden_path(rel)
        if reason:
            failures.append(f"{rel}: {reason}")
            continue
        reason = inspect_payload(rel, path.read_bytes())
        if reason:
            failures.append(f"{rel}: {reason}")

    for rel in sorted(REQUIRED - present):
        failures.append(f"{rel}: required release file is missing")

    if screenshots > 8:
        failures.append(f"docs/screenshots contains {screenshots} images; limit is 8")

    for rel in indexed_paths(tree):
        reason = forbidden_path(rel)
        if reason:
            failures.append(f"git index contains {rel}: {reason}")
            continue
        data = subprocess.run(
            ["git", "-C", str(tree), "show", f":{rel}"],
            check=True,
            capture_output=True,
        ).stdout
        reason = inspect_payload(rel, data)
        if reason:
            failures.append(f"git index blob {rel}: {reason}")

    seen_blobs: set[str] = set()
    for object_id, rel in historical_objects(tree):
        reason = forbidden_path(rel)
        if reason:
            failures.append(f"git history contains {rel}: {reason}; start from the clean export")
            continue
        if object_id in seen_blobs:
            continue
        kind = subprocess.run(
            ["git", "-C", str(tree), "cat-file", "-t", object_id],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if kind != "blob":
            continue
        seen_blobs.add(object_id)
        data = subprocess.run(
            ["git", "-C", str(tree), "cat-file", "blob", object_id],
            check=True, capture_output=True,
        ).stdout
        reason = inspect_payload(rel, data)
        if reason:
            failures.append(f"git history blob {rel}: {reason}; start from the clean export")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, default=Path.cwd())
    args = parser.parse_args()
    tree = args.tree.resolve()
    if not tree.is_dir():
        parser.error(f"not a directory: {tree}")
    failures = audit(tree)
    if failures:
        print("release audit FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    count = sum(
        1
        for path in tree.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(tree).parts
        and not FORBIDDEN_PARTS.intersection(path.relative_to(tree).parts)
        and not ignored_local_path(path.relative_to(tree).as_posix())
    )
    print(f"release audit OK: {count} source/documentation files; no forbidden game blobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
