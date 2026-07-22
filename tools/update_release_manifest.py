#!/usr/bin/env python3
"""Regenerate the exact SHA-256 manifest for the publishable public tree."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "release-manifest.sha256"
SKIP_PARTS = {".git", ".work", "__pycache__", "out", "target", "toolchain"}
SKIP_FILES = {
    "src/dsce_config.h",
    "src/dsce_tuning.h",
    "tools/inputbot/mupen64plus-input-script.dylib",
    "tools/inputbot/mupen64plus-input-script.so",
    "tools/inputbot/mupen64plus-video-null.dylib",
    "tools/inputbot/mupen64plus-video-null.so",
}


def publishable_files() -> list[Path]:
    return [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and path != MANIFEST
        and not SKIP_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.relative_to(ROOT).as_posix() not in SKIP_FILES
    ]


def main() -> int:
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}"
        for path in publishable_files()
    ]
    temporary = MANIFEST.with_suffix(".sha256.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(MANIFEST)
    print(f"release manifest updated: {len(lines)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
