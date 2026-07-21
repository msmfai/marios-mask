#!/usr/bin/env python3
"""insert_frag.py <file> <frag> <anchor> <guard> -- idempotently insert frag before the
first occurrence of anchor unless guard substring is already present."""
import io
import sys

path, frag, anchor, guard = sys.argv[1:5]
s = io.open(path).read()
if guard in s:
    sys.exit(0)
add = io.open(frag).read()
assert anchor in s, f"anchor {anchor!r} missing in {path}"
io.open(path, "w").write(s.replace(anchor, add + anchor, 1))
