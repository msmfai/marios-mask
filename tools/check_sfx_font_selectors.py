#!/usr/bin/env python3
"""Prove generated SFX channels select their intended global soundfonts.

MM's channel font/fontinstr operand is a reverse index into the sequence's
compiled .note.fonts list, not a global soundfont id. A selector outside that
list reads unrelated bytes before the list and can corrupt the audio engine.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


FONTINSTR = 0xEB
INSTR_SFX = 0x7E
EXPECTED_PREFIXES = {
    "CHAN_PL_DSCE_": 41,
    "CHAN_VO_DSCE_": 42,
}


def output(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout


def dump_section(objdump: str, obj: Path, section: str) -> bytes:
    dumped = output(objdump, "-s", f"--section={section}", str(obj))
    chunks: dict[int, bytes] = {}
    for line in dumped.splitlines():
        match = re.match(r"^\s*([0-9A-Fa-f]+)\s+(.+)$", line)
        if not match:
            continue
        address = int(match.group(1), 16)
        hex_words = []
        for field in match.group(2).split():
            if not re.fullmatch(r"[0-9A-Fa-f]{8}", field):
                break
            hex_words.append(field)
        if hex_words:
            chunks[address] = bytes.fromhex("".join(hex_words))
    if not chunks:
        raise SystemExit(f"SFX font selector check FAILED: {obj}: empty/missing {section}")
    end = max(address + len(data) for address, data in chunks.items())
    result = bytearray(end)
    for address, data in chunks.items():
        result[address:address + len(data)] = data
    return bytes(result)


def symbols(nm: str, obj: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in output(nm, "-a", str(obj)).splitlines():
        fields = line.split()
        if len(fields) >= 3 and re.fullmatch(r"[0-9A-Fa-f]+", fields[0]):
            result[fields[-1]] = int(fields[0], 16)
    return result


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: check_sfx_font_selectors.py <nm> <objdump> <seq_0-object>")
    nm, objdump, object_arg = sys.argv[1:]
    obj = Path(object_arg)
    if not obj.is_file():
        raise SystemExit(f"SFX font selector check FAILED: missing object: {obj}")

    fonts = list(dump_section(objdump, obj, ".note.fonts"))
    data = dump_section(objdump, obj, ".data")
    found = {prefix: 0 for prefix in EXPECTED_PREFIXES}
    errors: list[str] = []

    for name, address in symbols(nm, obj).items():
        prefix = next((p for p in EXPECTED_PREFIXES if name.startswith(p)), None)
        if prefix is None:
            continue
        found[prefix] += 1
        if address + 3 > len(data):
            errors.append(f"{name}: address 0x{address:X} lies outside .data")
            continue
        opcode, selector, instrument = data[address:address + 3]
        if opcode != FONTINSTR or instrument != INSTR_SFX:
            errors.append(
                f"{name}: expected fontinstr <selector>, {INSTR_SFX}; "
                f"compiled bytes are {opcode:02X} {selector:02X} {instrument:02X}"
            )
            continue
        if selector >= len(fonts):
            errors.append(
                f"{name}: selector {selector} is outside sequence font list {fonts}; "
                "runtime would read before Fonts_0"
            )
            continue
        resolved = fonts[len(fonts) - 1 - selector]
        expected = EXPECTED_PREFIXES[prefix]
        if resolved != expected:
            errors.append(
                f"{name}: selector {selector} resolves to global font {resolved}, expected {expected}; "
                f"compiled font list is {fonts}"
            )

    for prefix, count in found.items():
        if count == 0:
            errors.append(f"no generated symbols found with prefix {prefix}")

    if errors:
        for error in errors:
            print(f"SFX FONT SELECTOR ERROR: {error}")
        raise SystemExit(
            f"SFX font selector check FAILED: {len(errors)} error(s), compiled font list {fonts}"
        )

    print(
        "SFX font selector check OK: "
        f"{sum(found.values())} channels, compiled font list {fonts}, "
        "selectors 2->41 and 1->42"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
