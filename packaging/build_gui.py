#!/usr/bin/env python3
"""Build the native GUI executable for the current host with PyInstaller."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path

import PyInstaller.__main__


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    options = [
        str(project / "app" / "marios_mask_builder.py"),
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name=MariosMaskBuilder",
        f"--distpath={args.dist}",
        f"--workpath={args.work}",
        f"--specpath={args.work}",
    ]
    if platform.system() != "Darwin":
        options.append("--onefile")
    PyInstaller.__main__.run(options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
