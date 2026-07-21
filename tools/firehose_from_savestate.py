#!/usr/bin/env python3
"""Black-box recorder: extract the DSCE firehose ring from a RetroArch savestate.

The debug ROM's gDsceFhRing lives in RDRAM, which RetroArch savestates contain.
The ring is SELF-IDENTIFYING: 1024 x 32-byte records whose first word is a
monotonically increasing seq (mod ring wraps) -- we scan the file for that
structure, no container parsing needed. Yield: the last ~1024 events before the
state was saved (~10s of per-frame audio state) as a normal spool for ingest.

Usage: firehose_from_savestate.py <retroarch.state[.auto]> [out.fh.jsonl]
       [--symbols <debug-rom.z64.va>]
Then:  tools/firehose_ingest.py <out.fh.jsonl> --rom <debug rom> --notes "RA failure"
"""
import argparse
import struct
import sys
import zlib

RECSZ = 32
RING = 1024


def load(path):
    raw = open(path, "rb").read()
    for attempt in (raw,):
        yield attempt
    try:
        yield zlib.decompress(raw)
    except Exception:
        pass
    # RetroArch rzip: the version is a binary byte (current files begin
    # ``#RZIPv\x01#``), followed by independently compressed zlib chunks.
    # Keep accepting the older printable spelling used by some frontends.
    if raw[:8] in (b"#RZIPv\x01#", b"#RZIPv1#"):
        chunk_size = struct.unpack("<I", raw[8:12])[0]
        out = bytearray()
        off = 20
        while off + 4 <= len(raw):
            n = struct.unpack("<I", raw[off:off + 4])[0]
            off += 4
            out += zlib.decompress(raw[off:off + n])
            off += n
        yield bytes(out)


def find_ring(buf):
    """scan for RING consecutive 32B records with coherent seq fields (BE)."""
    best = None
    for base in range(0, len(buf) - RING * RECSZ, 4):
        s0 = struct.unpack(">I", buf[base:base + 4])[0]
        s1 = struct.unpack(">I", buf[base + RECSZ:base + RECSZ + 4])[0]
        if s1 != s0 + 1 and s1 != s0 + 1 - RING:
            continue
        ok = 0
        for i in range(0, 16):
            a = struct.unpack(">I", buf[base + i * RECSZ:base + i * RECSZ + 4])[0]
            b = struct.unpack(">I", buf[base + (i + 1) * RECSZ:base + (i + 1) * RECSZ + 4])[0]
            if b == a + 1 or (a > 0 and b == a + 1 - RING):
                ok += 1
        if ok >= 14:
            return base
    return best


def read_symbols(path):
    symbols = {}
    with open(path, encoding="utf-8") as source:
        for line in source:
            name, sep, value = line.strip().partition("=")
            if sep:
                symbols[name] = int(value, 16)
    try:
        return symbols["gDsceFhRing"], symbols["gDsceFhHead"]
    except KeyError as exc:
        raise ValueError(f"missing {exc.args[0]} in {path}") from exc


def records_at_symbols(buf, ring_va, head_va):
    """Read Mupen64Plus RDRAM at exact debug-symbol addresses.

    RetroArch wraps the core's ``M64+SAVE`` stream in a 16-byte RASTATE
    header. Mupen's fixed state prefix is 44 bytes plus 400 bytes of device
    registers, after which its 8 MiB RDRAM image begins. RDRAM words are
    serialized little-endian on the host even though the emulated structs are
    big-endian, so each record is decoded as little-endian here.
    """
    if not (buf.startswith(b"RASTATE\x01") and buf[16:24] == b"M64+SAVE"):
        return None
    rdram = 16 + 44 + 400
    ring = rdram + (ring_va & 0x7FFFFF)
    head_addr = rdram + (head_va & 0x7FFFFF)
    if ring + RING * RECSZ > len(buf) or head_addr + 4 > len(buf):
        return None
    head = struct.unpack_from("<I", buf, head_addr)[0]
    count = min(head, RING)
    first = head - count
    recs = []
    for seq_expected in range(first, head):
        slot = seq_expected & (RING - 1)
        values = struct.unpack_from("<IIIIiiii", buf, ring + slot * RECSZ)
        if values[0] != seq_expected:
            raise ValueError(
                f"firehose slot {slot} contains seq {values[0]}, expected {seq_expected}"
            )
        recs.append(values)
    return recs, ring, head


def write_records(out, recs):
    with open(out, "w", encoding="utf-8") as dest:
        for seq, dft, tick, frame, a, b, c, d in recs:
            dest.write('{"seq":%u,"domain":%u,"tag":%u,"tick":%u,"frame":%u,'
                       '"a":%d,"b":%d,"c":%d,"d":%d}\n'
                       % (seq, (dft >> 24) & 0xFF, dft & 0xFFFF,
                          tick, frame, a, b, c, d))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state")
    parser.add_argument("out", nargs="?")
    parser.add_argument("--symbols", help="debug ROM .va sidecar (exact extraction)")
    args = parser.parse_args()
    path = args.state
    out = args.out or path + ".fh.jsonl"
    symbol_addrs = read_symbols(args.symbols) if args.symbols else None
    for buf in load(path):
        if symbol_addrs:
            exact = records_at_symbols(buf, *symbol_addrs)
            if exact is not None:
                recs, base, head = exact
                if not recs:
                    write_records(out, recs)
                    print(f"ring read from symbols at 0x{base:x}: 0 events (head {head}) -> {out}")
                    return
                write_records(out, recs)
                print(f"ring read from symbols at 0x{base:x}: {len(recs)} events "
                      f"(seq {recs[0][0]}..{recs[-1][0]}, head {head}) -> {out}")
                return
        base = find_ring(buf)
        if base is None:
            continue
        recs = []
        for i in range(RING):
            o = base + i * RECSZ
            seq, dft, tick, frame, a, b, c, d = struct.unpack(">IIIIiiii", buf[o:o + RECSZ])
            recs.append((seq, dft, tick, frame, a, b, c, d))
        recs.sort(key=lambda r: r[0])
        write_records(out, recs)
        print(f"ring found at 0x{base:x}: {len(recs)} events "
              f"(seq {recs[0][0]}..{recs[-1][0]}) -> {out}")
        return
    sys.exit("no firehose ring found (is this a DEBUG-ROM savestate?)")


if __name__ == "__main__":
    main()
