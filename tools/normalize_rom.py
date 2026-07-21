#!/usr/bin/env python3
"""Normalize supported N64 ROM byte orders and identify the exact game revision."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import tempfile
import zipfile
from contextlib import contextmanager
from collections.abc import Iterator
from typing import BinaryIO
from pathlib import Path


MAGIC_Z64 = bytes.fromhex("80371240")
MAGIC_V64 = bytes.fromhex("37804012")
MAGIC_N64 = bytes.fromhex("40123780")
MAX_ROM_SIZE = 128 * 1024 * 1024
ROM_SUFFIXES = {".z64", ".v64", ".n64", ".rom"}

SUPPORTED = {
    "sm64": {
        ("sha1", "9bef1128717f958171a4afac3ed78ee2bb4e86ce"): "sm64-us",
    },
    "mm": {
        ("md5", "2a0a8acb61538235bc1094d297fb6556"): "mm-us-compressed",
        ("md5", "f46493eaa0628827dbd6ad3ecd8d65d6"): "mm-us-decompressed",
    },
}


class RomError(ValueError):
    pass


@contextmanager
def open_rom(source: Path) -> Iterator[BinaryIO]:
    """Open a raw, ZIP, or gzip-compressed ROM without extracting archive paths."""
    try:
        with source.open("rb") as probe:
            signature = probe.read(4)
        if signature.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(source) as archive:
                files = [entry for entry in archive.infolist() if not entry.is_dir()]
                roms = [entry for entry in files if Path(entry.filename).suffix.lower() in ROM_SUFFIXES]
                candidates = roms or files
                if len(candidates) != 1:
                    raise RomError("ZIP must contain exactly one ROM file")
                member = candidates[0]
                if member.file_size > MAX_ROM_SIZE:
                    raise RomError("ROM inside ZIP is unexpectedly large")
                with archive.open(member) as handle:
                    yield handle
        elif signature[:2] == b"\x1f\x8b":
            with gzip.open(source, "rb") as handle:
                yield handle
        else:
            if source.stat().st_size > MAX_ROM_SIZE:
                raise RomError("ROM is unexpectedly large")
            with source.open("rb") as handle:
                yield handle
    except RomError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise RomError(f"could not read ROM or archive: {error}") from error


def canonical_chunk(data: bytes, magic: bytes) -> bytes:
    if magic == MAGIC_Z64:
        return data
    if magic == MAGIC_V64:
        if len(data) % 2:
            raise RomError("V64 ROM size is not divisible by 2")
        swapped = bytearray(data)
        swapped[0::2], swapped[1::2] = data[1::2], data[0::2]
        return bytes(swapped)
    if magic == MAGIC_N64:
        if len(data) % 4:
            raise RomError("N64 ROM size is not divisible by 4")
        swapped = bytearray(len(data))
        swapped[0::4] = data[3::4]
        swapped[1::4] = data[2::4]
        swapped[2::4] = data[1::4]
        swapped[3::4] = data[0::4]
        return bytes(swapped)
    raise RomError(
        "not an N64 ROM (expected Z64, V64, or N64 byte-order header)"
    )


def normalize(game: str, source: Path, destination: Path | None = None) -> str:
    if not source.is_file():
        raise RomError(f"ROM not found: {source}")

    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
    digest_sha1 = hashlib.sha1()
    digest_md5 = hashlib.md5()
    temporary: Path | None = None
    outgoing = None
    try:
        if destination is not None:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", dir=destination.parent
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            outgoing = temporary.open("wb")
        total = 0
        with open_rom(source) as incoming:
            magic = incoming.read(4)
            if magic not in {MAGIC_Z64, MAGIC_V64, MAGIC_N64}:
                raise RomError("not an N64 ROM (unknown four-byte header)")
            buffered = magic
            while True:
                chunk = incoming.read(4 * 1024 * 1024)
                buffered += chunk
                usable = len(buffered) if not chunk else len(buffered) - (len(buffered) % 4)
                if usable:
                    canonical = canonical_chunk(buffered[:usable], magic)
                    buffered = buffered[usable:]
                else:
                    canonical = b""
                if outgoing is not None:
                    outgoing.write(canonical)
                digest_sha1.update(canonical)
                digest_md5.update(canonical)
                total += len(canonical)
                if total > MAX_ROM_SIZE:
                    raise RomError("decompressed ROM is unexpectedly large")
                if not chunk:
                    break
        if outgoing is not None:
            outgoing.close()
            outgoing = None

        candidates = {
            ("sha1", digest_sha1.hexdigest()),
            ("md5", digest_md5.hexdigest()),
        }
        kind = next(
            (SUPPORTED[game][candidate] for candidate in candidates if candidate in SUPPORTED[game]),
            None,
        )
        if kind is None:
            expected = ", ".join(digest for _algorithm, digest in SUPPORTED[game])
            raise RomError(
                f"unsupported {game.upper()} revision after byte-order normalization; "
                f"got SHA-1 {digest_sha1.hexdigest()} / MD5 {digest_md5.hexdigest()}; "
                f"expected one of: {expected}"
            )
        if temporary is not None and destination is not None:
            os.replace(temporary, destination)
            temporary = None
        return kind
    finally:
        if outgoing is not None:
            outgoing.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=sorted(SUPPORTED), required=True)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        kind = normalize(args.game, args.source, args.destination)
    except RomError as error:
        parser.error(str(error))
    print(kind)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
