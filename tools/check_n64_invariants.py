#!/usr/bin/env python3
"""Fail a Brother's Mask build whose linked N64 contracts are not self-consistent.

This is intentionally standard-library-only.  It checks facts the linker/ROM can prove;
it does not pretend to replace a real-console timing, cache-coherency, or audio test.
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path


ROM_MAGIC = 0x80371240
MAX_CART_BYTES = 64 * 1024 * 1024
MIN_STATIC_ARENA = 2 * 1024 * 1024
DEBUG_ONLY_SYMBOLS = {
    "gDsceLogHead", "gDsceLogRing", "gDsceFhHead", "gDsceFhRing",
    "gDsceSeqFlightHead", "gDsceSeqFlightRing", "gDsceSeqFlightFrozen",
    "gDsceAiSubmitTrace", "gDsceAudioMgrTrace", "gDsceAudioUpdateTrace",
    "gDsceAudioSeqTrace", "gDsceAudioSlowLoadTrace", "gDsceAudioChannelPtrTrace",
}
LEGACY_SYMBOLS = {"gDsceLogHead", "gDsceLogRing"}
FIREHOSE_SYMBOLS = {"gDsceFhHead", "gDsceFhRing"}
AUDIO_DEBUG_SYMBOLS = {
    "gDsceSeqFlightHead", "gDsceSeqFlightRing", "gDsceSeqFlightFrozen",
    "gDsceAiSubmitTrace", "gDsceAudioMgrTrace", "gDsceAudioUpdateTrace",
    "gDsceAudioSeqTrace", "gDsceAudioSlowLoadTrace", "gDsceAudioChannelPtrTrace",
}


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.checks = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)


def read_map(path: Path) -> tuple[dict[str, int], list[str]]:
    symbols: dict[str, int] = {}
    assertions: list[str] = []
    symbol_line = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s+([A-Za-z_.$][A-Za-z0-9_.$]*)\s*(?:=|$)")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = symbol_line.match(line)
        if match:
            symbols[match.group(2)] = int(match.group(1), 16)
        if "ASSERT (" in line:
            assertions.append(line.strip())
    return symbols, assertions


def need(symbols: dict[str, int], audit: Audit, name: str) -> int:
    audit.require(name in symbols, f"map is missing required symbol {name}")
    return symbols.get(name, 0)


def audit_elf(path: Path, rom_entry: int, audit: Audit) -> None:
    data = path.read_bytes()[:52]
    audit.require(len(data) == 52, "ELF header is truncated")
    if len(data) != 52:
        return
    audit.require(data[:4] == b"\x7fELF", "linked image is not ELF")
    audit.require(data[4] == 1, "linked image is not ELF32")
    audit.require(data[5] == 2, "linked image is not big-endian")
    audit.require(struct.unpack_from(">H", data, 18)[0] == 8, "linked image is not MIPS")
    entry = struct.unpack_from(">I", data, 24)[0]
    flags = struct.unpack_from(">I", data, 36)[0]
    audit.require(entry == rom_entry, f"ELF/header entrypoint mismatch: 0x{entry:08X} != 0x{rom_entry:08X}")
    audit.require((flags & 0xF0000000) == 0x20000000, f"ELF is not tagged MIPS III: flags=0x{flags:08X}")
    audit.require(bool(flags & 0x100), f"ELF lacks 32-bit-mode flag: flags=0x{flags:08X}")


def audit_dmadata(rom: bytes, start: int, end: int, rom_end: int, audit: Audit) -> int:
    audit.require(start % 16 == 0 and end % 16 == 0, "dmadata segment is not 16-byte aligned")
    audit.require(0 <= start < end <= len(rom), "dmadata segment lies outside ROM")
    if not (0 <= start < end <= len(rom)):
        return 0

    entries: list[tuple[int, int, int, int]] = []
    sentinel = None
    for offset in range(start, end, 16):
        entry = struct.unpack_from(">IIII", rom, offset)
        if entry == (0, 0, 0, 0):
            sentinel = offset
            break
        entries.append(entry)
    audit.require(sentinel is not None, "dmadata has no all-zero sentinel")
    if sentinel is None:
        return len(entries)
    audit.require(not any(rom[sentinel:end]), "dmadata bytes after its sentinel are not zero padding")

    previous_vrom_end = 0
    previous_physical_end = 0
    saw_table_owner = False
    for index, (vstart, vend, pstart, pend) in enumerate(entries):
        label = f"dmadata[{index}]"
        audit.require(vstart < vend, f"{label} has empty/reversed VROM span 0x{vstart:X}..0x{vend:X}")
        audit.require(vstart % 16 == 0 and vend % 16 == 0,
                      f"{label} VROM span is not 16-byte aligned")
        audit.require(vstart >= previous_vrom_end,
                      f"{label} overlaps or reorders the preceding VROM entry")
        audit.require(vend <= rom_end, f"{label} VROM end 0x{vend:X} exceeds linked ROM end 0x{rom_end:X}")
        previous_vrom_end = vend
        if vstart <= start and vend >= end:
            saw_table_owner = True

        is_syms = pstart == 0xFFFFFFFF and pend == 0xFFFFFFFF
        audit.require(is_syms or (pstart != 0xFFFFFFFF and pend != 0xFFFFFFFF),
                      f"{label} has a half-SYMS physical range")
        if is_syms:
            continue
        physical_end = pstart + (vend - vstart) if pend == 0 else pend
        audit.require(pstart % 2 == 0 and physical_end % 2 == 0,
                      f"{label} violates the PI ROM two-byte alignment contract")
        audit.require(pstart < physical_end <= len(rom),
                      f"{label} physical span 0x{pstart:X}..0x{physical_end:X} lies outside ROM")
        audit.require(pstart >= previous_physical_end,
                      f"{label} physical span overlaps or reorders the preceding file")
        if pend != 0:
            audit.require(pend > pstart, f"{label} compressed physical span is reversed")
        previous_physical_end = physical_end

    audit.require(bool(entries), "dmadata contains no entries")
    audit.require(saw_table_owner, "dmadata does not contain an entry covering its own table")
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--map", required=True, dest="map_path", type=Path)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--debug", required=True, choices=("0", "1"))
    parser.add_argument("--debug-legacy", default="0", choices=("0", "1"))
    parser.add_argument("--debug-firehose", default="0", choices=("0", "1"))
    parser.add_argument("--debug-audio", default="0", choices=("0", "1"))
    args = parser.parse_args()

    audit = Audit()
    rom = args.rom.read_bytes()
    symbols, assertions = read_map(args.map_path)

    audit.require(len(rom) >= 0x101000, "ROM is too small for the CIC checksum window")
    audit.require(len(rom) <= MAX_CART_BYTES, f"ROM exceeds the 64 MiB cartridge-image ceiling: {len(rom)}")
    audit.require(len(rom) % 0x1000 == 0, "ROM size is not a 4 KiB multiple")
    if len(rom) >= 0x40:
        magic, clock, entry, _release, crc1, crc2 = struct.unpack_from(">IIIIII", rom, 0)
        audit.require(magic == ROM_MAGIC, f"ROM is not big-endian .z64: magic=0x{magic:08X}")
        audit.require(clock == 0xF, f"unexpected N64 clock-rate header word: 0x{clock:08X}")
        audit.require(0x80000400 <= entry < 0x80800000, f"entrypoint is outside KSEG0 RDRAM: 0x{entry:08X}")
        audit.require(crc1 != 0 and crc2 != 0, "CIC CRC1/CRC2 were not populated")
        audit.require(rom[0x20:0x34] == b"ZELDA MAJORA'S MASK ", "unexpected internal ROM name/revision")
        audit.require(rom[0x3B:0x40] == b"NZSE\x00", "ROM is not Majora's Mask N64 US revision 0")
    else:
        entry = 0
        audit.require(False, "ROM header is truncated")

    audit_elf(args.elf, entry, audit)
    audit.require(bool(assertions), "linker map contains no ASSERT results")
    for assertion in assertions:
        value = int(assertion.split()[0], 16)
        audit.require(value == 1, f"linker assertion failed: {assertion}")

    rom_start = need(symbols, audit, "_RomStart")
    rom_end = need(symbols, audit, "_RomEnd")
    dmadata_start = need(symbols, audit, "_dmadataSegmentRomStart")
    dmadata_end = need(symbols, audit, "_dmadataSegmentRomEnd")
    code_start = need(symbols, audit, "_codeSegmentStart")
    code_end = need(symbols, audit, "_codeSegmentEnd")
    buffers_start = need(symbols, audit, "_buffersSegmentStart")
    buffers_end = need(symbols, audit, "_buffersSegmentEnd")
    framebuffer_start = need(symbols, audit, "_framebuffer_hiSegmentStart")
    framebuffer_end = need(symbols, audit, "_framebuffer_hiSegmentEnd")

    audit.require(rom_start == 0, f"linked ROM does not begin at zero: 0x{rom_start:X}")
    audit.require(0 < rom_end <= len(rom), f"linked ROM end 0x{rom_end:X} lies outside image")
    audit.require(len(rom) - rom_end < 0x20000,
                  f"unexpectedly large unlinked ROM tail: {len(rom) - rom_end} bytes")
    audit.require(0x80000400 <= code_start < code_end <= buffers_start,
                  "resident code/data and buffer segments overlap or escape KSEG0")
    audit.require(buffers_start <= buffers_end < framebuffer_start,
                  "resident buffers overlap the fixed high framebuffer")
    audit.require(framebuffer_start == 0x80780000 and framebuffer_end == 0x80800000,
                  "Expansion Pak framebuffer contract moved from 0x80780000..0x80800000")
    static_arena = framebuffer_start - buffers_end
    audit.require(static_arena >= MIN_STATIC_ARENA,
                  f"static Zelda arena headroom fell below 2 MiB: {static_arena} bytes")

    segment_pairs = 0
    for name, start_value in symbols.items():
        match = re.fullmatch(r"_(.+)SegmentRomStart", name)
        if not match:
            continue
        end_name = f"_{match.group(1)}SegmentRomEnd"
        if end_name not in symbols:
            continue
        end_value = symbols[end_name]
        segment_pairs += 1
        audit.require(start_value <= end_value <= rom_end,
                      f"segment {match.group(1)} ROM span is reversed or outside _RomEnd")
        audit.require(start_value % 16 == 0 and end_value % 16 == 0,
                      f"segment {match.group(1)} ROM span is not 16-byte aligned")
    audit.require(segment_pairs > 100, f"parsed implausibly few ROM segments: {segment_pairs}")

    for name, address in symbols.items():
        if re.match(r"^(?:mario|peach).*(?:_dl|_dl_[0-9A-Fa-f]+)$", name):
            audit.require(address % 8 == 0, f"RSP display list {name} is not 8-byte aligned")

    entry_count = audit_dmadata(rom, dmadata_start, dmadata_end, rom_end, audit)
    present_debug = DEBUG_ONLY_SYMBOLS.intersection(symbols)
    requested_groups = {
        "legacy": (args.debug_legacy == "1", LEGACY_SYMBOLS),
        "firehose": (args.debug_firehose == "1", FIREHOSE_SYMBOLS),
        "audio": (args.debug_audio == "1", AUDIO_DEBUG_SYMBOLS),
    }
    if args.debug == "0":
        audit.require(not any(enabled for enabled, _symbols in requested_groups.values()),
                      "release audit was asked to permit debug instrumentation")
        audit.require(not present_debug,
                      f"release build contains debug-only state: {', '.join(sorted(present_debug))}")
    else:
        for group, (enabled, group_symbols) in requested_groups.items():
            present = group_symbols.intersection(symbols)
            if enabled:
                missing = group_symbols.difference(symbols)
                audit.require(not missing,
                              f"enabled {group} debug group lacks symbols: {', '.join(sorted(missing))}")
            else:
                audit.require(not present,
                              f"disabled {group} debug group leaked symbols: {', '.join(sorted(present))}")

    if audit.errors:
        for error in audit.errors:
            print(f"N64 INVARIANT ERROR: {error}")
        print(f"N64 invariant audit FAILED: {len(audit.errors)} errors across {audit.checks} checks")
        return 1
    print(f"N64 invariant audit OK: {audit.checks} checks, {segment_pairs} segments, "
          f"{entry_count} DMA entries, {static_arena} bytes static arena headroom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
