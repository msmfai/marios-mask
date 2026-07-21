#!/usr/bin/env python3
"""Generate src/dsce_tuning.h from tuning.yaml (the N64 stand-in for the PC ImGui sliders).

tuning.yaml is a flat `Key: value` file (valid YAML, parsed here with a tiny hand parser
so the build has no dependency). Floats become `1.5f` defines, ints stay ints.

Usage: gen_tuning.py <tuning.yaml> <out_header>
"""
import re
import sys


def main():
    src, out = sys.argv[1], sys.argv[2]
    entries = []
    for lineno, line in enumerate(open(src), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^(\w+)\s*:\s*(0x[0-9A-Fa-f]+|-?\d+(\.\d+)?)$", line)
        if not m:
            sys.exit(f"{src}:{lineno}: cannot parse tuning line: {line!r}")
        key, val = m.group(1), m.group(2)
        isfloat = m.group(3) is not None and not val.startswith("0x")
        entries.append((key, val + "f" if isfloat else val))

    with open(out, "w") as f:
        f.write("/* GENERATED from tuning.yaml by gen_tuning.py -- edit the YAML, not this. */\n")
        f.write("#ifndef DSCE_TUNING_H\n#define DSCE_TUNING_H\n")
        for key, val in entries:
            f.write(f"#define DSCE_{key} {val}\n")
        f.write("#endif\n")
    print(f"gen_tuning: {len(entries)} options -> {out}")


if __name__ == "__main__":
    main()
