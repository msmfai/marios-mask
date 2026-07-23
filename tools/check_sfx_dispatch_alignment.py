#!/usr/bin/env python3
"""Fail if generated game-side SFX ids disagree with aseq dispatch slots."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROW = re.compile(
    r"\bDEFINE_SFX\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*,"
)
FULL_ROW = re.compile(r"\bDEFINE_SFX\(([^)]*)\)")
FIXED_PITCH_FLAGS = {"SFX_FLAG_FREQ_NO_DIST"}


def without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def rows(path: Path, *, aseq: bool) -> list[tuple[str, str]]:
    defined = {"_LANGUAGE_ASEQ"} if aseq else set()
    active = True
    stack: list[tuple[bool, bool]] = []
    found: list[tuple[str, str]] = []

    for number, raw in enumerate(without_comments(path.read_text()).splitlines(), 1):
        line = raw.strip()
        directive = re.fullmatch(r"#\s*(ifndef|ifdef)\s+([A-Za-z0-9_]+)", line)
        if directive:
            kind, symbol = directive.groups()
            condition = (symbol not in defined) if kind == "ifndef" else (symbol in defined)
            stack.append((active, condition))
            active = active and condition
            continue
        if re.fullmatch(r"#\s*else", line):
            if not stack:
                raise SystemExit(f"SFX alignment FAILED: unmatched #else in {path}:{number}")
            parent, condition = stack[-1]
            condition = not condition
            stack[-1] = (parent, condition)
            active = parent and condition
            continue
        if re.fullmatch(r"#\s*endif", line):
            if not stack:
                raise SystemExit(f"SFX alignment FAILED: unmatched #endif in {path}:{number}")
            parent, _ = stack.pop()
            active = parent
            continue
        if active:
            match = ROW.search(line)
            if match:
                found.append(match.groups())

    if stack:
        raise SystemExit(f"SFX alignment FAILED: unterminated conditional in {path}")
    return found


def generated_pairs(path: Path) -> list[tuple[str, str]]:
    source = without_comments(path.read_text())
    pairs = ROW.findall(source)
    if not pairs:
        raise SystemExit(f"SFX alignment FAILED: no generated rows in {path}")
    if len(pairs) != len(set(pairs)):
        raise SystemExit(f"SFX alignment FAILED: duplicate generated row in {path}")
    full_rows = FULL_ROW.findall(source)
    if len(full_rows) != len(pairs):
        raise SystemExit(f"SFX alignment FAILED: could not parse every generated row in {path}")
    for number, row in enumerate(full_rows, 1):
        fields = [field.strip() for field in row.split(",")]
        if len(fields) != 7:
            raise SystemExit(
                f"SFX alignment FAILED: row {number} in {path} has {len(fields)} fields"
            )
        if fields[3:6] != ["0", "0", "0"]:
            raise SystemExit(
                f"SFX alignment FAILED: generated row {number} in {path} has runtime "
                f"distance/random parameters {fields[3:6]}"
            )
        flags = {flag.strip() for flag in fields[6].split("|")}
        if flags != FIXED_PITCH_FLAGS:
            raise SystemExit(
                f"SFX alignment FAILED: generated row {number} in {path} is not fixed-pitch "
                f"(got {fields[6]!r})"
            )
    return pairs


def unique_index(
    table: list[tuple[str, str]], column: int, symbol: str, description: str
) -> int:
    matches = [index for index, row in enumerate(table) if row[column] == symbol]
    if len(matches) != 1:
        raise SystemExit(
            f"SFX alignment FAILED: expected one {description} {symbol}, found {len(matches)}"
        )
    return matches[0]


def check_bank(table_path: Path, frag_path: Path) -> tuple[int, int, int]:
    c_rows = rows(table_path, aseq=False)
    aseq_rows = rows(table_path, aseq=True)
    pairs = generated_pairs(frag_path)
    indices: list[int] = []

    for channel, enum in pairs:
        c_index = unique_index(c_rows, 1, enum, "game-side enum")
        aseq_index = unique_index(aseq_rows, 0, channel, "aseq channel")
        if c_index != aseq_index:
            raise SystemExit(
                "SFX alignment FAILED: "
                f"{enum} is game-side slot {c_index}, but {channel} is aseq slot "
                f"{aseq_index} (skew {c_index - aseq_index:+d})"
            )
        indices.append(c_index)

    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise SystemExit(
            f"SFX alignment FAILED: generated rows are not contiguous in {table_path}"
        )
    return len(pairs), indices[0], indices[-1]


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: check_sfx_dispatch_alignment.py "
            "<player-table> <player-frag> <voice-table> <voice-frag>"
        )

    summaries = []
    for label, table_arg, frag_arg in (
        ("player", sys.argv[1], sys.argv[2]),
        ("voice", sys.argv[3], sys.argv[4]),
    ):
        count, first, last = check_bank(Path(table_arg), Path(frag_arg))
        summaries.append(f"{label}={count} rows at {first}..{last}")
    print("SFX dispatch alignment OK: " + "; ".join(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
