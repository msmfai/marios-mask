#!/usr/bin/env python3
"""Fail unless the canonical Laundry Pool build boots with Peach and without the mask."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "out" / "mm-dsce-test-laundry-pool-nomask.z64"
INPUTBOT = ROOT / "tools" / "inputbot" / "mupen64plus-input-script.dylib"
NULLVIDEO = ROOT / "tools" / "inputbot" / "mupen64plus-video-null.dylib"
BROTHERS_MASK_ITEM = 0x3D


def symbol(rom: Path, name: str) -> str:
    sidecar = Path(str(rom) + ".va")
    for line in sidecar.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key == name:
            return value
    raise RuntimeError(f"{name} missing from {sidecar}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="?", type=Path, default=DEFAULT_ROM)
    args = parser.parse_args()
    rom = args.rom.expanduser().resolve()
    if not rom.is_file():
        parser.error(f"missing ROM: {rom}")
    if "laundry-pool-nomask" not in rom.name.lower():
        parser.error("acquisition smoke requires a *laundry-pool-nomask*.z64 build")

    with tempfile.TemporaryDirectory(prefix="dsce-acquisition-smoke-") as tmp:
        work = Path(tmp)
        rules = work / "rules.txt"
        raw = work / "telemetry.csv"
        config = work / "mupen-config"
        rules.write_text("", encoding="utf-8")
        source_config = Path.home() / "Library" / "Application Support" / "Mupen64Plus"
        shutil.copytree(source_config, config) if source_config.is_dir() else config.mkdir()
        env = dict(os.environ, CT_INPUT_SCRIPT=str(rules),
                   CT_DSCE_ADDR=symbol(rom, "gDsceTelemetry"),
                   CT_TELEMETRY=str(raw), CT_MAX_FRAMES="1800")
        result = subprocess.run([
            "mupen64plus", "--nospeedlimit", "--audio", "dummy",
            "--configdir", str(config), "--datadir", str(config),
            "--gfx", str(NULLVIDEO), "--input", str(INPUTBOT), str(rom),
        ], env=env, capture_output=True, text=True, timeout=120, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"headless emulator failed ({result.returncode}): {result.stderr[-1000:]}")

        samples = []
        with raw.open(encoding="utf-8") as stream:
            for row in csv.reader(stream):
                if row and row[0] == "DSCE" and len(row) >= 21:
                    samples.append({"poll": int(row[1]), "mask_item": int(row[16]),
                                    "quest_state": int(row[20])})
        if not samples:
            raise RuntimeError("no DSCE telemetry: ROM did not reach the Laundry Pool test scene")
        if any(sample["mask_item"] == BROTHERS_MASK_ITEM for sample in samples):
            raise RuntimeError("Brother's Mask was pre-granted; Peach acquisition cannot be tested")
        peach = next((sample for sample in samples if sample["quest_state"] == 1), None)
        if peach is None:
            raise RuntimeError("Peach never reached quest_state=1 during cold boot")
        print(f"acquisition boot OK: Peach present by poll {peach['poll']}, mask not owned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
