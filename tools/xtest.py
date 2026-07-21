#!/usr/bin/env python3
"""XTEST: totalistic cross-game moveset parity over the matched corridor arena.

Both ROMs (out/sm64-xtest.z64 oracle, out/mm-dsce-test-xtest.z64 mod) boot Mario to the
IDENTICAL spawn on IDENTICAL geometry. Scenarios are authored in BURST-RELATIVE TICKS with
cardinal-only movement (stick straight ahead/behind: the one heading where both games'
cameras provably align -> intendedYaw is exact on both sides). A calibration run per side
maps ticks -> input polls (the mod's poll rate is ~7:1 and offset by boot; SM64 is 1:1),
then each scenario is compiled to per-side rule files, run, and the tick streams compared:

  R1 action-id stream equality (aligned at the first non-idle action after burst start)
  R2 ABSOLUTE position equality per tick (same spawn + same floors => bit-equal, no /4.29)
  RF floorH stream equality (the continuous arena-identity gate)

Divergences print the first divergent tick with both rows. Known findings XFAIL.
Coverage: the union of observed actions must include every CORE mechanic id (minus the
declared PENDING list); the full observed set is reported for the matrix.
"""
import csv
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_ROM = os.path.join(HERE, "out", "mm-dsce-test-xtest.z64")
SM64_ROM = os.path.join(HERE, "out", "sm64-xtest.z64")
INPUTBOT = os.path.join(HERE, "tools", "inputbot", "mupen64plus-input-script.dylib")
NULLVIDEO = os.path.join(HERE, "tools", "inputbot", "mupen64plus-video-null.dylib")

IDLE_FAMILY = {0x0C400201, 0x0C400202, 0x0C000203, 0x0C000204, 0x0C400205, 0x0C400206,
               0x00000000, 0x0C000207}  # idle/sleep/head-turn fidgets: never anchor on these

ACT_NAMES = {}  # filled from sm64.h


def load_act_names():
    p = os.path.join(HERE, "src", "sm64", "include", "sm64.h")
    for line in open(p):
        if line.startswith("#define ACT_") and "0x" in line:
            parts = line.split()
            try:
                ACT_NAMES[int(parts[2], 16)] = parts[1][4:]
            except (ValueError, IndexError):
                pass


def act(a):
    return ACT_NAMES.get(a, f"{a:08x}")


def va(rom, sym):
    for line in open(rom + ".va"):
        k, _, val = line.strip().partition("=")
        if k == sym:
            return val
    sys.exit(f"xtest: {sym} not in {rom}.va")


class Side:
    def __init__(self, name, rom, tick_addr, mario_addr, t0, max_frames, phase=0):
        self.name, self.rom = name, rom
        self.tick_addr, self.mario_addr = tick_addr, mario_addr
        self.t0 = t0            # burst tick 0 == absolute tick t0
        self.max_frames = max_frames
        self.phase = phase      # input-phase shift: the mod's tick counter increments
                                # POST-tick, so the poll labeled T-1 is what tick T reads
        self.tick2poll = None

    def run(self, rules, want_sounds=False):
        d = tempfile.mkdtemp(prefix=f"xtest-{self.name}-")
        rp = os.path.join(d, "rules")
        open(rp, "w").write(rules or "9999999 9999999 NONE 0 0\n")
        csvp = os.path.join(d, "tel.csv")
        env = dict(os.environ, CT_INPUT_SCRIPT=rp, CT_TICK_ADDR=self.tick_addr,
                   CT_MARIO_ADDR=self.mario_addr, CT_TELEMETRY=csvp,
                   CT_MAX_FRAMES=str(self.max_frames))
        if want_sounds:
            env["CT_LOG_ADDR"] = self.snd_head
            env["CT_LOGRING_ADDR"] = self.snd_ring
            env["CT_LOG_DIR"] = d
        self.last_dir = d
        subprocess.run(["mupen64plus", "--nospeedlimit", "--audio", "dummy",
                        "--gfx", NULLVIDEO, "--input", INPUTBOT, self.rom],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=900, check=False)
        rows = []
        for r in csv.reader(open(csvp)):
            if r and r[0] != "frame" and len(r) >= 8:
                rows.append({"tick": int(r[0]), "poll": int(r[1]), "x": float(r[2]),
                             "y": float(r[3]), "z": float(r[4]), "yaw": int(r[5]),
                             "action": int(r[6], 16), "floorh": float(r[7])})
        return rows

    def calibrate(self):
        rows = self.run(None)
        if not rows:
            sys.exit(f"xtest: calibration produced no rows for {self.name}")
        self.tick2poll = {r["tick"]: r["poll"] for r in rows}
        # pass 2: ONE walk-and-release probe measures BOTH edge latencies (MM buffers pad
        # input differently on press vs release; both games measured, not assumed).
        # probe INSIDE the proven input window: t0 onward (earlier ticks sit in the mod's
        # entrance-cutscene neutral window, where the takeover deliberately ignores the pad)
        t_on, t_off = self.t0 + 15, self.t0 + 45
        probe = f"{self.tick2poll[t_on]} {self.tick2poll[t_off]} NONE 0 80\n"
        rows2 = self.run(probe)
        walk = next((r["tick"] for r in rows2 if r["action"] == 0x04000440), None)
        brake = next((r["tick"] for r in rows2
                      if r["action"] in (0x04800457, 0x0400044A, 0x04000445)), None)
        if walk is None or brake is None:
            sys.exit(f"xtest: {self.name} edge probe inconclusive (walk {walk}, brake {brake})")
        self.press_lat = walk - t_on
        self.release_lat = brake - t_off
        print(f"  {self.name}: press latency {self.press_lat}, release latency {self.release_lat}")
        return rows

    def compile_rules(self, inputs):
        """inputs: [(rel_tick, dur_ticks, buttons, sx, sy)] -> poll-indexed rule file."""
        lines = []
        last = max(self.tick2poll)
        for rel, dur, btns, sx, sy in inputs:
            t1 = self.t0 + rel - self.press_lat
            t2 = self.t0 + rel + dur - self.release_lat
            p1 = self.tick2poll.get(t1)
            p2 = self.tick2poll.get(t2)
            if p1 is None or p2 is None:
                sys.exit(f"xtest: {self.name} calibration too short for tick {t2} (max {last})")
            lines.append(f"{p1} {p2} {btns} {sx} {sy}")
        return "\n".join(lines) + "\n"


def anchor(rows, from_tick):
    for i, r in enumerate(rows):
        if r["tick"] >= from_tick and r["action"] not in IDLE_FAMILY:
            return i
    return None


FAIL = 0
OBSERVED = set()


def check(name, ok, detail=""):
    global FAIL
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
    if not ok:
        FAIL += 1


def compare(name, s_rows, m_rows, s_side, m_side, xfail=None, horizon=None):
    print(f"\n{name}:")
    si = anchor(s_rows, s_side.t0 - 2)
    mi = anchor(m_rows, m_side.t0 - 2)
    if xfail and (si is None or mi is None):
        print(f"  [XFAIL] {xfail}")
        return
    if si is None or mi is None:
        check(f"{name}: both sides acted", False, f"(anchors sm64={si} mod={mi})")
        return
    best = (None, -1)
    for slip in (0, 1, -1, 2, -2):
        a_i, b_i = si, mi + slip
        if b_i < 0:
            continue
        run_len = 0
        while (a_i + run_len < len(s_rows) and b_i + run_len < len(m_rows)):
            a, b = s_rows[a_i + run_len], m_rows[b_i + run_len]
            if a["action"] != b["action"] or a["x"] != b["x"] or a["z"] != b["z"]:
                break
            run_len += 1
        if run_len > best[1]:
            best = (slip, run_len)
    mi += best[0] or 0
    s_seq = s_rows[si:]
    m_seq = m_rows[mi:]
    n = min(len(s_seq), len(m_seq))
    if horizon:
        n = min(n, horizon)  # stop before the F1 sleep-onset tail devours long idles
    OBSERVED.update(r["action"] for r in s_seq[:n])
    OBSERVED.update(r["action"] for r in m_seq[:n])
    div = None
    note = ""
    i = 0
    while i < n:
        a, b = s_seq[i], m_seq[i]
        if (a["action"] != b["action"] or a["x"] != b["x"] or a["y"] != b["y"]
                or a["z"] != b["z"] or a["floorh"] != b["floorh"]):
            # F5: shared-edge quarter-step tie-breaks wobble a coordinate by ~1e-6 for a
            # few ticks, then the streams RETURN TO BIT-EQUALITY (an integrating physics
            # divergence never re-equalizes). Actions must stay equal and every wobble
            # must stay tiny; anything else is a real failure.
            j = i
            transient = True
            while j < n and j < i + 6:
                a2, b2 = s_seq[j], m_seq[j]
                if a2["action"] != b2["action"] or any(
                        abs(a2[k] - b2[k]) > 1e-4 for k in ("x", "y", "z", "floorh")):
                    transient = False
                    break
                if (a2["x"] == b2["x"] and a2["y"] == b2["y"] and a2["z"] == b2["z"]
                        and a2["floorh"] == b2["floorh"]):
                    break
                j += 1
            if transient and j < n and j > i:
                note = f" [NOTE F5: {j - i}-tick 1e-6 transient at +{i}, reconverged bit-exact]"
                i = j
                continue
            div = i
            break
        i += 1
    if xfail:
        tag = "XFAIL-STILL-DIVERGENT" if div is not None else "XPASS (finding healed?)"
        print(f"  [{tag}] {xfail}"
              + (f" first divergence at +{div}" if div is not None else ""))
        return
    detail = f"({n} aligned ticks){note}"
    if div is not None:
        lo = max(0, div - 2)
        tbl = ["    +i  | sm64 action (z, y)             | mod action (z, y)"]
        for i in range(lo, min(div + 4, n)):
            a, b = s_seq[i], m_seq[i]
            mark = " <-- diverges" if i == div else ""
            tbl.append(f"    +{i:<3d}| {act(a['action']):<18s} x{a['x']:.9g} z{a['z']:.9g} y{a['y']:.9g} fh{a['floorh']:.9g} | "
                       f"{act(b['action']):<18s} x{b['x']:.9g} z{b['z']:.9g} y{b['y']:.9g} fh{b['floorh']:.9g}{mark}")
        detail = f"\n    first divergence at +{div} ticks:\n" + "\n".join(tbl)
    check(f"{name}: R1+R2+RF exact over the window", div is None, detail)


# ---- the scenario library (burst-relative ticks; stick (0,80)=ahead, (0,-80)=behind) ----
# Each entry: (name, variant, inputs, xfail). Variants: A corridor, B box, C descent,
# D finite floor ending in a wall-less void.
FWD = (0, 80)
BACK = (0, -80)
SCENARIOS = [
    ("S1 walk-jump-land", "A", [
        (0, 20, "NONE", *FWD), (22, 3, "A", *FWD), (25, 30, "NONE", *FWD),
        (55, 40, "NONE", 0, 0)], None),
    ("S2 jump-chain (double/triple)", "A", [
        (0, 90, "NONE", *FWD),
        (10, 3, "A", *FWD), (26, 3, "A", *FWD), (45, 3, "A", *FWD),
        (90, 40, "NONE", 0, 0)], None),
    ("S3 long-jump", "A", [
        (0, 40, "NONE", *FWD), (30, 6, "Z", *FWD), (32, 4, "A,Z", *FWD),
        (40, 40, "NONE", *FWD), (80, 30, "NONE", 0, 0)], None),
    ("S4 backflip", "A", [
        (0, 14, "Z", 0, 0), (8, 4, "A,Z", 0, 0), (20, 50, "NONE", 0, 0)], None),
    ("S5 ground-pound", "A", [
        (0, 3, "A", 0, 0), (10, 4, "Z", 0, 0), (20, 40, "NONE", 0, 0)], None),
    ("S6 punch-combo + crouch-crawl", "A", [
        (0, 3, "B", 0, 0), (9, 3, "B", 0, 0), (18, 3, "B", 0, 0),
        (60, 40, "Z", 0, 0), (70, 25, "Z", *FWD), (105, 20, "NONE", 0, 0)], None),
    ("S7 dive-rollout", "A", [
        (0, 42, "NONE", *FWD), (42, 3, "B", *FWD), (54, 3, "A", 0, 0),
        (70, 40, "NONE", 0, 0)], None),
    ("S8 lava boost", "A", [
        (0, 70, "NONE", *FWD), (70, 60, "NONE", 0, 0)], None),
    ("S9 water plunge-swim-exit", "A", [
        (0, 140, "NONE", *FWD), (52, 3, "A", *FWD),
        (115, 4, "A", *FWD), (125, 4, "A", *FWD), (135, 4, "A", *FWD),
        (140, 60, "NONE", *FWD), (200, 40, "NONE", 0, 0)], None),
    ("S10 deep-corridor gauntlet (lava-boost + plunge)", "A", [
        (0, 260, "NONE", *FWD), (52, 3, "A", *FWD),
        (99, 6, "Z", *FWD), (100, 4, "A,Z", *FWD),
        (260, 80, "NONE", 0, 0)], None),
    ("S12 walk-decelerate", "A", [
        (0, 8, "NONE", *FWD), (8, 40, "NONE", 0, 0)], None),
    # the tail (oracle-tuned timings; see docs/XGAME_METAMORPHIC.md)
    # facing-reversing air moves (side-flip, wall-kick): release the stick once the move
    # triggers -- the mod's follow camera chases the flipped facing instantly while
    # Lakitu doesn't, so held stick becomes air-control through DIFFERENT camera yaws.
    # Ballistic arcs need no input; with a neutral stick both games fly bit-exact.
    ("S13 side-flip", "A", [
        (0, 26, "NONE", *FWD), (26, 2, "NONE", *BACK), (28, 3, "A", 0, 0),
        (31, 50, "NONE", 0, 0)], None),
    ("S14 soft-bonk (jump at the face)", "B", [
        (0, 60, "NONE", *FWD), (28, 3, "A", *FWD), (60, 40, "NONE", 0, 0)], None),
    ("S15 wall-kick", "B", [
        (0, 41, "NONE", *FWD), (28, 3, "A", *FWD), (42, 3, "A", 0, 0),
        (45, 50, "NONE", 0, 0)], None),
    ("S16 ledge-grab + slow climb", "B", [
        (0, 60, "NONE", *FWD), (32, 3, "A", *FWD), (60, 60, "NONE", 0, 0)], None),
    ("S17 ledge-grab + fast climb", "B", [
        (0, 42, "NONE", *FWD), (32, 3, "A", *FWD), (46, 3, "A", 0, 0),
        (55, 40, "NONE", 0, 0)], None),
    ("S18 hard bonk (long-jump at the face)", "B", [
        (0, 60, "NONE", *FWD), (32, 6, "Z", *FWD), (33, 4, "A,Z", *FWD),
        (60, 50, "NONE", 0, 0)], None),
    ("S19 dive-bonk", "B", [
        (0, 60, "NONE", *FWD), (34, 3, "B", *FWD), (60, 50, "NONE", 0, 0)], None),
    ("S20 the descent (grab, climb, butt-slide)", "C", [
        (0, 42, "NONE", *FWD), (32, 3, "A", *FWD), (46, 3, "A", 0, 0),
        (50, 110, "NONE", *FWD), (160, 60, "NONE", 0, 0)], None),
    ("S21 void edge rejects + reverse escapes", "D", [
        (0, 75, "NONE", *FWD), (75, 45, "NONE", *BACK),
        (120, 25, "NONE", 0, 0)], None),
]

# coverage gate: every CORE mechanic must appear in some stream. PENDING = authored later
# (timing-critical approaches); they print loudly but don't fail the gate yet.
CORE = ["IDLE", "WALKING", "DECELERATING", "JUMP", "DOUBLE_JUMP", "TRIPLE_JUMP",
        "LONG_JUMP", "BACKFLIP", "GROUND_POUND", "GROUND_POUND_LAND", "DIVE",
        "FORWARD_ROLLOUT", "PUNCHING", "START_CROUCHING", "CROUCHING", "CRAWLING",
        "FREEFALL", "JUMP_LAND", "DOUBLE_JUMP_LAND", "TRIPLE_JUMP_LAND",
        "LONG_JUMP_LAND", "BACKFLIP_LAND", "LAVA_BOOST", "WATER_PLUNGE",
        "BREASTSTROKE", "CROUCH_SLIDE",
        "SIDE_FLIP", "SIDE_FLIP_LAND", "TURNING_AROUND", "AIR_HIT_WALL", "SOFT_BONK",
        "BACKWARD_AIR_KB", "BACKWARD_GROUND_KB", "WALL_KICK_AIR", "LEDGE_GRAB",
        "LEDGE_CLIMB_FAST", "LEDGE_CLIMB_SLOW_1", "LEDGE_CLIMB_SLOW_2", "BUTT_SLIDE"]
PENDING = []


def make_pair(suffix, shipped=False):
    sm64_rom = os.path.join(HERE, "out", f"sm64-xtest{suffix}.z64")
    mod_rom = os.path.join(HERE, "out", f"mm-dsce-test-xtest{suffix}{'-shipped' if shipped else ''}.z64")
    for r in (sm64_rom, mod_rom):
        if not os.path.exists(r):
            sys.exit(f"xtest: missing {r} (build all variants first: "
                     f"make sm64-xtest{{,-b,-c}} + make mod TESTBOOT=1 XTEST=1 XTEST_VARIANT={{A,B,C}})")
    sm64 = Side("sm64", sm64_rom, va(sm64_rom, "gGlobalTimer"),
                va(sm64_rom, "gMarioStates"), t0=150, max_frames=2200)
    mod_tick = f"{int(va(mod_rom, 'gDsceTelemetry'), 16) + 4:x}"
    mod = Side("mod", mod_rom, mod_tick, va(mod_rom, "gDsceMarioState"),
               t0=75, max_frames=14000, phase=0)
    return sm64, mod


def check_idle_decay(s_rows, m_rows):
    """F1 (FIXED by F4): idle->sleep pacing must now match EXACTLY. Compare phase
    durations relative to each side's first idle tick — no wall-clock, no absolutes."""
    print("\nS11 idle-decay (from variant-A calibration streams):")

    def phases(rows, who):
        idle0 = next((r["tick"] for r in rows if r["action"] == 0x0C400201), None)
        onset = next((r["tick"] for r in rows if r["action"] == 0x0C400202), None)
        sleep = next((r["tick"] for r in rows if r["action"] == 0x0C000203), None)
        if None in (idle0, onset, sleep):
            sys.exit(f"xtest: {who} idle-decay phases missing ({idle0},{onset},{sleep})")
        return onset - idle0, sleep - onset

    s_p, m_p = phases(s_rows, "sm64"), phases(m_rows, "mod")
    check("S11: idle->START_SLEEPING duration exact", s_p[0] == m_p[0],
          f"(sm64 {s_p[0]} vs mod {m_p[0]} ticks)")
    check("S11: START_SLEEPING->SLEEPING duration exact", s_p[1] == m_p[1],
          f"(sm64 {s_p[1]} vs mod {m_p[1]} ticks)")


def f32(x):
    """round to binary32 -- replicate the mod's f32 arithmetic exactly."""
    import struct
    return struct.unpack("f", struct.pack("f", x))[0]


def compare_shipped(name, s_rows, m_rows, horizon):
    """Shipped tier (F2 = KEPT, user decision 2026-07-08): the mod runs MarioSpeedMul 1.5.
    DECLARED TRANSFORM (dsce_mario_sandbox.c): per tick, pos_h = prev_h + 1.5f*step_h in
    f32; vertical native. So while both sides take the SAME raw physics step (flat ground,
    equal forwardVel -- the step is velocity-based, not position-based):
      R2s: mod horizontal delta == f32(prev_m + f32(1.5 * sm64_delta)) - prev_m, BIT-EXACT
      R2y: y stream identical bit-exact
      R1s: action stream identical until the mod's earlier geometry arrival (it covers
           1.5x ground/tick, so it reaches features sooner) -- that tick is REPORTED, and
           everything after it is excluded from the exact gate (transform-declared).
    """
    print(f"\n{name}:")
    si = anchor(s_rows, 148)
    mi = anchor(m_rows, 73)
    if si is None or mi is None:
        check(f"{name}: both sides acted", False, f"(anchors sm64={si} mod={mi})")
        return None
    # action-only slip (positions differ by design here)
    best = (0, 0, -1)
    for da, db in ((0, 0), (0, 1), (1, 0), (0, 2), (2, 0)):
        run_len = 0
        while (si + da + run_len < len(s_rows) and mi + db + run_len < len(m_rows)
               and run_len < horizon):
            if s_rows[si + da + run_len]["action"] != m_rows[mi + db + run_len]["action"]:
                break
            run_len += 1
        if run_len > best[2]:
            best = (da, db, run_len)
    si += best[0]
    mi += best[1]
    s_seq = s_rows[si:]
    m_seq = m_rows[mi:]
    n = min(len(s_seq), len(m_seq), horizon)
    OBSERVED.update(r["action"] for r in s_seq[:n])
    OBSERVED.update(r["action"] for r in m_seq[:n])

    act_div = next((i for i in range(n)
                    if s_seq[i]["action"] != m_seq[i]["action"]), None)
    # Geometry arrival = FIRST tick the transform stops predicting the mod (wall clamp,
    # ledge snap...) -- it precedes the action divergence for wall scenarios (the mod is
    # clamped against the face ticks before AIR_HIT_WALL fires). The exact gate runs to
    # whichever comes first; the arrival itself is F2 evidence, not failure.
    geo_div = None
    for i in range(1, n if act_div is None else act_div):
        a0, a1 = s_seq[i - 1], s_seq[i]
        b0, b1 = m_seq[i - 1], m_seq[i]
        for k in ("x", "z"):
            want = f32(b0[k] + f32(1.5 * (a1[k] - a0[k]))) - b0[k]
            tol = 4 * 2 ** -23 * max(1.0, abs(b0[k]), abs(a0[k]))
            if abs(want - (b1[k] - b0[k])) > tol:
                geo_div = i
                break
        if geo_div is not None:
            break
    window = min(x for x in (act_div, geo_div, n) if x is not None)
    # NOTE precision: the mod's position update rounds in f32 AT ITS OWN coordinates,
    # which differ from sm64's by design (1.5x covered ground) -- so the transformed
    # delta can't be replicated bit-exact from positions alone. The gate is exact up
    # to a few ULPs of the position (measured errors are ~1 ulp), PLUS the cumulative
    # displacement ratio must be 1.5 to 1e-6 (rounding is unbiased, so it cancels).
    y_bad = h_bad = None
    sum_s = sum_m = 0.0
    for i in range(1, window):
        a0, a1 = s_seq[i - 1], s_seq[i]
        b0, b1 = m_seq[i - 1], m_seq[i]
        if (a1["y"] != b1["y"]) and y_bad is None:
            y_bad = (i, a1["y"], b1["y"])
        for k in ("x", "z"):
            want = f32(b0[k] + f32(1.5 * (a1[k] - a0[k]))) - b0[k]
            got = b1[k] - b0[k]
            tol = 4 * 2 ** -23 * max(1.0, abs(b0[k]), abs(a0[k]))
            if abs(want - got) > tol and h_bad is None:
                h_bad = (i, k, want, got)
            sum_s += abs(a1[k] - a0[k])
            sum_m += abs(got)
    ratio = (sum_m / sum_s) if sum_s > 1.0 else None
    ratio_ok = ratio is None or abs(ratio - 1.5) < 1e-6
    ok = y_bad is None and h_bad is None and ratio_ok and window >= min(20, n)
    detail = (f"(window {window}/{n}; cumulative ratio "
              f"{'n/a (stationary)' if ratio is None else f'{ratio:.9f}'})")
    if y_bad:
        detail += f"\n    R2y break at +{y_bad[0]}: y sm64 {y_bad[1]:.9g} vs mod {y_bad[2]:.9g}"
    if h_bad:
        detail += (f"\n    R2s break at +{h_bad[0]} ({h_bad[1]}): "
                   f"expected delta {h_bad[2]:.9g} got {h_bad[3]:.9g}")
    check(f"{name}: shipped transform holds over the pre-arrival window", ok, detail)
    if geo_div is not None and (act_div is None or geo_div < act_div):
        b = m_seq[geo_div]
        ev = (f"+{geo_div} (geometry clamp): mod {act(b['action'])} "
              f"z={b['z']:.1f} stops tracking the 1.5x prediction")
        print(f"  [F2-EVIDENCE] earlier-arrival divergence at {ev}")
        return (name, window, n, ev)
    if act_div is not None:
        a, b = s_seq[act_div], m_seq[act_div]
        ev = (f"+{act_div}: sm64 {act(a['action'])} z={a['z']:.1f} vs "
              f"mod {act(b['action'])} z={b['z']:.1f}")
        print(f"  [F2-EVIDENCE] earlier-arrival divergence at {ev}")
        return (name, window, n, ev)
    return (name, window, n, "none -- streams identical over the horizon")


def check_void_edge_recovery(name, m_rows, horizon):
    if not name.startswith("S21 "):
        return
    mi = anchor(m_rows, 73)
    if mi is None:
        check(f"{name}: void edge remains recoverable", False, "(no mod anchor)")
        return
    seq = m_rows[mi:mi + horizon]
    penetrated = next(((i, r) for i, r in enumerate(seq)
                       if r["z"] < 899.9 or r["floorh"] <= -10000.0), None)
    reverse = seq[80:125]
    escaped = bool(reverse) and max(r["z"] for r in reverse) > 1000.0
    detail = ""
    if penetrated:
        i, r = penetrated
        detail = f"(+{i}: z={r['z']:.3f}, floor={r['floorh']:.3f})"
    elif not escaped:
        detail = "(reverse input did not move the center back above z=1000)"
    check(f"{name}: void edge remains recoverable", penetrated is None and escaped, detail)


def check_shipped_wall_containment(name, m_rows, horizon):
    """Regression for post-step speed compensation crossing an already-solid wall.

    Variant B's near box face is z=900 and the airborne body radius is 50, so Mario's
    center must remain at z>=950 while below its y=300 top.  The old test stopped at
    first geometry divergence and missed the illegal 942/953/948 oscillation entirely.
    """
    if name.startswith("S21 "):
        return
    if not name.startswith(("S14 ", "S15 ", "S16 ", "S17 ", "S18 ", "S19 ", "S20 ")):
        return
    mi = anchor(m_rows, 73)
    if mi is None:
        check(f"{name}: scaled endpoint remains outside wall", False, "(no mod anchor)")
        return
    seq = m_rows[mi:mi + horizon]
    bad = next(((i, r) for i, r in enumerate(seq[:45])
                if r["y"] < 299.0 and r["z"] < 949.9), None)
    detail = ""
    if bad is not None:
        i, r = bad
        detail = (f"(+{i}: center z={r['z']:.3f}, y={r['y']:.3f}; "
                  "wall requires z>=950 below its top)")
    check(f"{name}: scaled endpoint remains outside wall", bad is None, detail)


# R3 sound families -- the buckets the mod's play_sound shim declares (support.c):
# random id variation inside a family (rand%3 / rand%5) makes exact ids non-deterministic
# across games, so families are the comparable unit.
def sound_family(bits):
    bank = (bits >> 28) & 0xF
    sid = (bits >> 16) & 0xFF
    if bank == 0:
        for hi, nm in ((0x07, "JUMP"), (0x0F, "LAND"), (0x17, "STEP"), (0x1F, "BODYHIT")):
            if sid <= hi:
                return f"act.{nm}"
        if 0x30 <= sid <= 0x32:
            return "act.SPLASH"
        if sid in (0x33, 0x47):
            return "act.SWIM"
        if sid in (0x37, 0x38):
            return "act.SPIN"
        if sid in (0x42, 0x44, 0x45):
            return "act.BONK"
        if 0x60 <= sid <= 0x67:
            return "act.HEAVY"
        return f"act.{sid:02x}"
    if bank == 2:
        if sid <= 0x02:
            return "voi.YAH_WAH_HOO"
        if 0x2B <= sid <= 0x2F:
            return "voi.YAHOO_WAHA_YIPPEE"
        return f"voi.{sid:02x}"
    return None  # other banks: camera/menu/env/objects -- not Mario's kernel stream


def read_sounds(side):
    """(tick, family) stream from the JSONL the plugin drained during the last run.
    sm64 records frame=gGlobalTimer (== tick axis); mod records the sandbox tick in b."""
    import glob
    import json
    out = []
    for f in sorted(glob.glob(os.path.join(side.last_dir, "*.jsonl"))):
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("tag") != "snd":
                continue
            fam = sound_family(r["a"] & 0xFFFFFFFF)
            if fam is None:
                continue
            tick = r["frame"] if side.name == "sm64" else r["b"]
            out.append((tick, fam))
    return out


def main_sounds():
    load_act_names()
    print("R3 sound-event relation -- REPORT TIER (families, not gate)")
    sm64, mod = make_pair("")
    sm64.snd_head = va(sm64.rom, "dsceSndHead")
    sm64.snd_ring = va(sm64.rom, "dsceSndRing")
    mod.snd_head = va(mod.rom, "gDsceLogHead")
    mod.snd_ring = va(mod.rom, "gDsceLogRing")
    sm64.calibrate()
    mod.calibrate()
    findings = 0
    for name, variant, inputs, xfail in SCENARIOS:
        if variant != "A":
            continue
        s_rows = sm64.run(sm64.compile_rules(inputs), want_sounds=True)
        s_snd = read_sounds(sm64)
        m_rows = mod.run(mod.compile_rules(inputs), want_sounds=True)
        m_snd = read_sounds(mod)
        si = anchor(s_rows, 148)
        mi = anchor(m_rows, 73)
        if si is None or mi is None:
            continue
        s0, m0 = s_rows[si]["tick"], m_rows[mi]["tick"]
        horizon = max(rel + dur for rel, dur, *_ in inputs) + 30
        s_seq = [(t - s0, f) for t, f in s_snd if 0 <= t - s0 < horizon]
        m_seq = [(t - m0, f) for t, f in m_snd if 0 <= t - m0 < horizon]
        n = min(len(s_seq), len(m_seq))
        div = next((i for i in range(n) if s_seq[i] != m_seq[i]), None)
        if div is None and len(s_seq) == len(m_seq):
            print(f"  [MATCH] {name}: {len(s_seq)} sound events, families+ticks aligned")
        else:
            findings += 1
            i = div if div is not None else n
            print(f"  [FINDING R3] {name}: {len(s_seq)} vs {len(m_seq)} events; "
                  f"first mismatch at event {i}:")
            for j in range(max(0, i - 2), min(i + 3, max(len(s_seq), len(m_seq)))):
                a = s_seq[j] if j < len(s_seq) else ("-", "-")
                b = m_seq[j] if j < len(m_seq) else ("-", "-")
                print(f"      #{j}: sm64 t+{a[0]} {a[1]:<24} | mod t+{b[0]} {b[1]}")
    print(f"\n{findings} R3 finding(s) (report tier -- informational, exit 0)")
    sys.exit(0)


def main_shipped():
    load_act_names()
    VSUFFIX = {"A": "", "B": "-b", "C": "-c", "D": "-d"}
    pairs = {}

    def pair(variant):
        if variant not in pairs:
            print(f"calibrating variant {variant} (shipped mod)...")
            sm64, mod = make_pair(VSUFFIX[variant], shipped=True)
            sm64.calibrate()
            mod.calibrate()
            pairs[variant] = (sm64, mod)
        return pairs[variant]

    evidence = []
    for name, variant, inputs, xfail in SCENARIOS:
        sm64, mod = pair(variant)
        s_rows = sm64.run(sm64.compile_rules(inputs))
        m_rows = mod.run(mod.compile_rules(inputs))
        horizon = max(rel + dur for rel, dur, *_ in inputs) + 30
        compare_horizon = 75 if name.startswith("S21 ") else horizon
        row = compare_shipped(name, s_rows, m_rows, compare_horizon)
        check_void_edge_recovery(name, m_rows, horizon)
        check_shipped_wall_containment(name, m_rows, horizon)
        if row:
            evidence.append(row)

    print("\n== F2 evidence table (paste into docs/XGAME_METAMORPHIC.md) ==")
    for name, window, n, ev in evidence:
        print(f"  {name}: exact {window}/{n}; arrival {ev}")
    print(f"\n{FAIL} failure(s)")
    sys.exit(1 if FAIL else 0)


def main():
    load_act_names()
    # Bursts run EARLY, from untouched settled idle: both cameras are provably exact
    # (x stays bit-equal on straight pushes) in the early window, before SM64's idle
    # camera starts to drift; the mod's entrance cutscene releases the pad by ~tick 70.
    VSUFFIX = {"A": "", "B": "-b", "C": "-c", "D": "-d"}
    pairs = {}

    def pair(variant):
        if variant not in pairs:
            print(f"calibrating variant {variant} (tick->poll + input latency)...")
            sm64, mod = make_pair(VSUFFIX[variant])
            cal = (sm64.calibrate(), mod.calibrate())
            pairs[variant] = (sm64, mod, cal)
        return pairs[variant]

    for name, variant, inputs, xfail in SCENARIOS:
        sm64, mod, _ = pair(variant)
        s_rows = sm64.run(sm64.compile_rules(inputs))
        m_rows = mod.run(mod.compile_rules(inputs))
        horizon = max(rel + dur for rel, dur, *_ in inputs) + 30
        compare_horizon = 75 if name.startswith("S21 ") else horizon
        compare(name, s_rows, m_rows, sm64, mod, xfail, compare_horizon)
        check_void_edge_recovery(name, m_rows, horizon)

    check_idle_decay(*pair("A")[2])

    print("\nCoverage:")
    seen_names = {act(a) for a in OBSERVED}
    missing = [c for c in CORE if c not in seen_names]
    check("coverage: every CORE mechanic observed", not missing,
          f"(missing: {missing})" if missing else f"({len(CORE)} core ids)")
    pend = [p for p in PENDING if p not in seen_names]
    if pend:
        print(f"  [PENDING] not yet authored (timing-critical approaches): {pend}")
    print(f"  observed {len(OBSERVED)} distinct actions total: "
          + " ".join(sorted(act(a) for a in OBSERVED)))

    print(f"\n{FAIL} failure(s)")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    if "--sounds" in sys.argv:
        main_sounds()
    elif "--shipped" in sys.argv:
        main_shipped()
    else:
        main()
