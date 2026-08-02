#!/usr/bin/env python3
"""Audit the complete public history for the standalone patcher boundary."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


ALLOWED_TOP_LEVEL = {
    ".github",
    ".gitignore",
    "LICENSE",
    "PROVENANCE.md",
    "README.md",
    "RELEASE_NOTES.md",
    "VERSION",
    "packaging",
    "patcher",
    "tools",
}
FORBIDDEN_SUFFIXES = {
    ".7z", ".a", ".aif", ".aiff", ".bin", ".bps", ".dll", ".dylib", ".elf",
    ".exe", ".gz", ".iso", ".jpg", ".jpeg", ".mid", ".midi", ".mm2p", ".n64",
    ".o", ".png", ".rar", ".rom", ".sav", ".so", ".tar", ".v64", ".wav",
    ".xdelta", ".zip", ".z64",
}
FORBIDDEN_ROOTS = {
    "app", "assets", "build", "docs", "extracted", "out", "patches", "src",
    "state", "test", "toolchain",
}
RECIPE = "patcher/recipe/marios-mask.mmrecipe"
EXPECTED_RECIPE_SHA256 = "584151acab8ceecb7c604ec50523465f1f0b515576253be0eb2524b896841759"
REQUIRED = {
    ".github/workflows/binary-release.yml",
    ".github/workflows/release-audit.yml",
    ".gitignore",
    "LICENSE",
    "PROVENANCE.md",
    "README.md",
    "RELEASE_NOTES.md",
    "VERSION",
    "packaging/audit_binary_package.py",
    "packaging/macos/Info.plist",
    "patcher/Cargo.lock",
    "patcher/Cargo.toml",
    "patcher/recipe/FORMAT.md",
    "patcher/recipe/REPORT.md",
    RECIPE,
    "patcher/src/bin/recipe_tool.rs",
    "patcher/src/lib.rs",
    "patcher/src/main.rs",
    "patcher/src/recipe.rs",
    "tools/release_audit.py",
}
N64_MAGICS = {
    bytes.fromhex("80371240"),
    bytes.fromhex("37804012"),
    bytes.fromhex("40123780"),
}
RECIPE_MAGIC = b"MMRECP01"
HEADER_SIZE = 116
MAX_RECIPE_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
MAX_COMMANDS = 8_000_000


def git(tree: Path, *arguments: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(tree), *arguments],
        check=True,
        capture_output=True,
    ).stdout
    return result if binary else result.decode("utf-8")


def forbidden_path(name: str) -> str | None:
    path = Path(name)
    if not path.parts:
        return "empty path"
    if path.parts[0] not in ALLOWED_TOP_LEVEL:
        return "outside the standalone-patcher boundary"
    if path.parts[0] in FORBIDDEN_ROOTS:
        return "private development/source root"
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"forbidden binary/media extension {path.suffix}"
    if any(part in {".work", "target", "__pycache__"} for part in path.parts):
        return "generated or private-input directory"
    return None


def parse_recipe(data: bytes) -> str | None:
    if len(data) > MAX_RECIPE_BYTES:
        return f"transparent recipe exceeds {MAX_RECIPE_BYTES} bytes"
    if len(data) < HEADER_SIZE or data[:8] != RECIPE_MAGIC:
        return "unsupported transparent recipe header"
    output_size = int.from_bytes(data[8:16], "little")
    command_count = int.from_bytes(data[112:116], "little")
    if output_size > MAX_OUTPUT_BYTES:
        return "declared output exceeds size limit"
    if command_count > MAX_COMMANDS:
        return "declared command count exceeds limit"

    cursor = HEADER_SIZE
    produced = 0
    for index in range(command_count):
        if cursor >= len(data):
            return f"command {index} is truncated"
        opcode = data[cursor]
        cursor += 1
        if opcode in (0, 1, 3):
            if cursor + 8 > len(data):
                return f"command {index} is truncated"
            offset = int.from_bytes(data[cursor:cursor + 4], "little")
            length = int.from_bytes(data[cursor + 4:cursor + 8], "little")
            cursor += 8
            if length == 0:
                return f"command {index} has zero length"
            if opcode == 3 and offset >= produced:
                return f"command {index} references unwritten output"
        elif opcode == 2:
            if cursor + 4 > len(data):
                return f"command {index} is truncated"
            length = int.from_bytes(data[cursor:cursor + 4], "little")
            cursor += 4
            if length == 0 or cursor + length > len(data):
                return f"literal command {index} is empty or truncated"
            cursor += length
        else:
            return f"command {index} has unknown opcode {opcode}"
        produced += length
        if produced > output_size:
            return f"command {index} exceeds the declared output size"

    if produced != output_size:
        return f"commands produce {produced} bytes, expected {output_size}"
    if cursor != len(data):
        return "recipe has trailing bytes"
    return None


def inspect_blob(name: str, data: bytes) -> str | None:
    if name.endswith(".mmrecipe"):
        return parse_recipe(data)
    if data.startswith(bytes.fromhex("28b52ffd")):
        return "opaque Zstandard payload"
    if data[:4] in N64_MAGICS:
        return "N64 ROM header"
    if b"\0" in data:
        return "unexpected binary payload"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "non-UTF-8 payload"
    return None


def current_files(tree: Path) -> list[str]:
    return [name for name in git(tree, "ls-files", "-z").split("\0") if name]


def historical_blobs(tree: Path) -> list[tuple[str, str]]:
    lines = git(tree, "rev-list", "--objects", "--all").splitlines()
    result: list[tuple[str, str]] = []
    for line in lines:
        if " " not in line:
            continue
        object_id, name = line.split(" ", 1)
        if git(tree, "cat-file", "-t", object_id).strip() == "blob":
            result.append((object_id, name))
    return result


def audit(tree: Path) -> list[str]:
    failures: list[str] = []
    present = set(current_files(tree))
    for missing in sorted(REQUIRED - present):
        failures.append(f"{missing}: required file is missing")

    seen: set[str] = set()
    for object_id, name in historical_blobs(tree):
        reason = forbidden_path(name)
        if reason:
            failures.append(f"history contains {name}: {reason}")
            continue
        if object_id in seen:
            continue
        seen.add(object_id)
        data = git(tree, "cat-file", "blob", object_id, binary=True)
        reason = inspect_blob(name, data)
        if reason:
            failures.append(f"history blob {name}: {reason}")

    current_recipe = tree / RECIPE
    if current_recipe.is_file():
        digest = hashlib.sha256(current_recipe.read_bytes()).hexdigest()
        print(f"transparent recipe SHA-256: {digest}")
        if digest != EXPECTED_RECIPE_SHA256:
            failures.append(
                f"{RECIPE}: SHA-256 {digest} does not match the reviewed release pin"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, default=Path.cwd())
    tree = parser.parse_args().tree.resolve()
    failures = audit(tree)
    if failures:
        print("Public-history audit failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("Public-history audit passed: every reachable ref is patcher-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
