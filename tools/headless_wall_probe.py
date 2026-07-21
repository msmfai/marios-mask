#!/usr/bin/env python3
"""Drive Mario into real MM boundaries and record detection/recovery evidence.

This is a debug-only observation harness.  It does not classify geometry as an
"invisible wall" itself.  Isolated scenarios exercise walking and aerial moves against
cardinal walls and diagonal corners, then steer back to the known spawn in world
coordinates.  The raw telemetry and wall-adapter PEEK counters are retained so a human
can distinguish no detection, repeated push-out, and failure to escape.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import run_tests as rt


HERE = Path(__file__).resolve().parent.parent
DEFAULT_ROM = HERE / "out" / "mm-dsce-test-laundry-pool-debug-dbg0010.z64"
INPUTBOT = HERE / "tools" / "inputbot" / "mupen64plus-input-script.dylib"
NULLVIDEO = HERE / "tools" / "inputbot" / "mupen64plus-video-null.dylib"

# Camera-relative pad sweeps.  Separate savestate-restored runs give every direction the
# same initial scene/camera/player state.
DIRECTIONS = {
    "forward": (0, 80),
    "back": (0, -80),
    "left": (-80, 0),
    "right": (80, 0),
    "forward_left": (-80, 80),
    "forward_right": (80, 80),
    "back_left": (-80, -80),
    "back_right": (80, -80),
}

# Canonical SM64-space spawn read from the shared warm savestate. World sweeps use the
# plugin's self-calibrating GOTO steering, so camera rotation cannot turn the nominal
# "escape" input back toward the same wall.
# Exact gMarioState position in the real-mask warm state (SM64/canonical units).
SPAWN_CANON = (-6311.51221, 1624.9574)
WORLD_TARGETS = {
    "north": (SPAWN_CANON[0], SPAWN_CANON[1] + 20000.0),
    "south": (SPAWN_CANON[0], SPAWN_CANON[1] - 20000.0),
    "east": (SPAWN_CANON[0] + 20000.0, SPAWN_CANON[1]),
    "west": (SPAWN_CANON[0] - 20000.0, SPAWN_CANON[1]),
    "north_east": (SPAWN_CANON[0] + 20000.0, SPAWN_CANON[1] + 20000.0),
    "north_west": (SPAWN_CANON[0] - 20000.0, SPAWN_CANON[1] + 20000.0),
    "south_east": (SPAWN_CANON[0] + 20000.0, SPAWN_CANON[1] - 20000.0),
    "south_west": (SPAWN_CANON[0] - 20000.0, SPAWN_CANON[1] - 20000.0),
}


def canonical(mmx: float, mmz: float):
    return (mmx * 4.29, mmz * 4.29)


# Target points deliberately placed beyond specific dry Laundry Pool collision boundaries.
# Coordinates come from Z2_ALLEYCollisionHeader_0028A8, not from visual guesswork. Four
# east-wall slices catch height/corner differences; north/south probes cover its ends.
GEOMETRY_TARGETS = {
    "east_wall_south": canonical(-500.0, 50.0),
    "east_wall_mid": canonical(-500.0, 250.0),
    "east_wall_spawn": canonical(-500.0, 400.0),
    "east_wall_north": canonical(-500.0, 560.0),
    "north_end": canonical(-900.0, 1000.0),
    "south_end": canonical(-900.0, -500.0),
}

WARM_SHIFT = rt.WARM_SHIFT
APPROACH = (2400 - WARM_SHIFT, 4300 - WARM_SHIFT)
NEUTRAL = (4300 - WARM_SHIFT, 4700 - WARM_SHIFT)
ESCAPE = (4700 - WARM_SHIFT, 5500 - WARM_SHIFT)
STOP = 5600 - WARM_SHIFT
_mask_state_lock = threading.Lock()


def ensure_mask_state(rom: Path):
    """Cache a state produced by the real Brother's Mask transformation path."""
    with _mask_state_lock:
        state_dir = HERE / "out" / "statecache"
        state_dir.mkdir(parents=True, exist_ok=True)
        state = state_dir / f"{rt.rom_md5(str(rom))}-mask.st"
        if state.exists():
            return str(state)
        print(f"  [state] equipping real mask in {rom.name} to build boundary-test state...")
        # Testboot grants the mask on C-left. Saving on takeover tick 60 is invariant to
        # transformation/reload timing and guarantees this is the mask-owned actor, not L+R+Z.
        rt._run_raw("2400 2410 CL 0 0\n", 3800, f"mask-state-{rom.name}", str(rom),
                    extra_env={"CT_STATE_SAVE_ON_TICKS": "60", "CT_STATE_PATH": str(state)})
        return str(state) if state.exists() else None


def va(rom: Path, symbol: str) -> str:
    for line in Path(str(rom) + ".va").read_text().splitlines():
        key, _, value = line.partition("=")
        if key == symbol:
            return value
    raise SystemExit(f"{symbol} missing from {rom}.va")


def signed32(value: int) -> int:
    return value - 0x100000000 if value & 0x80000000 else value


def rules_for(x: int, y: int) -> str:
    cold = rt.SPAWN_PULSE
    cold += f"2400 4300 NONE {x} {y}\n"
    cold += "4300 4700 NONE 0 0\n"
    cold += f"4700 5500 NONE {-x} {-y}\n"
    return rt._shift_rules(cold, WARM_SHIFT)


def world_rules_for(tx: float, tz: float) -> str:
    # Already warm-timeline rules: drive toward a distant world target, release, then
    # explicitly steer back to the known starting point. GOTO's occasional hop is retained
    # as a stronger recovery attempt and is visible in the action trace.
    return (f"G {APPROACH[0]} {APPROACH[1]} {tx:.1f} {tz:.1f} 50\n"
            f"{NEUTRAL[0]} {NEUTRAL[1]} NONE 0 0\n"
            f"G {ESCAPE[0]} {ESCAPE[1]} {SPAWN_CANON[0]:.1f} {SPAWN_CANON[1]:.1f} 50\n")


def oob_rules_for(tx: float, tz: float, move: str) -> str:
    """World-steered boundary pressure with explicit, repeatable move inputs."""
    lines = [f"G {APPROACH[0]} {APPROACH[1]} {tx:.1f} {tz:.1f} 50"]
    late = move.startswith("late_")
    base_move = move.removeprefix("late_")
    action_start = APPROACH[0] + (1050 if late else 180)
    if base_move == "jump":
        for poll in range(action_start, APPROACH[1] - 8, 105):
            lines.append(f"H {poll} {poll + 8} A {tx:.1f} {tz:.1f} 50")
    elif base_move == "long_jump":
        for poll in range(max(action_start, APPROACH[0] + 300), APPROACH[1] - 18, 165):
            lines.append(f"H {poll} {poll + 8} Z {tx:.1f} {tz:.1f} 50")
            lines.append(f"H {poll + 8} {poll + 16} A,Z {tx:.1f} {tz:.1f} 50")
    elif base_move == "dive":
        for poll in range(max(action_start, APPROACH[0] + 300), APPROACH[1] - 32, 180):
            lines.append(f"H {poll} {poll + 8} A {tx:.1f} {tz:.1f} 50")
            lines.append(f"H {poll + 18} {poll + 28} B {tx:.1f} {tz:.1f} 50")
    elif base_move != "walk":
        raise ValueError(f"unknown move: {move}")
    lines.append(f"{NEUTRAL[0]} {NEUTRAL[1]} NONE 0 0")
    lines.append(f"G {ESCAPE[0]} {ESCAPE[1]} {SPAWN_CANON[0]:.1f} {SPAWN_CANON[1]:.1f} 50")
    return "\n".join(lines) + "\n"


def pinned_back_world_escape_rules() -> str:
    """Reproduce the raw-back pin, then remove camera-relative escape ambiguity."""
    return (f"{APPROACH[0]} {APPROACH[1]} NONE 0 -80\n"
            f"{NEUTRAL[0]} {NEUTRAL[1]} NONE 0 0\n"
            f"G {ESCAPE[0]} {ESCAPE[1]} {SPAWN_CANON[0]:.1f} {SPAWN_CANON[1]:.1f} 50\n")


def jumping_boundary_rules(x: int, y: int) -> str:
    """Hold toward a boundary, repeatedly jump, then recover in world coordinates."""
    lines = [f"{APPROACH[0]} {APPROACH[1]} NONE {x} {y}"]
    # Later rules override the held-stick rule. Eight input polls is a clean press long
    # enough for MM's buffered controller path; spacing permits jump/land cycles.
    for poll in range(APPROACH[0] + 180, APPROACH[1] - 5, 105):
        lines.append(f"{poll} {poll + 8} A {x} {y}")
    lines.append(f"{NEUTRAL[0]} {NEUTRAL[1]} NONE 0 0")
    lines.append(f"G {ESCAPE[0]} {ESCAPE[1]} {SPAWN_CANON[0]:.1f} {SPAWN_CANON[1]:.1f} 50")
    return "\n".join(lines) + "\n"


def parse_raw(path: Path):
    samples = {}
    peeks = []
    play_samples = []
    lifecycle = []
    with path.open() as f:
        for row in csv.reader(f):
            if not row:
                continue
            if row[0] == "DSCE" and len(row) >= 21:
                tick = int(row[2])
                if 0 < tick < 0xBB00:
                    poll = int(row[1])
                    samples[poll] = {
                        "poll": int(row[1]), "tick": tick, "tick_us": int(row[3]),
                        "action": int(row[7], 16), "x": float(row[8]),
                        "y": float(row[9]), "z": float(row[10]),
                    }
            elif row[0] == "PEEK" and len(row) >= 6:
                peeks.append({
                    "poll": int(row[1]), "queries": int(row[2]), "hits": int(row[3]),
                    "push_x": signed32(int(row[4])) / 100.0,
                    "push_z": signed32(int(row[5])) / 100.0,
                })
            elif row[0] == "PEEK2" and len(row) >= 10:
                packed = int(row[5])
                actor_state = int(row[7])
                lifecycle.append({
                    "poll": int(row[1]), "play_frame": int(row[2]),
                    "state_flags1": int(row[3]), "state_flags2": int(row[4]),
                    "current_room": (packed >> 24) & 0xFF,
                    "previous_room": (packed >> 16) & 0xFF,
                    "cutscene": (packed >> 8) & 1, "message_mode": packed & 0xFF,
                    "spike_alive": int(row[6]), "actor_freeze_timer": actor_state >> 16,
                    "actor_has_update": actor_state & 1, "actor_flags": int(row[8]),
                    "transformation": int(row[9]) & 0xFF,
                    "via_mask": (int(row[9]) >> 8) & 1,
                    "transition_trigger": (int(row[9]) >> 16) & 0xFF,
                    "transition_mode": (int(row[9]) >> 24) & 0xFF,
                })
            elif row[0].isdigit() and len(row) == 8:
                # With CT_TICK_ADDR=gDscePlayFrame, this is one row per live PlayState
                # update. It lets us distinguish a stopped Mario actor from a stopped game.
                play_samples.append((int(row[1]), int(row[0])))
    rows = sorted(samples.values(), key=lambda r: r["poll"])
    play_index = 0
    lifecycle_index = 0
    current_play_frame = None
    current_lifecycle = None
    for sample in rows:
        while (play_index < len(play_samples) and
               play_samples[play_index][0] <= sample["poll"]):
            current_play_frame = play_samples[play_index][1]
            play_index += 1
        sample["play_frame"] = current_play_frame
        while (lifecycle_index < len(lifecycle) and
               lifecycle[lifecycle_index]["poll"] <= sample["poll"]):
            current_lifecycle = lifecycle[lifecycle_index]
            lifecycle_index += 1
        if current_lifecycle:
            for key in ("state_flags1", "state_flags2", "current_room",
                        "previous_room", "cutscene", "message_mode", "spike_alive",
                        "actor_freeze_timer", "actor_has_update", "actor_flags",
                        "transformation", "via_mask", "transition_trigger", "transition_mode"):
                sample[key] = current_lifecycle[key]
    return rows, peeks


def phase_rows(rows, bounds):
    lo, hi = bounds
    return [r for r in rows if lo <= r["poll"] < hi]


def displacement(rows):
    if len(rows) < 2:
        return 0.0
    return math.hypot(rows[-1]["x"] - rows[0]["x"], rows[-1]["z"] - rows[0]["z"])


def max_stall(rows, epsilon=0.02):
    longest = run = 0
    for a, b in zip(rows, rows[1:]):
        if math.hypot(b["x"] - a["x"], b["z"] - a["z"]) <= epsilon:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def peek_at(peeks, poll):
    eligible = [p for p in peeks if p["poll"] <= poll]
    return eligible[-1] if eligible else None


def summarize(name, rows, peeks):
    phases = {key: phase_rows(rows, bounds) for key, bounds in (
        ("approach", APPROACH), ("neutral", NEUTRAL), ("escape", ESCAPE))}
    p0 = peek_at(peeks, APPROACH[0])
    p1 = peek_at(peeks, APPROACH[1])
    hit_delta = (p1["hits"] - p0["hits"]) if p0 and p1 else None
    query_delta = (p1["queries"] - p0["queries"]) if p0 and p1 else None
    e0 = peek_at(peeks, ESCAPE[0])
    e1 = peek_at(peeks, ESCAPE[1])
    escape_hits = (e1["hits"] - e0["hits"]) if e0 and e1 else None
    tail = phases["approach"][-40:]
    approach_stall = max_stall(tail)
    escape_distance = displacement(phases["escape"])
    escape_actor_ticks = ((phases["escape"][-1]["tick"] - phases["escape"][0]["tick"])
                          if len(phases["escape"]) >= 2 else None)
    escape_play_frames = None
    if (len(phases["escape"]) >= 2 and
            phases["escape"][0].get("play_frame") is not None and
            phases["escape"][-1].get("play_frame") is not None):
        escape_play_frames = (phases["escape"][-1]["play_frame"] -
                              phases["escape"][0]["play_frame"])
    reached_candidate = approach_stall >= 15
    tail_actions = sorted({r["action"] for r in tail})
    escape_tail_actions = {r["action"] for r in phases["escape"][-40:]}
    first = rows[0] if rows else None
    last = rows[-1] if rows else None
    if last and last.get("spike_alive") == 0:
        observation = "takeover actor was destroyed while PlayState remained live"
    elif (escape_play_frames or 0) > 0 and escape_actor_ticks == 0:
        observation = "takeover actor stopped updating while PlayState remained live"
    elif escape_tail_actions and all((a & 0x1C0) == 0xC0 for a in escape_tail_actions):
        observation = "entered submerged action; not a wall result"
    elif tail_actions and all((a & 0x1C0) == 0xC0 for a in tail_actions):
        observation = "entered submerged action; not a wall result"
    elif not reached_candidate:
        observation = "no sustained boundary stall reached"
    elif hit_delta == 0:
        observation = "stalled with no wall-adapter hit"
    elif escape_distance < 1.0:
        observation = "wall detected, but opposite input did not recover"
    else:
        observation = "wall detected and opposite input escaped"
    return_distance = (math.hypot(last["x"] - first["x"], last["z"] - first["z"])
                       if first and last else None)
    return {
        "scenario": name,
        "samples": len(rows),
        "approach_displacement_mm": round(displacement(phases["approach"]), 3),
        "approach_tail_stall_ticks": approach_stall,
        "neutral_displacement_mm": round(displacement(phases["neutral"]), 3),
        "escape_displacement_mm": round(escape_distance, 3),
        "escape_actor_ticks_elapsed": escape_actor_ticks,
        "escape_play_frames_elapsed": escape_play_frames,
        "approach_wall_queries": query_delta,
        "approach_wall_hits": hit_delta,
        "escape_wall_hits": escape_hits,
        "last_push_mm": ([p1["push_x"], p1["push_z"]] if p1 else None),
        "max_y_mm": round(max((r["y"] for r in rows), default=0.0), 3),
        "actions_seen": [f"0x{a:08x}" for a in sorted({r["action"] for r in rows})],
        "final_distance_from_initial_mm": round(return_distance, 3) if return_distance is not None else None,
        "final": last,
        "observation": observation,
    }


def action_transitions(rows):
    transitions = []
    previous = None
    for row in rows:
        if row["action"] != previous:
            transitions.append({"poll": row["poll"], "tick": row["tick"],
                                "action": f"0x{row['action']:08x}",
                                "x": row["x"], "y": row["y"], "z": row["z"]})
            previous = row["action"]
    return transitions


def lifecycle_transitions(rows):
    transitions = []
    previous = None
    for row in rows:
        current = tuple(row.get(key) for key in
                        ("state_flags1", "state_flags2", "current_room",
                         "previous_room", "cutscene", "message_mode", "spike_alive",
                         "actor_freeze_timer", "actor_has_update", "actor_flags",
                         "transformation", "via_mask", "transition_trigger", "transition_mode"))
        if current != previous:
            transitions.append({
                "poll": row["poll"], "play_frame": row.get("play_frame"),
                "actor_tick": row["tick"], "state_flags1": f"0x{(current[0] or 0):08x}",
                "state_flags2": f"0x{(current[1] or 0):08x}",
                "current_room": current[2], "previous_room": current[3],
                "cutscene": current[4], "message_mode": current[5],
                "spike_alive": current[6], "actor_freeze_timer": current[7],
                "actor_has_update": current[8],
                "actor_flags": f"0x{(current[9] or 0):08x}",
                "transformation": current[10], "via_mask": current[11],
                "transition_trigger": current[12], "transition_mode": current[13],
            })
            previous = current
    return transitions


def run_one(rom: Path, state: str, root: Path, name: str, rules: str,
            metadata=None, goto_unstick=False):
    out = root / name
    out.mkdir(parents=True)
    (out / "rules.txt").write_text(rules)
    raw = out / "raw.csv"
    cfg = out / "mupen-config"
    cfgsrc = Path.home() / "Library" / "Application Support" / "Mupen64Plus"
    shutil.copytree(cfgsrc, cfg) if cfgsrc.is_dir() else cfg.mkdir()
    env = dict(os.environ,
               CT_INPUT_SCRIPT=str(out / "rules.txt"),
               CT_DSCE_ADDR=va(rom, "gDsceTelemetry"),
               CT_MARIO_ADDR=va(rom, "gDsceMarioState"),
               CT_PEEK_ADDR=va(rom, "gDsceProbe"),
               CT_PEEK2_ADDR=va(rom, "gDsceLifecycleProbe"),
               CT_TELEMETRY=str(raw), CT_MAX_FRAMES=str(STOP),
               CT_STATE_LOAD=state,
               CT_TICK_ADDR=va(rom, "gDscePlayFrame"),
               CT_GOTO_UNSTICK="1" if goto_unstick else "0")
    proc = subprocess.run([
        "mupen64plus", "--nospeedlimit", "--audio", "dummy",
        "--configdir", str(cfg), "--datadir", str(cfg),
        "--gfx", str(NULLVIDEO), "--input", str(INPUTBOT), str(rom),
    ], env=env, capture_output=True, text=True, timeout=600, check=False)
    (out / "emulator.stderr.log").write_text(proc.stderr)
    (out / "emulator.stdout.log").write_text(proc.stdout)
    rows, peeks = parse_raw(raw)
    result = summarize(name, rows, peeks)
    result["metadata"] = metadata or {}
    result["goto_unstick"] = goto_unstick
    result["exit_code"] = proc.returncode
    (out / "action-transitions.json").write_text(
        json.dumps(action_transitions(rows), indent=2) + "\n")
    (out / "lifecycle-transitions.json").write_text(
        json.dumps(lifecycle_transitions(rows), indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    ap.add_argument("--directions", nargs="*", choices=sorted(DIRECTIONS),
                    default=list(DIRECTIONS))
    ap.add_argument("--world", action="store_true",
                    help="run four world-coordinate approach/return sweeps instead")
    ap.add_argument("--jump", action="store_true",
                    help="repeat jumps while approaching, then use world-coordinate recovery")
    ap.add_argument("--oob", action="store_true",
                    help="run broad world-coordinate walk/jump/long-jump/dive boundary matrix")
    ap.add_argument("--geometry-oob", action="store_true",
                    help="pressure known dry Z2_ALLEY collision boundaries after a walk-up")
    ap.add_argument("--only", nargs="*", metavar="SCENARIO",
                    help="run only named scenarios from the selected matrix")
    args = ap.parse_args()
    rom = args.rom.resolve()
    if not rom.exists():
        raise SystemExit(f"missing debug ROM: {rom}")
    state = ensure_mask_state(rom)
    if not state:
        raise SystemExit("could not create real-mask warm savestate")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = HERE / "out" / "headless-wall-runs" / stamp
    root.mkdir(parents=True)
    manifest = {
        "rom": str(rom),
        "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
        "state": state,
        "state_kind": "real Brother's Mask transform (C-left), takeover tick 60",
        "probe_words": ["wall queries", "wall hits", "last push x*100", "last push z*100"],
        "results": [],
    }
    if args.geometry_oob:
        scenarios = {}
        for move in ("walk", "late_jump", "late_long_jump", "late_dive"):
            for boundary, target in GEOMETRY_TARGETS.items():
                name = f"{move}_{boundary}"
                scenarios[name] = (oob_rules_for(*target, move),
                                   {"move": move, "boundary": boundary, "target": target,
                                    "source": "Z2_ALLEYCollisionHeader_0028A8"})
    elif args.oob:
        scenarios = {}
        for move in ("walk", "jump"):
            for heading, target in WORLD_TARGETS.items():
                name = f"{move}_{heading}"
                scenarios[name] = (oob_rules_for(*target, move),
                                   {"move": move, "heading": heading, "target": target})
        for move in ("long_jump", "dive"):
            for heading in ("north", "south", "east", "west"):
                target = WORLD_TARGETS[heading]
                name = f"{move}_{heading}"
                scenarios[name] = (oob_rules_for(*target, move),
                                   {"move": move, "heading": heading, "target": target})
    elif args.world:
        scenarios = {f"world_{name}": (world_rules_for(*target),
                     {"move": "walk", "heading": name, "target": target})
                     for name, target in WORLD_TARGETS.items()}
        scenarios["raw_back_world_escape"] = (pinned_back_world_escape_rules(),
                                               {"move": "walk_raw_then_world"})
    elif args.jump:
        scenarios = {f"jump_{name}": (jumping_boundary_rules(*DIRECTIONS[name]),
                     {"move": "jump", "camera_direction": name})
                     for name in args.directions}
    else:
        scenarios = {name: (rules_for(*DIRECTIONS[name]),
                     {"move": "walk", "camera_direction": name})
                     for name in args.directions}
    if args.only:
        unknown = sorted(set(args.only) - set(scenarios))
        if unknown:
            raise SystemExit(f"unknown scenario(s): {', '.join(unknown)}")
        scenarios = {name: scenarios[name] for name in args.only}
    for name, (rules, metadata) in scenarios.items():
        result = run_one(rom, state, root, name, rules, metadata=metadata)
        manifest["results"].append(result)
        print(f"{name:14s} {result['observation']}; "
              f"hits={result['approach_wall_hits']} escape={result['escape_displacement_mm']:.2f}mm")
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"headless wall evidence: {root}")


if __name__ == "__main__":
    main()
