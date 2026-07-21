#!/usr/bin/env python3
"""Headless tests for the GUI's path and safety logic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import marios_mask_builder as builder


class BuilderTests(unittest.TestCase):
    def test_rejects_missing_input(self) -> None:
        with self.assertRaisesRegex(builder.BuilderError, "both ROMs"):
            builder.validate_choices("", "", "out.z64")

    def test_never_overwrites_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sm64 = root / "sm64.rom"
            mm = root / "mm.rom"
            sm64.touch()
            mm.touch()
            with self.assertRaisesRegex(builder.BuilderError, "cannot overwrite"):
                builder.validate_choices(str(sm64), str(mm), str(sm64))

    def test_source_tree_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            (root / "tools" / "build_from_roms.sh").touch()
            sm64 = root / "sm64.v64"
            mm = root / "mm.n64"
            output = root / "result.z64"
            sm64.touch()
            mm.touch()
            with mock.patch.object(builder.platform, "system", return_value="Linux"):
                invocation = builder.build_invocation(root, sm64, mm, output)
            self.assertEqual(invocation.command[-3:], [str(sm64), str(mm), str(output)])
            self.assertEqual(invocation.cwd, root)


if __name__ == "__main__":
    unittest.main()
