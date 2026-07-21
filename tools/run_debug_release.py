#!/usr/bin/env python3
"""Run a DSCE debug ROM with isolated, automatic ROM diagnostics.

Every invocation creates out/debug-runs/<UTC timestamp>/ containing the frontend
log, read-only RDRAM firehose captures, one merged spool, one ClickHouse-local
database, symbols, metadata, and generated diagnosis reports. Non-debug ROMs are
rejected. RetroArch and its core are never patched or written through the command API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DEFAULT_ROM = ROOT / "out" / "mm-dsce-test-laundry-pool-nomask-debug.z64"
DEFAULT_RETROARCH = Path("/Applications/RetroArch.app/Contents/MacOS/RetroArch")
DEFAULT_CORE = Path.home() / "Library/Application Support/RetroArch/cores/mupen64plus_next_libretro.dylib"
STOP = False
FH_RECORD_SIZE = 32
FH_RING_RECORDS = 1024
SEQ_FLIGHT_RECORD_SIZE = 32
SEQ_FLIGHT_RING_RECORDS = 1024
MEMORY_READ_CHUNK = 1024
ACCURACY_PROFILE_NAME = "n64-strict-software-lle-v1"
# Deliberately conservative: no dynarec, no HLE RSP/RDP, no overclock, no
# compatibility hacks, original VI filtering, and the Expansion Pak present.
# Angrylion's own option text says one thread behaves like the original renderer;
# High synchronization trades performance for accuracy.
ACCURACY_CORE_OPTIONS = {
    "mupen64plus-rdp-plugin": "angrylion",
    "mupen64plus-rsp-plugin": "cxd4",
    "mupen64plus-cpucore": "pure_interpreter",
    "mupen64plus-angrylion-vioverlay": "Filtered",
    "mupen64plus-angrylion-sync": "High",
    "mupen64plus-angrylion-multithread": "1",
    "mupen64plus-angrylion-overscan": "disabled",
    "mupen64plus-FrameDuping": "False",
    "mupen64plus-Framerate": "Original",
    "mupen64plus-virefresh": "Auto",
    "mupen64plus-ForceDisableExtraMem": "False",
    "mupen64plus-IgnoreTLBExceptions": "False",
    "mupen64plus-CountPerOp": "0",
    "mupen64plus-CountPerOpDenomPot": "0",
}
EXPECTED_RUNTIME_PROFILE_MARKER = "Starting R4300 emulator: Pure Interpreter"
FORBIDDEN_RUNTIME_PROFILE_MARKERS = {
    "Starting R4300 emulator: Cached Interpreter": "cached interpreter",
    "parallel-RDP": "ParaLLEl-RDP",
    "Using 8x upscaling!": "8x RDP upscaling",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def find_program(explicit: str | None, default: Path, name: str) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
    elif default.is_file():
        path = default.resolve()
    else:
        found = shutil.which(name)
        if not found:
            raise FileNotFoundError(f"cannot find {name}; pass --{name.replace('_', '-')}")
        path = Path(found).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def validate_acquisition_rom_identity(rom: Path, allow_pregranted_mask: bool = False) -> None:
    """Prevent a pre-granted-mask build from impersonating the canonical Peach test."""
    name = rom.name.lower()
    if ("laundry-pool" in name and "nomask" not in name and
            not allow_pregranted_mask):
        raise ValueError(
            "refusing pre-granted Laundry Pool ROM: Peach is intentionally absent when the "
            "Brother's Mask is already owned; use a *-nomask-debug*.z64 acquisition build "
            "or pass --allow-pregranted-mask for a non-acquisition test")


def validate_debug_rom(rom: Path, allow_pregranted_mask: bool = False) -> tuple[Path, Path | None]:
    rom = rom.expanduser().resolve()
    if not rom.is_file():
        raise FileNotFoundError(rom)
    if not (rom.name.endswith("-debug.z64") or "-debug-dbg" in rom.name):
        raise ValueError("refusing non-debug ROM: filename must contain a debug build suffix")
    validate_acquisition_rom_identity(rom, allow_pregranted_mask)
    symbols = Path(str(rom) + ".va")
    if not symbols.is_file():
        raise ValueError(f"debug symbol sidecar is missing: {symbols}")
    names = {line.partition("=")[0] for line in symbols.read_text().splitlines() if "=" in line}
    required = {"gDsceFhRing", "gDsceFhHead"}
    if not required.issubset(names):
        raise ValueError(
            f"{symbols} has no enabled firehose group ({', '.join(sorted(required))} missing); "
            "play this ROM directly or rebuild with DBG_AUDIO=1 or DBG_GAMEPLAY=1")
    map_path = Path(str(rom) + ".map")
    return symbols, map_path if map_path.is_file() else None


def reserve_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def config_quote(value: Path | str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def write_core_options(path: Path) -> None:
    path.write_text("\n".join(
        f'{key} = "{value}"' for key, value in ACCURACY_CORE_OPTIONS.items()
    ) + "\n", encoding="utf-8")


def validate_core_profile(core: Path) -> None:
    core_bytes = core.read_bytes()
    missing = [key for key in ACCURACY_CORE_OPTIONS if key.encode("ascii") not in core_bytes]
    if missing:
        raise ValueError(
            f"installed core does not expose the canonical accuracy profile: {', '.join(missing)}")


def write_config(path: Path, port: int, core_options: Path) -> None:
    lines = [
        'network_cmd_enable = "true"',
        f'network_cmd_port = "{port}"',
        f'core_options_path = "{config_quote(core_options)}"',
        # Without this, modern RetroArch ignores core_options_path and loads its
        # per-core Mupen64Plus-Next.opt file instead.
        'global_core_options = "true"',
        'auto_overrides_enable = "false"',
        'game_specific_options = "false"',
        'log_to_file = "false"',
        'log_verbosity = "true"',
        'pause_nonactive = "false"',
        'audio_sync = "true"',
        'video_vsync = "true"',
        'video_threaded = "false"',
        'video_shader_enable = "false"',
        'rewind_enable = "false"',
        'run_ahead_enabled = "false"',
        'preemptive_frames_enable = "false"',
    ]
    if platform.system() == "Darwin":
        lines.extend(['video_driver = "metal"', 'input_joypad_driver = "mfi"'])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def runtime_profile_status(log_path: Path) -> tuple[str, str | None]:
    """Verify resolved core behaviour, not merely the options file we requested."""
    log = log_path.read_text(encoding="utf-8", errors="replace")
    for marker, description in FORBIDDEN_RUNTIME_PROFILE_MARKERS.items():
        if marker in log:
            return "rejected", f"core started with {description}: {marker}"
    if EXPECTED_RUNTIME_PROFILE_MARKER in log:
        return "verified", None
    return "pending", None


def command(port: int, text: str, response: bool = False) -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if response:
            sock.settimeout(1.0)
        sock.sendto(text.encode("ascii"), ("127.0.0.1", port))
        if response:
            return sock.recvfrom(4096)[0].decode("utf-8", errors="replace")
        return None
    finally:
        sock.close()


def read_core_memory(port: int, address: int, size: int) -> bytes:
    """Use RetroArch's read-only command; this never writes core or frontend state."""
    reply = command(port, f"READ_CORE_MEMORY {address:x} {size}", response=True)
    if not reply:
        raise RuntimeError("no READ_CORE_MEMORY response")
    parts = reply.strip().split()
    if len(parts) < 3 or parts[0] != "READ_CORE_MEMORY":
        raise RuntimeError(f"malformed READ_CORE_MEMORY response: {reply[:160]}")
    if parts[2] == "-1":
        raise RuntimeError(" ".join(parts[2:]))
    data = bytes(int(value, 16) for value in parts[2:])
    if len(data) != size:
        raise RuntimeError(f"READ_CORE_MEMORY returned {len(data)} of {size} bytes")
    return data


def read_symbol_addresses(path: Path) -> dict[str, int]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep:
            values[name] = int(value, 16)
    return values


def write_merged(path: Path, records: dict[int, dict]) -> int:
    temporary = path.with_suffix(path.suffix + ".tmp")
    previous = None
    drops = 0
    with temporary.open("w", encoding="utf-8") as dest:
        for seq in sorted(records):
            if previous is not None and seq > previous + 1:
                gap = seq - previous - 1
                drops += gap
                dest.write(json.dumps({"drop": gap, "after_seq": previous}) + "\n")
            dest.write(json.dumps(records[seq], separators=(",", ":")) + "\n")
            previous = seq
    temporary.replace(path)
    return drops


def append_jsonl(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as dest:
        dest.write(json.dumps(value, sort_keys=True) + "\n")


def make_tree(parent: Path) -> tuple[Path, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run = parent / stamp
    counter = 1
    while run.exists():
        run = parent / f"{stamp}-{counter:02d}"
        counter += 1
    for rel in (
        "config", "database/clickhouse", "firehose/captures", "sequence-flight/captures", "logs",
        "reports", "symbols",
    ):
        (run / rel).mkdir(parents=True, exist_ok=False)
    return run, run.name.replace("-", "").replace(":", "")


def capture(run: Path, symbols: Path, port: int, number: int,
            records: dict[int, dict], flight_records: dict[int, dict]) -> tuple[bool, bool]:
    """Drain both ROM rings through read-only core memory, with no savestate cycle."""
    try:
        addresses = read_symbol_addresses(symbols)
        ring_address = addresses["gDsceFhRing"]
        head_address = addresses["gDsceFhHead"]
        head_before = struct.unpack("<I", read_core_memory(port, head_address, 4))[0]
        ring = bytearray()
        ring_bytes = FH_RECORD_SIZE * FH_RING_RECORDS
        for offset in range(0, ring_bytes, MEMORY_READ_CHUNK):
            amount = min(MEMORY_READ_CHUNK, ring_bytes - offset)
            ring.extend(read_core_memory(port, ring_address + offset, amount))
        head_after = struct.unpack("<I", read_core_memory(port, head_address, 4))[0]
        has_flight = {
            "gDsceSeqFlightRing", "gDsceSeqFlightHead", "gDsceSeqFlightFrozen"
        }.issubset(addresses)
        flight_ring = bytearray()
        flight_head_before = 0
        flight_head_after = 0
        flight_frozen = 0
        if has_flight:
            flight_ring_address = addresses["gDsceSeqFlightRing"]
            flight_head_address = addresses["gDsceSeqFlightHead"]
            flight_frozen_address = addresses["gDsceSeqFlightFrozen"]
            flight_head_before = struct.unpack(
                "<I", read_core_memory(port, flight_head_address, 4))[0]
            flight_ring_bytes = SEQ_FLIGHT_RECORD_SIZE * SEQ_FLIGHT_RING_RECORDS
            for offset in range(0, flight_ring_bytes, MEMORY_READ_CHUNK):
                amount = min(MEMORY_READ_CHUNK, flight_ring_bytes - offset)
                flight_ring.extend(read_core_memory(port, flight_ring_address + offset, amount))
            flight_head_after = struct.unpack(
                "<I", read_core_memory(port, flight_head_address, 4))[0]
            flight_frozen = struct.unpack(
                "<I", read_core_memory(port, flight_frozen_address, 4))[0]
    except (OSError, socket.timeout, RuntimeError, KeyError, ValueError) as exc:
        append_jsonl(run / "logs" / "capture.jsonl", {
            "at": utc_now(), "capture": number, "status": "memory-read-error", "error": str(exc)})
        return False, False

    newest = head_after
    oldest = max(0, newest - FH_RING_RECORDS)
    captured_records = {}
    for slot in range(FH_RING_RECORDS):
        offset = slot * FH_RECORD_SIZE
        seq, dft, tick, frame, a, b, c, d = struct.unpack_from("<IIIIiiii", ring, offset)
        domain = (dft >> 24) & 0xFF
        if oldest <= seq < newest and domain <= 7:
            captured_records[seq] = {
                "seq": seq, "domain": domain, "tag": dft & 0xFFFF,
                "tick": tick, "frame": frame, "a": a, "b": b, "c": c, "d": d,
            }

    spool = run / "firehose" / "captures" / f"{number:06d}.fh.jsonl"
    with spool.open("w", encoding="utf-8") as destination:
        for seq in sorted(captured_records):
            destination.write(json.dumps(captured_records[seq], separators=(",", ":")) + "\n")
    added = 0
    for seq, row in captured_records.items():
        if seq not in records:
            added += 1
        records[seq] = row
    drops = write_merged(run / "firehose" / "session.fh.jsonl", records)

    flight_oldest = max(0, flight_head_after - SEQ_FLIGHT_RING_RECORDS)
    captured_flight = {}
    for slot in range(SEQ_FLIGHT_RING_RECORDS if has_flight else 0):
        offset = slot * SEQ_FLIGHT_RECORD_SIZE
        event_seq, task, frame, meta, pc, seq_data, a, b = struct.unpack_from(
            "<IIIIIIii", flight_ring, offset)
        kind = (meta >> 24) & 0xFF
        if flight_oldest <= event_seq < flight_head_after and 1 <= kind <= 8:
            player = (meta >> 16) & 0xFF
            channel = (meta >> 8) & 0xFF
            captured_flight[event_seq] = {
                "seq": event_seq, "task": task, "frame": frame, "kind": kind,
                "player": -1 if player == 0xFF else player,
                "channel": -1 if channel == 0xFF else channel,
                "opcode": meta & 0xFF, "pc": pc, "seq_data": seq_data,
                "a": a, "b": b,
            }
    flight_spool = run / "sequence-flight" / "captures" / f"{number:06d}.jsonl"
    with flight_spool.open("w", encoding="utf-8") as destination:
        for event_seq in sorted(captured_flight):
            destination.write(json.dumps(captured_flight[event_seq], separators=(",", ":")) + "\n")
    flight_added = 0
    for event_seq, row in captured_flight.items():
        if event_seq not in flight_records:
            flight_added += 1
        flight_records[event_seq] = row
    flight_drops = write_merged(run / "sequence-flight" / "session.jsonl", flight_records)
    append_jsonl(run / "logs" / "capture.jsonl", {
        "at": utc_now(), "capture": number, "status": "ok", "capture_method": "read-core-memory",
        "head_before": head_before, "head_after": head_after, "events_in_ring": len(captured_records),
        "new_events": added, "merged_events": len(records), "detected_gaps": drops,
        "flight_head_before": flight_head_before, "flight_head_after": flight_head_after,
        "flight_frozen": bool(flight_frozen), "flight_events_in_ring": len(captured_flight),
        "flight_new_events": flight_added, "flight_merged_events": len(flight_records),
        "flight_detected_gaps": flight_drops})
    return bool(captured_records or captured_flight), bool(flight_frozen)


def finalize(run: Path, rom: Path, run_id: str, notes: str, records: dict[int, dict],
             flight_records: dict[int, dict], exit_code: int | None, stop_reason: str, launcher_terminated: bool,
             observation: str) -> bool:
    if not records:
        (run / "reports" / "diagnosis.txt").write_text(
            "DSCE debug diagnosis: INCOMPLETE\nNo firehose records were captured.\n", encoding="utf-8")
        return False
    spool = run / "firehose" / "session.fh.jsonl"
    db = run / "database" / "clickhouse"
    ingest = subprocess.run(
        [sys.executable, str(TOOLS / "firehose_ingest.py"), str(spool), "--rom", str(rom),
         "--seq-flight", str(run / "sequence-flight" / "session.jsonl"),
         "--notes", notes, "--scenario", "laundry-healing", "--db", str(db),
         "--run-id", run_id], capture_output=True, text=True,
    )
    (run / "logs" / "ingest.log").write_text(ingest.stdout + ingest.stderr, encoding="utf-8")
    if ingest.returncode:
        (run / "reports" / "diagnosis.txt").write_text(
            f"DSCE debug diagnosis: INGEST FAILED\nSee {run / 'logs' / 'ingest.log'}\n", encoding="utf-8")
        return False
    diagnosis = subprocess.run(
        [sys.executable, str(TOOLS / "firehose_diagnose.py"), "--db", str(db),
         "--run-id", run_id, "--out-dir", str(run / "reports"),
         "--retroarch-log", str(run / "logs" / "retroarch.log"),
         "--map", str(next((run / "symbols").glob("*.map"))),
         "--termination-reason", stop_reason,
         "--retroarch-exit-code", str(exit_code if exit_code is not None else 0),
         "--observation", observation]
        + (["--launcher-terminated"] if launcher_terminated else []),
        capture_output=True, text=True,
    )
    (run / "logs" / "diagnose.log").write_text(
        diagnosis.stdout + diagnosis.stderr, encoding="utf-8")
    return diagnosis.returncode == 0


def stop_handler(_signum, _frame) -> None:
    global STOP
    STOP = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="?", default=str(DEFAULT_ROM))
    parser.add_argument("--retroarch")
    parser.add_argument("--core")
    parser.add_argument("--runs-dir", default=str(ROOT / "out" / "debug-runs"))
    parser.add_argument("--interval", type=float, default=1.0,
                        help="seconds between telemetry snapshots (default: 1)")
    parser.add_argument("--notes", default="canonical Laundry Pool mask acquisition test")
    parser.add_argument("--observation", default="", help="audible/visual symptom observed during this run")
    parser.add_argument("--allow-pregranted-mask", action="store_true",
                        help="allow a Laundry Pool debug ROM that intentionally suppresses Peach")
    parser.add_argument("--check", action="store_true", help="validate dependencies without launching")
    parser.add_argument("--duration", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.interval < 0.5:
        parser.error("--interval must be at least 0.5 seconds")

    rom = Path(args.rom)
    symbols, map_path = validate_debug_rom(rom, args.allow_pregranted_mask)
    symbol_addresses = read_symbol_addresses(symbols)
    rom = rom.expanduser().resolve()
    retroarch = find_program(args.retroarch, DEFAULT_RETROARCH, "retroarch")
    core = Path(args.core).expanduser().resolve() if args.core else DEFAULT_CORE.resolve()
    if not core.is_file():
        raise FileNotFoundError(f"cannot find Mupen64Plus-Next core; pass --core: {core}")
    validate_core_profile(core)
    if not shutil.which("clickhouse"):
        raise FileNotFoundError("clickhouse is required for debug-run databases")
    if args.check:
        options = "\n".join(f"  {key}={value}" for key, value in ACCURACY_CORE_OPTIONS.items())
        print(f"debug ROM: {rom}\nsymbols: {symbols}\nRetroArch: {retroarch}"
              f"\ncore: {core}\ncore sha256: {digest(core)}"
              f"\naccuracy profile: {ACCURACY_PROFILE_NAME}\n{options}"
              f"\nclickhouse: {shutil.which('clickhouse')}")
        return 0

    run, run_id = make_tree(Path(args.runs_dir).expanduser().resolve())
    shutil.copy2(symbols, run / "symbols" / symbols.name)
    if map_path:
        shutil.copy2(map_path, run / "symbols" / map_path.name)
    port = reserve_udp_port()
    config = run / "config" / "retroarch-debug.cfg"
    core_options = run / "config" / "core-options.opt"
    write_core_options(core_options)
    write_config(config, port, core_options)
    metadata = {
        "schema": 1, "run_id": run_id, "started_at": utc_now(), "finished_at": None,
        "status": "starting", "rom": str(rom), "rom_sha256": digest(rom),
        "symbols": symbols.name, "symbol_sha256": digest(symbols),
        "retroarch": str(retroarch), "retroarch_sha256": digest(retroarch),
        "core": str(core), "core_sha256": digest(core),
        "accuracy_profile": ACCURACY_PROFILE_NAME,
        "accuracy_profile_status": "pending",
        "accuracy_core_options": ACCURACY_CORE_OPTIONS,
        "debug_log_modules": {
            "legacy": {"gDsceLogRing", "gDsceLogHead"}.issubset(symbol_addresses),
            "firehose": {"gDsceFhRing", "gDsceFhHead"}.issubset(symbol_addresses),
            "audio_flight": {
                "gDsceSeqFlightRing", "gDsceSeqFlightHead", "gDsceSeqFlightFrozen"
            }.issubset(symbol_addresses),
        },
        "capture_interval_seconds": args.interval,
        "command_port": port, "notes": args.notes, "user_observation": args.observation,
        "capture_method": "read-core-memory", "captures": 0, "events": 0,
    }
    metadata_path = run / "run.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    argv = [str(retroarch), "--verbose", "--appendconfig", str(config), "-L", str(core), str(rom)]
    (run / "config" / "command.json").write_text(json.dumps(argv, indent=2) + "\n", encoding="utf-8")
    print(f"debug run: {run}")
    print("Close RetroArch when finished; capture and diagnosis will finalize automatically.")

    records: dict[int, dict] = {}
    flight_records: dict[int, dict] = {}
    capture_number = 0
    fault_announced = False
    profile_status = "pending"
    profile_error = None
    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    with (run / "logs" / "retroarch.log").open("w", encoding="utf-8") as frontend_log:
        process = subprocess.Popen(argv, stdout=frontend_log, stderr=subprocess.STDOUT)
        metadata["status"] = "running"
        metadata["pid"] = process.pid
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        next_capture = time.monotonic() + args.interval
        deadline = time.monotonic() + args.duration if args.duration else None
        while process.poll() is None and not STOP and (deadline is None or time.monotonic() < deadline):
            profile_status, profile_error = runtime_profile_status(run / "logs" / "retroarch.log")
            if profile_status == "rejected":
                print(f"Accuracy profile rejected: {profile_error}")
                break
            if profile_status == "verified" and metadata["accuracy_profile_status"] != "verified":
                metadata["accuracy_profile_status"] = "verified"
                metadata_path.write_text(
                    json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            try:
                status = command(port, "GET_STATUS", response=True)
            except (OSError, socket.timeout):
                status = None
            now = time.monotonic()
            if status and " PLAYING " in status and now >= next_capture:
                capture_number += 1
                _, frozen = capture(run, symbols, port, capture_number, records, flight_records)
                if frozen and not fault_announced:
                    print("Sequence fault and its causal history are captured; you can close RetroArch now.")
                    fault_announced = True
                next_capture = time.monotonic() + args.interval
            time.sleep(0.25)
        stop_reason = "retroarch-exited"
        launcher_terminated = False
        if process.poll() is None:
            if profile_status == "rejected":
                stop_reason = "accuracy-profile-rejected"
            else:
                stop_reason = "signal" if STOP else "duration-limit"
            capture_number += 1
            capture(run, symbols, port, capture_number, records, flight_records)
            try:
                command(port, "QUIT")
            except OSError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
                launcher_terminated = True
        exit_code = process.poll()

    if profile_status == "pending":
        profile_status, profile_error = runtime_profile_status(run / "logs" / "retroarch.log")
    okay = finalize(run, rom, run_id, args.notes, records, flight_records, exit_code,
                    stop_reason, launcher_terminated, args.observation)
    if profile_status != "verified":
        okay = False
        if profile_error is None:
            profile_error = "core never emitted the Pure Interpreter startup marker"
    diagnosis_path = run / "reports" / "diagnosis.json"
    diagnosis_status = None
    if diagnosis_path.is_file():
        diagnosis_status = json.loads(diagnosis_path.read_text(encoding="utf-8")).get("status")
    metadata.update({
        "finished_at": utc_now(), "status": "complete" if okay else "incomplete",
        "captures": capture_number, "events": len(records), "sequence_flight_events": len(flight_records),
        "retroarch_exit_code": exit_code,
        "termination_reason": stop_reason, "launcher_terminated_emulator": launcher_terminated,
        "diagnosis_status": diagnosis_status,
        "accuracy_profile_status": profile_status,
        "accuracy_profile_error": profile_error,
    })
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"diagnosis: {run / 'reports' / 'diagnosis.txt'}")
    print(f"ClickHouse: {run / 'database' / 'clickhouse'}")
    return 0 if okay else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"error: {exc}")
