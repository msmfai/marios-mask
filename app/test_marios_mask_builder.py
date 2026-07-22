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
            self.assertNotIn("DSCE_PACKAGED_RUNTIME", invocation.environment)

    def test_packaged_invocation_uses_only_bundled_host_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "payload" / "project"
            runtime = root / "runtime"
            (project / "tools").mkdir(parents=True)
            (project / "tools" / "build_from_roms.sh").touch()
            (runtime / "bin").mkdir(parents=True)
            (runtime / "bin" / "micromamba").touch()
            sm64 = root / "sm64.z64"
            mm = root / "mm.z64"
            output = root / "result.z64"
            with mock.patch.object(builder, "materialize_project", return_value=project), \
                 mock.patch.object(builder, "materialize_runtime", return_value=runtime), \
                 mock.patch.object(builder, "cache_root", return_value=root / "cache"), \
                 mock.patch.object(builder.platform, "system", return_value="Darwin"):
                invocation = builder.build_invocation(root, sm64, mm, output)
            self.assertEqual(invocation.environment["DSCE_PACKAGED_RUNTIME"], "1")
            self.assertEqual(invocation.command[0], str(runtime / "bin" / "micromamba"))


if __name__ == "__main__":
    unittest.main()
