#!/usr/bin/env python3
"""Unit tests for byte-order conversion without using or embedding any game ROM."""

from __future__ import annotations

import tempfile
import unittest
import gzip
import zipfile
from pathlib import Path
from unittest import mock

import normalize_rom


class NormalizeRomTests(unittest.TestCase):
    def test_chunk_byte_orders(self) -> None:
        canonical = bytes.fromhex("8037124001020304")
        v64 = bytes.fromhex("3780401202010403")
        n64 = bytes.fromhex("4012378004030201")
        self.assertEqual(normalize_rom.canonical_chunk(canonical, normalize_rom.MAGIC_Z64), canonical)
        self.assertEqual(normalize_rom.canonical_chunk(v64, normalize_rom.MAGIC_V64), canonical)
        self.assertEqual(normalize_rom.canonical_chunk(n64, normalize_rom.MAGIC_N64), canonical)

    def test_rejects_unknown_header(self) -> None:
        with self.assertRaisesRegex(normalize_rom.RomError, "not an N64 ROM"):
            normalize_rom.canonical_chunk(b"nope", b"nope")

    def test_normalize_identifies_supported_hash(self) -> None:
        payload = bytes.fromhex("80371240") + b"source-only-fixture"
        digest = __import__("hashlib").sha1(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.anything"
            output = root / "output.z64"
            source.write_bytes(payload)
            supported = {"sm64": {("sha1", digest): "fixture"}, "mm": {}}
            with mock.patch.object(normalize_rom, "SUPPORTED", supported):
                self.assertEqual(normalize_rom.normalize("sm64", source, output), "fixture")
            self.assertEqual(output.read_bytes(), payload)

    def test_failed_revision_does_not_leave_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.z64"
            output = root / "output.z64"
            source.write_bytes(bytes.fromhex("80371240") + b"wrong-revision")
            with self.assertRaisesRegex(normalize_rom.RomError, "unsupported SM64"):
                normalize_rom.normalize("sm64", source, output)
            self.assertFalse(output.exists())

    def test_verify_without_output(self) -> None:
        payload = bytes.fromhex("80371240") + b"verify-only-fixture"
        digest = __import__("hashlib").md5(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.rom"
            source.write_bytes(payload)
            supported = {"sm64": {}, "mm": {("md5", digest): "verified"}}
            with mock.patch.object(normalize_rom, "SUPPORTED", supported):
                self.assertEqual(normalize_rom.normalize("mm", source), "verified")
            self.assertEqual(["input.rom"], [path.name for path in Path(directory).iterdir()])

    def test_zip_and_gzip_inputs(self) -> None:
        payload = bytes.fromhex("80371240") + b"compressed-fixture"
        digest = __import__("hashlib").sha1(payload).hexdigest()
        supported = {"sm64": {("sha1", digest): "compressed"}, "mm": {}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zipped = root / "game.zip"
            gzipped = root / "game.z64.gz"
            with zipfile.ZipFile(zipped, "w") as archive:
                archive.writestr("inside/game.v64", payload)
            with gzip.open(gzipped, "wb") as archive:
                archive.write(payload)
            with mock.patch.object(normalize_rom, "SUPPORTED", supported):
                self.assertEqual(normalize_rom.normalize("sm64", zipped), "compressed")
                self.assertEqual(normalize_rom.normalize("sm64", gzipped), "compressed")

    def test_zip_rejects_multiple_roms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "two.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("one.z64", b"one")
                archive.writestr("two.z64", b"two")
            with self.assertRaisesRegex(normalize_rom.RomError, "exactly one"):
                normalize_rom.normalize("sm64", archive_path)


if __name__ == "__main__":
    unittest.main()
