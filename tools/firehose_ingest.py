#!/usr/bin/env python3
"""Ingest a DSCE firehose spool into the tagged ClickHouse ontology.

One run = one row in `runs` + typed rows in per-domain tables, all keyed by run_id.
Database defaults to out/firehose/clickhouse (clickhouse local --path); ``--db`` can
instead isolate it inside a timestamped debug-run directory. Domains (must match
dsce_hook.c):
  0 legacy (Dsce_Log mirror)   1 audio.request   2 audio.seqplayer
  3 audio.heap                 4 audio.pipeline  5 kernel.action   6 kernel.sound
  7 quest.rite

Usage: firehose_ingest.py <spool.fh.jsonl> --rom <rom> [--notes "..."] [--scenario file]
"""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBPATH = os.path.join(HERE, "out", "firehose", "clickhouse")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id String, ts DateTime, rom String, rev String, notes String,
    scenario String, events UInt64, drops UInt64
) ENGINE = MergeTree ORDER BY (run_id);
CREATE TABLE IF NOT EXISTS audio_requests (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    sfx_id UInt16, pos UInt32, token UInt8
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS seqplayer_state (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    flags UInt8, fonts_player UInt32, fonts_voice UInt32,
    chan_enabled UInt8, active_notes UInt8, notes_font41 UInt8
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS heap_levels (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    permanent_used Int32, permanent_size Int32, cache_used Int32, cache_size Int32
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS audio_pipeline (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    sample_type UInt16, a Int32, b Int32, c Int32, d Int32
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS kernel_actions (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    action UInt32, prev_action UInt32, forward_vel Int32
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS kernel_sounds (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    key UInt16, na_se UInt16, miss UInt8
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS legacy_log (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    tag2 UInt16, a Int32, b Int32, c Int32, d Int32
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS quest_rite (
    run_id String, seq UInt32, tick UInt32, frame UInt32,
    sample_type UInt16, a Int32, b Int32, c Int32, d Int32
) ENGINE = MergeTree ORDER BY (run_id, seq);
CREATE TABLE IF NOT EXISTS sequence_flight (
    run_id String, event_seq UInt32, task UInt32, frame UInt32,
    kind UInt8, player Int16, channel Int16, opcode UInt8,
    pc UInt32, seq_data UInt32, seq_offset Int64, a Int32, b Int32
) ENGINE = MergeTree ORDER BY (run_id, event_seq);
"""


def ch(dbpath, queries, input_data=None):
    cmd = ["clickhouse", "local", "--path", dbpath, "--multiquery", "--query", queries]
    return subprocess.run(cmd, input=input_data, capture_output=True, text=True, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spool")
    ap.add_argument("--rom", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--scenario", default="")
    ap.add_argument("--seq-flight", help="sequence flight-recorder JSONL from run_debug_release.py")
    ap.add_argument("--db", default=os.environ.get("DSCE_CLICKHOUSE_PATH", DBPATH),
                    help="ClickHouse local database directory")
    ap.add_argument("--run-id", help="stable run id (default: spool content hash)")
    args = ap.parse_args()

    dbpath = os.path.abspath(args.db)
    os.makedirs(dbpath, exist_ok=True)
    run_id = args.run_id or hashlib.sha1(open(args.spool, "rb").read()).hexdigest()[:12]
    rev = subprocess.run(["git", "-C", HERE, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    rows = {k: [] for k in ("audio_requests", "seqplayer_state", "heap_levels", "audio_pipeline",
                            "kernel_actions", "kernel_sounds", "quest_rite", "legacy_log")}
    events = drops = 0
    for line in open(args.spool):
        r = json.loads(line)
        if "drop" in r:
            drops += r["drop"]
            continue
        events += 1
        base = (run_id, r["seq"], r["tick"], r["frame"])
        d = r["domain"]
        if d == 1:
            rows["audio_requests"].append(base + (r["a"] & 0xFFFF, r["b"] & 0xFFFFFFFF, r["c"] & 0xFF))
        elif d == 2:
            rows["seqplayer_state"].append(base + (r["a"] & 0xFF, r["b"] & 0xFFFFFFFF,
                                                   r["c"] & 0xFFFFFFFF, r["d"] & 0x3F,
                                                   (r["d"] >> 8) & 0xFF, (r["d"] >> 16) & 0xFF))
        elif d == 3:
            rows["heap_levels"].append(base + (r["a"], r["b"], r["c"], r["d"]))
        elif d == 4:
            rows["audio_pipeline"].append(base + (r["tag"], r["a"], r["b"], r["c"], r["d"]))
        elif d == 5:
            rows["kernel_actions"].append(base + (r["a"] & 0xFFFFFFFF, r["b"] & 0xFFFFFFFF, r["c"]))
        elif d == 6:
            rows["kernel_sounds"].append(base + (r["a"] & 0xFFFF, r["b"] & 0xFFFF, r["tag"] & 1))
        elif d == 7:
            rows["quest_rite"].append(base + (r["tag"], r["a"], r["b"], r["c"], r["d"]))
        else:
            rows["legacy_log"].append(base + (r["tag"], r["a"], r["b"], r["c"], r["d"]))

    ch(dbpath, SCHEMA)
    for table, data in rows.items():
        if not data:
            continue
        payload = "\n".join(json.dumps(list(row)) for row in data)
        ch(dbpath, f"INSERT INTO {table} FORMAT JSONCompactEachRow", payload)
    flight_events = 0
    if args.seq_flight and os.path.isfile(args.seq_flight):
        flight_rows = []
        for line in open(args.seq_flight):
            item = json.loads(line)
            if "drop" in item:
                continue
            flight_events += 1
            pc = item["pc"] & 0xFFFFFFFF
            seq_data = item["seq_data"] & 0xFFFFFFFF
            flight_rows.append((
                run_id, item["seq"], item["task"], item["frame"], item["kind"],
                item["player"], item["channel"], item["opcode"], pc, seq_data,
                pc - seq_data if seq_data else -1, item["a"], item["b"],
            ))
        if flight_rows:
            payload = "\n".join(json.dumps(list(row)) for row in flight_rows)
            ch(dbpath, "INSERT INTO sequence_flight FORMAT JSONCompactEachRow", payload)
    ch(dbpath, "INSERT INTO runs FORMAT JSONCompactEachRow",
       json.dumps([run_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                   os.path.basename(args.rom), rev, args.notes,
                   args.scenario, events, drops]))
    print(f"run {run_id}: {events} firehose events ({drops} drops), "
          f"{flight_events} sequence-flight events -> {dbpath}")
    print(f"  query: tools/firehose_query --db {dbpath} last-audio {run_id}")


if __name__ == "__main__":
    main()
