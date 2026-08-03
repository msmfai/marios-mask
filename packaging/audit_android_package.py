#!/usr/bin/env python3
"""Audit a release APK without unpacking or executing it."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path, PurePosixPath


MAX_APK_BYTES = 30 * 1024 * 1024
ALLOWED_ABIS = {"arm64-v8a", "x86_64"}
LIBRARY = "libmarios_mask_builder.so"
FORBIDDEN_SUFFIXES = {".z64", ".v64", ".n64", ".rom", ".sav", ".sra"}
N64_MAGICS = {
    bytes.fromhex("80371240"),
    bytes.fromhex("37804012"),
    bytes.fromhex("40123780"),
}


def audit(apk: Path) -> list[str]:
    failures: list[str] = []
    if not apk.is_file():
        return [f"APK is missing: {apk}"]
    if apk.suffix.lower() != ".apk":
        failures.append("release asset does not use the .apk extension")
    if apk.stat().st_size > MAX_APK_BYTES:
        failures.append(f"APK exceeds {MAX_APK_BYTES} bytes")

    try:
        with zipfile.ZipFile(apk) as archive:
            names = set(archive.namelist())
            for required in {"AndroidManifest.xml", "classes.dex"}:
                if required not in names:
                    failures.append(f"APK is missing {required}")

            expected_libraries = {f"lib/{abi}/{LIBRARY}" for abi in ALLOWED_ABIS}
            for missing in sorted(expected_libraries - names):
                failures.append(f"APK is missing {missing}")

            observed_abis: set[str] = set()
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts:
                    failures.append(f"unsafe APK path: {info.filename}")
                    continue
                if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                    failures.append(f"forbidden ROM/save file in APK: {info.filename}")
                if len(path.parts) >= 3 and path.parts[0] == "lib":
                    observed_abis.add(path.parts[1])
                    if path.name != LIBRARY:
                        failures.append(f"unexpected native library: {info.filename}")
                if not info.is_dir():
                    with archive.open(info) as handle:
                        if handle.read(4) in N64_MAGICS:
                            failures.append(f"N64 ROM header in APK: {info.filename}")

            if observed_abis != ALLOWED_ABIS:
                failures.append(
                    f"APK ABIs are {sorted(observed_abis)}, expected {sorted(ALLOWED_ABIS)}"
                )
    except (OSError, zipfile.BadZipFile) as error:
        failures.append(f"invalid APK/ZIP: {error}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    failures = audit(args.apk)
    if failures:
        print("Android package audit failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("Android package audit passed: expected 64-bit ABIs; no ROMs or saves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
