#!/usr/bin/env python3
"""Reject game data, build toolchains, and oversized binary downloads."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


FORBIDDEN_SUFFIXES = {".z64", ".v64", ".n64", ".rom", ".wad", ".sav", ".sra"}
FORBIDDEN_PARTS = {"conda", "msys64", "payload", "python", "src", "toolchain"}
N64_MAGICS = {
    bytes.fromhex("80371240"),
    bytes.fromhex("37804012"),
    bytes.fromhex("40123780"),
}
MAX_UNPACKED_BYTES = 20 * 1024 * 1024


def audit(root: Path) -> list[str]:
    failures: list[str] = []
    total = 0
    executable_found = False
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        lowered_parts = {part.lower() for part in relative.parts}
        total += path.stat().st_size
        if path.name in {"MariosMaskBuilder", "MariosMaskBuilder.exe"}:
            executable_found = True
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden game/save extension: {relative}")
        if lowered_parts & FORBIDDEN_PARTS:
            failures.append(f"forbidden runtime or source directory: {relative}")
        try:
            with path.open("rb") as handle:
                if handle.read(4) in N64_MAGICS:
                    failures.append(f"N64 ROM header: {relative}")
        except OSError as error:
            failures.append(f"could not inspect {relative}: {error}")
    if not executable_found:
        failures.append("standalone builder executable is missing")
    if total > MAX_UNPACKED_BYTES:
        failures.append(f"unpacked download is {total} bytes; limit is {MAX_UNPACKED_BYTES}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    failures = audit(args.root)
    if failures:
        print("Binary package audit failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("Binary package audit passed: small standalone builder; no ROMs or toolchain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
