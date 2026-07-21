#!/usr/bin/env python3
"""Reject game data from an assembled binary-release directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


FORBIDDEN_SUFFIXES = {".z64", ".v64", ".n64", ".rom", ".wad", ".sav", ".sra"}
FORBIDDEN_PARTS = {"extracted", "baseroms", ".work", "out"}
N64_MAGICS = {
    bytes.fromhex("80371240"),
    bytes.fromhex("37804012"),
    bytes.fromhex("40123780"),
}


def audit(root: Path) -> list[str]:
    failures = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        lowered_parts = {part.lower() for part in relative.parts}
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden game/save extension: {relative}")
        if "payload" in lowered_parts and lowered_parts & FORBIDDEN_PARTS:
            failures.append(f"forbidden generated-data directory: {relative}")
        try:
            with path.open("rb") as handle:
                if handle.read(4) in N64_MAGICS:
                    failures.append(f"N64 ROM header: {relative}")
        except OSError as error:
            failures.append(f"could not inspect {relative}: {error}")
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
    print("Binary package audit passed: no ROMs, saves, or extracted game data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
