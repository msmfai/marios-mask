#!/usr/bin/env python3
"""Fail the build if any sequence's advertised span omits object bytes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def output(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout


def check_object(nm: str, objdump: str, obj: Path) -> tuple[str, int]:
    symbol_values: dict[str, int] = {}
    for line in output(nm, "-a", str(obj)).splitlines():
        fields = line.split()
        if len(fields) >= 3:
            symbol_values[fields[-1]] = int(fields[0], 16)

    suffixes = ("_Start", "_End", "_Size")
    names = {
        symbol[: -len(suffix)]
        for symbol in symbol_values
        for suffix in suffixes
        if symbol.endswith(suffix)
    }
    complete = [
        name for name in names
        if all(f"{name}{suffix}" in symbol_values for suffix in suffixes)
    ]
    if len(complete) != 1:
        raise SystemExit(
            f"sequence span check FAILED: {obj}: expected exactly one Start/End/Size symbol set; "
            f"found {sorted(complete)}"
        )
    name = complete[0]

    section_size = None
    for line in output(objdump, "-h", str(obj)).splitlines():
        match = re.match(r"\s*\d+\s+\.data\s+([0-9A-Fa-f]+)\b", line)
        if match:
            section_size = int(match.group(1), 16)
            break

    if section_size is None:
        raise SystemExit(f"sequence span check FAILED: {obj}: missing .data section")

    start = symbol_values[f"{name}_Start"]
    end = symbol_values[f"{name}_End"]
    advertised = symbol_values[f"{name}_Size"]
    if start != 0 or end - start != advertised or advertised != section_size:
        raise SystemExit(
            f"sequence span check FAILED: {obj}: "
            f"start=0x{start:X} end=0x{end:X} advertised=0x{advertised:X} "
            f"object=.data/0x{section_size:X}; all sequence data must be inside .startseq/.endseq"
        )
    return name, advertised


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("usage: check_sequence_span.py <nm> <objdump> <sequence-object> [...]")

    nm, objdump, *object_args = sys.argv[1:]
    checked = []
    for object_arg in object_args:
        obj = Path(object_arg)
        if not obj.is_file():
            raise SystemExit(f"sequence span check FAILED: missing object: {obj}")
        checked.append(check_object(nm, objdump, obj))

    focus = [f"{name}=0x{size:X}" for name, size in checked if name in {"Sequence_0", "Sequence_1"}]
    print(f"sequence span check OK: {len(checked)} object(s)" +
          (f"; {', '.join(focus)}" if focus else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
