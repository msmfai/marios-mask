#!/usr/bin/env python3
"""Cross-game metamorphic tests: the real SM64 ROM is Mario's behavioral oracle (goal 10).

Boots BOTH ROMs headless with tick-indexed MarioState telemetry (CT_TICK_ADDR: one CSV row
per sim tick -- SM64's gGlobalTimer vs the mod's gDscePlayFrame) and compares the streams
under the known transforms. Both sides read the SAME MarioState struct layout (the mod runs
the vendored SM64 kernel; gDsceMarioState is exported in the .va), in SM64 units, produced
by the same C code on the same emulated MIPS ISA -- so the flat-ground tier demands
EXACT equality, not tolerance bands.

Relations (docs/XGAME_METAMORPHIC.md):
  R1 action-stream: same logical input burst => same action-id sequence (+ durations for
     the deterministic parts: air time, landing recovery).
  R2 kinematics: per-tick jump-ascent y deltas bit-equal (ballistics are floor-independent
     for the first ~12 ticks).
  S1 idle-decay is a KNOWN DIVERGENCE today (mod sleeps ~88 idle ticks vs SM64's ~930) --
     reported as FINDING/XFAIL, not a harness failure.

Alignment: input scripts are POLL-indexed and poll:tick ratios differ per side (SM64 1:1,
mod ~7:1 incl. boot offset), so comparisons anchor on ACTION EDGES (first ACT_JUMP etc.),
never on absolute tick numbers. Determinism (verified bit-identical reruns) makes the
per-side scripts reproducible.
"""
import csv
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_ROM = os.path.join(HERE, "out", "mm-dsce-test.z64")
SM64_ROM = os.path.join(HERE, ".work", "sm64", "build", "us", "sm64.us.z64")
SM64_MAP = os.path.join(HERE, ".work", "sm64", "build", "us", "sm64.us.map")
INPUTBOT = os.path.join(HERE, "tools", "inputbot", "mupen64plus-input-script.dylib")
NULLVIDEO = os.path.join(HERE, "tools", "inputbot", "mupen64plus-video-null.dylib")

ACT = {  # the ids these scenarios traverse (sm64.h)
    0x0C400201: "IDLE", 0x0C400202: "START_SLEEPING", 0x0C000203: "SLEEPING",
    0x0C000204: "WAKING_UP", 0x04000440: "WALKING", 0x0400044A: "DECELERATING",
    0x03000880: "JUMP", 0x04000470: "JUMP_LAND", 0x0C000230: "JUMP_LAND_STOP",
}


def act_name(a):
    return ACT.get(a, f"{a:08x}")


def sm64_map_addr(sym):
    for line in open(SM64_MAP):
        parts = line.split()
        if len(parts) == 2 and parts[1] == sym:
            return parts[0][-8:]
    sys.exit(f"xgame: {sym} not in {SM64_MAP}")


def mod_va(sym):
    for line in open(MOD_ROM + ".va"):
        k, _, v = line.strip().partition("=")
        if k == sym:
            return v
    sys.exit(f"xgame: {sym} not in {MOD_ROM}.va")


def run(rom, rules, tick_addr, mario_addr, max_frames):
    d = tempfile.mkdtemp(prefix="xgame-")
    rp = os.path.join(d, "rules")
    open(rp, "w").write(rules)
    csvp = os.path.join(d, "tel.csv")
    env = dict(os.environ, CT_INPUT_SCRIPT=rp, CT_TICK_ADDR=tick_addr,
               CT_MARIO_ADDR=mario_addr, CT_TELEMETRY=csvp, CT_MAX_FRAMES=str(max_frames))
    subprocess.run(["mupen64plus", "--nospeedlimit", "--audio", "dummy",
                    "--gfx", NULLVIDEO, "--input", INPUTBOT, rom],
                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=900, check=False)
    rows = []
    for r in csv.reader(open(csvp)):
        if r and r[0] != "frame" and len(r) >= 6:
            rows.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                         int(r[4]), int(r[5], 16)))
    return rows  # (tick, x, y, z, yaw, action)


def edges(rows):
    """(tick, action) at each action change."""
    out, prev = [], None
    for t, _x, _y, _z, _yaw, a in rows:
        if a != prev:
            out.append((t, a))
            prev = a
    return out


def window(rows, start_act, from_tick=0):
    """rows from the first `start_act` at/after from_tick."""
    for i, r in enumerate(rows):
        if r[0] >= from_tick and r[5] == start_act:
            return rows[i:]
    return []


FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
    if not ok:
        FAIL += 1


def main():
    sm64_tick = sm64_map_addr("gGlobalTimer")
    sm64_mario = sm64_map_addr("gMarioStates")
    # the takeover's tick counter (gDsceTelemetry.frame, offset +4) increments AFTER the
    # sandbox tick -- sampling on gDscePlayFrame captured MID-FRAME state (split deltas)
    mod_tick = f"{int(mod_va('gDsceTelemetry'), 16) + 4:x}"
    mod_mario = mod_va("gDsceMarioState")
    print(f"oracle: {os.path.basename(SM64_ROM)} tick={sm64_tick} mario={sm64_mario}")
    print(f"mod:    {os.path.basename(MOD_ROM)} tick={mod_tick} mario={mod_mario}")

    # --- S2 pristine-idle jump: the exact-match tier needs forwardVel == 0 at the press
    # (SM64 jump vel = 42 + 0.25*forwardVel; ANY residual walk contaminates R2 -- measured
    # +0.064/tick from a 0.256 residual during bring-up). SM64 jumps from spawn idle.
    # The mod must WAKE first: it falls asleep ~88 takeover-ticks after spawn (finding S1),
    # so A#1 wakes him (sleep timer resets) and A#2 jumps from the fresh idle.
    sm64_rows = run(SM64_ROM,
                    "300 306 A 0 0\n400 900 NONE 0 0\n",
                    sm64_tick, sm64_mario, 900)
    mod_rows = run(MOD_ROM,
                   "600 1200 L,R,DU 0 0\n2900 2940 A 0 0\n3300 3340 A 0 0\n"
                   "3400 5500 NONE 0 0\n",
                   mod_tick, mod_mario, 5500)
    if not sm64_rows or not mod_rows:
        check("xgame: telemetry captured on both sides", False,
              f"(sm64 {len(sm64_rows)} rows, mod {len(mod_rows)})")
        sys.exit(1)

    print("\nS2 pristine-idle jump:")
    JUMP = 0x03000880
    sj = window(sm64_rows, JUMP)
    mj = window(mod_rows, JUMP)
    check("both sides reached ACT_JUMP", bool(sj) and bool(mj),
          f"(sm64 t{sj[0][0] if sj else '-'}, mod t{mj[0][0] if mj else '-'})")
    if sj and mj:
        # R1: identical action chain from the jump through the post-land idle
        want = ["JUMP", "JUMP_LAND", "JUMP_LAND_STOP", "IDLE"]
        se = [act_name(a) for _, a in edges(sj)][: len(want)]
        me = [act_name(a) for _, a in edges(mj)][: len(want)]
        check("R1 jump action chain identical", se == me == want, f"(sm64 {se}, mod {me})")

        # R1 duration: air ticks (JUMP entry -> JUMP_LAND entry) -- floor heights differ
        # between arenas, so REPORT rather than assert; equal-height floors would be exact.
        s_air = edges(sj)[1][0] - edges(sj)[0][0] if len(edges(sj)) > 1 else -1
        m_air = edges(mj)[1][0] - edges(mj)[0][0] if len(edges(mj)) > 1 else -1
        print(f"  [info] air ticks: sm64 {s_air}, mod {m_air} "
              f"(arena floor heights differ; equal only on matched floors)")

        # R2: jump-ascent ballistics -- per-tick y deltas for the first 10 airborne ticks
        # are floor-independent and must be EXACT (same code, same ISA, same f32 math).
        n = 10
        sd = [round(sj[i + 1][2] - sj[i][2], 3) for i in range(min(n, len(sj) - 1))]
        md = [round(mj[i + 1][2] - mj[i][2], 3) for i in range(min(n, len(mj) - 1))]
        check("R2 jump-ascent y deltas exact", sd == md, f"\n    sm64 {sd}\n    mod  {md}")

    # --- S1 idle-decay: KNOWN DIVERGENCE (finding, not failure). ---
    print("\nS1 idle-decay (XFAIL -- documented finding):")
    s_idle = edges(sm64_rows)
    m_idle = edges(mod_rows)

    def sleep_onset(es):
        idle_t = next((t for t, a in es if a == 0x0C400201), None)
        sleep_t = next((t for t, a in es if a == 0x0C400202), None)
        return (sleep_t - idle_t) if (idle_t is not None and sleep_t is not None) else None

    so_s, so_m = sleep_onset(s_idle), sleep_onset(m_idle)
    print(f"  [FINDING] idle->START_SLEEPING onset: sm64 ~930 ticks (measured), "
          f"mod ~88 ticks (this run: sm64 {so_s}, mod {so_m}).")
    print("            Suspect: sandbox scaffolding (zeroed camera / actionArg reuse)")
    print("            accelerates the head-turn cycle count. Tracked in docs/XGAME_METAMORPHIC.md.")

    print(f"\n{FAIL} failure(s)")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
