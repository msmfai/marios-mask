#!/usr/bin/env python3
"""XTEST arena generator (goal XTEST): ONE arena spec -> TWO compilations.

Emits:
  (a) an SM64 collision.inc.c that REPLACES castle_grounds area 1 collision (same symbol,
      staged at build by stage-xtest-sm64.sh) -- the oracle ROM's world becomes the arena;
  (b) dsce_xtest_arena.h for the mod -- the SAME triangles as C tables, served by the
      XTEST collision shim (SM64's original find_floor/wall algorithms, vendored).

Both games walk the IDENTICAL surface set, in SM64 units, around the SM64 castle-grounds
spawn (-837, 0, 1881), so cross-game runs are comparable bit-for-bit. Floors never
overlap in plan view (except shared edges), keeping surface-iteration order irrelevant.

Usage: gen_xtest_arena.py <out_collision.inc.c> <out_dsce_xtest_arena.h>
"""
import sys

SPAWN = (-837, 0, 1881)

# Surface types (surface_terrains.h)
DEFAULT = "SURFACE_DEFAULT"
BURNING = "SURFACE_BURNING"

verts = {}
vlist = []
tris = {DEFAULT: [], BURNING: []}


def v(x, y, z):
    key = (int(x), int(y), int(z))
    if key not in verts:
        verts[key] = len(vlist)
        vlist.append(key)
    return verts[key]


def tri(a, b, c, surf=DEFAULT):
    tris[surf].append((a, b, c))


def quad(a, b, c, d, surf=DEFAULT):
    """two tris for quad a-b-c-d (given in winding order)."""
    tri(a, b, c, surf)
    tri(a, c, d, surf)


def floor_rect(x1, z1, x2, z2, y, surf=DEFAULT):
    """flat floor, +y normal (CCW seen from above; SM64 winding: clockwise in x/z
    when y is up gives +y normal via the decomp's cross convention -- matches the
    vanilla files' vertex order for upward floors)."""
    a = v(x1, y, z1)
    b = v(x1, y, z2)
    c = v(x2, y, z2)
    d = v(x2, y, z1)
    quad(a, b, c, d, surf)


def ramp_x(x1, x2, z1, z2, y1, y2, surf=DEFAULT):
    """slope rising along +x from y1 (at x1) to y2 (at x2)."""
    a = v(x1, y1, z1)
    b = v(x1, y1, z2)
    c = v(x2, y2, z2)
    d = v(x2, y2, z1)
    quad(a, b, c, d, surf)


def wall_x(x, z1, z2, y1, y2, facing):
    """vertical wall in the z/y plane at x; facing +1 => normal toward +x."""
    a = v(x, y1, z1)
    b = v(x, y2, z1)
    c = v(x, y2, z2)
    d = v(x, y1, z2)
    if facing > 0:
        quad(a, b, c, d)
    else:
        quad(d, c, b, a)


def wall_z(z, x1, x2, y1, y2, facing):
    """vertical wall in the x/y plane at z; facing +1 => normal toward +z."""
    a = v(x1, y1, z)
    b = v(x1, y2, z)
    c = v(x2, y2, z)
    d = v(x2, y1, z)
    if facing > 0:
        quad(d, c, b, a)
    else:
        quad(a, b, c, d)


def box(x1, z1, x2, z2, y0, y1):
    """solid block standing on the apron: 4 outward walls + a top floor."""
    floor_rect(x1, z1, x2, z2, y1)
    wall_x(x1, z1, z2, y0, y1, -1)
    wall_x(x2, z1, z2, y0, y1, +1)
    wall_z(z1, x1, x2, y0, y1, -1)
    wall_z(z2, x1, x2, y0, y1, +1)


# ---------------- THE ARENAS ----------------
# Variant A "the corridor": every feature ON the walking line heading -z from spawn --
# straight cardinal pushes are the one heading where both games' cameras provably align.
# BZ2 sits 2700+ behind spawn: a closer rear wall squeezes SM64's Lakitu into a yaw
# epsilon. Deep features (slide/ledge/endwall) proved unreachable past the water, so the
# timing-critical knockback/ledge/slide mechanics get their own SHALLOW variants:
# Variant B "the box": one 300-high full-width block near spawn (bonk, wall-kick,
#   ledge-grab, climbs). Variant C "the slope": the 51-degree ramp near spawn
#   (butt-slide by jumping onto the incline, slide-back, stops).
# Variant D "the void edge": a finite floor with no perimeter wall. Walking off its
#   near edge must be rejected as OOB and reversing input must remain possible.
# Same spawn, same generator, same vendored algorithms -- one definition, N compilations.
VARIANT = "A"
WATER_BOXES = []   # (x1, z1, x2, z2, y)
POOL = None


def build_A():
    global POOL
    BX1, BZ1, BX2, BZ2 = -2400, -5200, 800, 4600
    LAVA = (BX1, 0, BX2, 400)
    POOL = (BX1, -1800, BX2, -1000)
    SLIDE = (-3400, -2600)
    LEDGE = (-4400, -4000)
    floor_rect(BX1, 400, BX2, BZ2, 0)
    floor_rect(BX1, POOL[3], BX2, 0, 0)
    floor_rect(BX1, SLIDE[1], BX2, POOL[1], 0)
    floor_rect(BX1, LEDGE[1], BX2, SLIDE[0], 0)
    floor_rect(BX1, BZ1, BX2, LEDGE[0], 0)
    floor_rect(LAVA[0], LAVA[1], LAVA[2], LAVA[3], 0, BURNING)
    floor_rect(POOL[0], POOL[1], POOL[2], POOL[3], -300)
    wall_z(POOL[1], POOL[0], POOL[2], -300, 0, +1)
    wall_z(POOL[3], POOL[0], POOL[2], -300, 0, -1)
    WATER_BOXES.append((POOL[0], POOL[1], POOL[2], POOL[3], -60))
    a = v(BX1, 0, SLIDE[1]); b = v(BX2, 0, SLIDE[1])
    c = v(BX2, 1000, SLIDE[0]); d = v(BX1, 1000, SLIDE[0])
    quad(b, a, d, c)
    wall_z(SLIDE[0], BX1, BX2, 0, 1000, -1)
    floor_rect(BX1, LEDGE[0], BX2, LEDGE[1], 350)
    wall_z(LEDGE[1], BX1, BX2, 0, 350, +1)
    wall_z(LEDGE[0], BX1, BX2, 0, 350, -1)
    perimeter(BX1, BZ1, BX2, BZ2)


def build_B():
    BX1, BZ1, BX2, BZ2 = -2400, -1600, 800, 4600
    BOX = (500, 900)   # z range; 300 high, full width
    floor_rect(BX1, BOX[1], BX2, BZ2, 0)   # spawn stretch (980-unit run-up)
    floor_rect(BX1, BZ1, BX2, BOX[0], 0)   # beyond the box
    floor_rect(BX1, BOX[0], BX2, BOX[1], 300)
    wall_z(BOX[1], BX1, BX2, 0, 300, +1)   # the face: bonk / wall-kick / ledge-grab
    wall_z(BOX[0], BX1, BX2, 0, 300, -1)
    perimeter(BX1, BZ1, BX2, BZ2)


def build_C():
    # "the descent": the B box with a 42-degree slope falling off its far edge. Route:
    # ledge-grab the face (proven B timings), climb, walk across the top and off the far
    # edge onto the down-slope FACING DOWNHILL -- the one orientation that butt-slides
    # (uphill approaches all fail: 42 deg is unwalkable from below and jump arcs bonk).
    BX1, BZ1, BX2, BZ2 = -2400, -1600, 800, 4600
    BOX = (500, 900)     # z range; 300 high
    SLOPE_LO = 167       # slope: y 300 at z=500 down to y 0 at z=167 (42 deg)
    floor_rect(BX1, BOX[1], BX2, BZ2, 0)      # spawn stretch (980-unit run-up)
    floor_rect(BX1, BOX[0], BX2, BOX[1], 300) # box top
    wall_z(BOX[1], BX1, BX2, 0, 300, +1)      # the grab face
    a = v(BX1, 0, SLOPE_LO); b = v(BX2, 0, SLOPE_LO)
    c = v(BX2, 300, BOX[0]); d = v(BX1, 300, BOX[0])
    quad(d, c, b, a)                          # descending slope, +y normal
    floor_rect(BX1, BZ1, BX2, SLOPE_LO, 0)    # runout flat
    perimeter(BX1, BZ1, BX2, BZ2)


def build_D():
    # Spawn faces -z. The floor ends at z=900 with deliberately no wall and no
    # lower floor, isolating floor-null containment from ordinary wall triangles.
    floor_rect(-2400, 900, 800, 4600, 0)


def perimeter(BX1, BZ1, BX2, BZ2):
    H = 2000
    wall_x(BX1, BZ1, BZ2, 0, H, +1)
    wall_x(BX2, BZ1, BZ2, 0, H, -1)
    wall_z(BZ1, BX1, BX2, 0, H, +1)
    wall_z(BZ2, BX1, BX2, 0, H, -1)

# ---------------- END ARENA ----------------


def emit_sm64(path):
    out = ["// GENERATED by gen_xtest_arena.py -- the XTEST cross-game arena.",
           "// Staged over south_collision_level (area 1, the Clock Town south slot) for sm64-xtest.",
           "const Collision south_collision_level[] = {",
           "    COL_INIT(),",
           f"    COL_VERTEX_INIT({len(vlist)}),"]
    for x, y, z in vlist:
        out.append(f"    COL_VERTEX({x}, {y}, {z}),")
    for surf, ts in tris.items():
        if not ts:
            continue
        out.append(f"    COL_TRI_INIT({surf}, {len(ts)}),")
        for a, b, c in ts:
            out.append(f"    COL_TRI({a}, {b}, {c}),")
    out.append("    COL_TRI_STOP(),")
    if WATER_BOXES:
        out.append(f"    COL_WATER_BOX_INIT({len(WATER_BOXES)}),")
        for i, (x1, z1, x2, z2, y) in enumerate(WATER_BOXES):
            out.append(f"    COL_WATER_BOX({i}, {x1}, {z1}, {x2}, {z2}, {y}),")
    out.append("    COL_END(),")
    out.append("};")
    open(path, "w").write("\n".join(out) + "\n")


def emit_mod(path):
    out = ["/* GENERATED by gen_xtest_arena.py -- the XTEST cross-game arena (mod side).",
           " * The SAME triangles the sm64-xtest ROM walks; served by the DSCE_XTEST",
           " * collision shim via SM64's original find_floor/wall algorithms. */",
           "#pragma once",
           "",
           f"#define DSCE_XTEST_NUM_VERTS {len(vlist)}",
           "static const short sDsceXtestVerts[DSCE_XTEST_NUM_VERTS][3] = {"]
    for x, y, z in vlist:
        out.append(f"    {{ {x}, {y}, {z} }},")
    out.append("};")
    all_tris = [(a, b, c, 0) for a, b, c in tris[DEFAULT]] + \
               [(a, b, c, 1) for a, b, c in tris[BURNING]]
    out.append(f"#define DSCE_XTEST_NUM_TRIS {len(all_tris)}")
    out.append("/* a, b, c, burning */")
    out.append("static const short sDsceXtestTris[DSCE_XTEST_NUM_TRIS][4] = {")
    for a, b, c, burn in all_tris:
        out.append(f"    {{ {a}, {b}, {c}, {burn} }},")
    out.append("};")
    wb = WATER_BOXES[0] if WATER_BOXES else (32000, 32000, 32000, 32000, -11000)
    out.append(f"#define DSCE_XTEST_WATER_X1 {wb[0]}")
    out.append(f"#define DSCE_XTEST_WATER_Z1 {wb[1]}")
    out.append(f"#define DSCE_XTEST_WATER_X2 {wb[2]}")
    out.append(f"#define DSCE_XTEST_WATER_Z2 {wb[3]}")
    out.append(f"#define DSCE_XTEST_WATER_Y {wb[4]}")
    out.append(f"#define DSCE_XTEST_SPAWN_X {SPAWN[0]}")
    out.append(f"#define DSCE_XTEST_SPAWN_Y {SPAWN[1]}")
    out.append(f"#define DSCE_XTEST_SPAWN_Z {SPAWN[2]}")
    out.append("#define DSCE_XTEST_SPAWN_YAW (-32768)")
    open(path, "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    VARIANT = sys.argv[3] if len(sys.argv) > 3 else "A"
    {"A": build_A, "B": build_B, "C": build_C, "D": build_D}[VARIANT]()
    emit_sm64(sys.argv[1])
    emit_mod(sys.argv[2])
    n = sum(len(t) for t in tris.values())
    print(f"xtest arena: {len(vlist)} verts, {n} tris "
          f"({len(tris[BURNING])} burning), {len(WATER_BOXES)} water box(es)")
