#!/usr/bin/env python3
"""Generate a machine-readable and human-readable DSCE run diagnosis."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def query(db: Path, sql: str) -> dict:
    result = subprocess.run(
        ["clickhouse", "local", "--path", str(db), "--query", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def query_rows(db: Path, sql: str) -> list[dict]:
    result = subprocess.run(
        ["clickhouse", "local", "--path", str(db), "--query", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def frontend_evidence(path: Path | None) -> tuple[list[str], bool]:
    if not path or not path.is_file():
        return [], False
    text = path.read_text(errors="replace")
    interesting = re.compile(
        r"(audio|coreaudio|fast.?forward|throttl|underrun|overrun|buffer).*(warn|error|fail|stall|drop)|"
        r"(warn|error|fail|stall|drop).*(audio|coreaudio|buffer)|"
        r"mutex lock failed|memory leaked in class allocator",
        re.IGNORECASE,
    )
    evidence = [line.strip() for line in text.splitlines() if interesting.search(line)][-100:]
    shutdown_abort = ("Restored video driver" in text and "mutex lock failed" in text)
    return evidence, shutdown_abort


def resolve_symbol(path: Path | None, address: int) -> str:
    if not path or not path.is_file() or not address:
        return "unresolved"
    address &= 0xFFFFFFFF
    best_addr = -1
    best_name = "unresolved"
    symbol = re.compile(r"^\s*0x([0-9a-fA-F]+)\s+([A-Za-z_.$][A-Za-z0-9_.$]*)\s*$")
    for line in path.read_text(errors="replace").splitlines():
        match = symbol.match(line)
        if match:
            candidate = int(match.group(1), 16) & 0xFFFFFFFF
            if candidate <= address and candidate > best_addr:
                best_addr = candidate
                best_name = match.group(2)
    return f"{best_name}+0x{address - best_addr:X}" if best_addr >= 0 else "unresolved"


def sequence_span_from_map(path: Path | None) -> tuple[int, int, str]:
    """Return advertised Sequence_0 end and the object's last data byte."""
    if not path or not path.is_file():
        return 0, 0, ""
    end = 0
    dsce_addr = 0
    dsce_name = ""
    symbol = re.compile(r"^\s*0x([0-9a-fA-F]+)\s+([A-Za-z_.$][A-Za-z0-9_.$]*)\s*$")
    seq_object = re.compile(
        r"^\s*\.data\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+.*seq_0\.prg\.o\s*$"
    )
    for line in path.read_text(errors="replace").splitlines():
        object_match = seq_object.match(line)
        if object_match:
            start = int(object_match.group(1), 16)
            size = int(object_match.group(2), 16)
            dsce_addr = start + size - 1
            dsce_name = "seq_0.prg.o .data"
        match = symbol.match(line)
        if not match:
            continue
        address = int(match.group(1), 16)
        name = match.group(2)
        if name == "Sequence_0_End":
            end = address
        elif (name.startswith("CHAN_PL_DSCE_") or name.startswith("CHAN_VO_DSCE_")
              or name.startswith("LAYER_DSCE_")) and address >= dsce_addr:
            dsce_addr = address
            dsce_name = name
    return end, dsce_addr, dsce_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--retroarch-log", type=Path)
    parser.add_argument("--map", type=Path, help="linker map used to resolve saved N64 thread PCs")
    parser.add_argument("--retroarch-exit-code", type=int, default=0)
    parser.add_argument("--termination-reason", default="unknown")
    parser.add_argument("--launcher-terminated", action="store_true")
    parser.add_argument("--observation", default="", help="user-observed symptom for evidence correlation")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", args.run_id):
        parser.error("run id contains unsupported characters")

    run = args.run_id
    sql = f"""
    SELECT
      (SELECT max(events) FROM runs WHERE run_id='{run}') AS events,
      (SELECT max(drops) FROM runs WHERE run_id='{run}') AS drops,
      (SELECT count() FROM audio_requests WHERE run_id='{run}') AS request_count,
      (SELECT max(frame) FROM audio_requests WHERE run_id='{run}') AS last_request_frame,
      (SELECT count() FROM seqplayer_state WHERE run_id='{run}') AS seq_samples,
      (SELECT max(frame) FROM seqplayer_state WHERE run_id='{run}') AS last_seq_frame,
      (SELECT maxIf(frame, active_notes > 0) FROM seqplayer_state WHERE run_id='{run}') AS last_active_note_frame,
      (SELECT max(active_notes) FROM seqplayer_state WHERE run_id='{run}') AS peak_active_notes,
      (SELECT max(notes_font41) FROM seqplayer_state WHERE run_id='{run}') AS peak_font41_notes,
      (SELECT countIf(notes_font41 > 0) FROM seqplayer_state WHERE run_id='{run}') AS font41_live_samples,
      (SELECT countIf(flags != 2 AND frame + 60 >= (SELECT max(frame) FROM seqplayer_state WHERE run_id='{run}'))
         FROM seqplayer_state WHERE run_id='{run}') AS unhealthy_seq_tail_samples,
      (SELECT countIf(miss = 0) FROM kernel_sounds WHERE run_id='{run}') AS kernel_sound_hits,
      (SELECT countIf(miss != 0) FROM kernel_sounds WHERE run_id='{run}') AS kernel_sound_misses,
      (SELECT count() FROM kernel_actions WHERE run_id='{run}') AS action_changes,
      (SELECT max(permanent_used) FROM heap_levels WHERE run_id='{run}') AS permanent_highwater,
      (SELECT max(permanent_size) FROM heap_levels WHERE run_id='{run}') AS permanent_size,
      (SELECT max(cache_used) FROM heap_levels WHERE run_id='{run}') AS cache_highwater,
      (SELECT max(cache_size) FROM heap_levels WHERE run_id='{run}') AS cache_size,
      (SELECT countIf(sample_type = 0) FROM audio_pipeline WHERE run_id='{run}') AS pipeline_samples,
      (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}') AS last_pipeline_frame,
      (SELECT maxIf(frame, sample_type = 2 AND d > 0) FROM audio_pipeline WHERE run_id='{run}') AS last_nonzero_pcm_frame,
      (SELECT countIf(sample_type = 2 AND d > 0) FROM audio_pipeline WHERE run_id='{run}') AS nonzero_pcm_samples,
      (SELECT argMaxIf(a, frame, sample_type = 0) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_task_count,
      (SELECT maxIf(a, sample_type = 0 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}')) -
              minIf(a, sample_type = 0 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}'))
         FROM audio_pipeline WHERE run_id='{run}') AS audio_task_tail_delta,
      (SELECT maxIf(c, sample_type = 0) FROM audio_pipeline WHERE run_id='{run}') AS max_ai_dma_length,
      (SELECT countIf(sample_type = 0 AND bitAnd(toUInt32(d), 2147483648) != 0 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}'))
         FROM audio_pipeline WHERE run_id='{run}') AS ai_fifo_full_tail_samples,
      (SELECT countIf(sample_type = 0 AND bitAnd(toUInt32(d), 1073741824) != 0 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}'))
         FROM audio_pipeline WHERE run_id='{run}') AS ai_dma_busy_tail_samples,
      (SELECT argMaxIf(a, seq, sample_type = 4) FROM audio_pipeline WHERE run_id='{run}') AS ai_submit_attempts,
      (SELECT argMaxIf(b, seq, sample_type = 4) FROM audio_pipeline WHERE run_id='{run}') AS ai_submit_failures,
      (SELECT argMaxIf(c, seq, sample_type = 4) FROM audio_pipeline WHERE run_id='{run}') AS ai_submit_successes,
      (SELECT argMaxIf(d, seq, sample_type = 4) FROM audio_pipeline WHERE run_id='{run}') AS ai_submit_last_result,
      (SELECT bitAnd(bitShiftRight(toUInt32(argMaxIf(b, seq, sample_type = 0)), 8), 255)
         FROM audio_pipeline WHERE run_id='{run}') AS last_audio_mgr_cmd_queue,
      (SELECT bitAnd(bitShiftRight(toUInt32(argMaxIf(b, seq, sample_type = 0)), 16), 255)
         FROM audio_pipeline WHERE run_id='{run}') AS last_audio_mgr_interrupt_queue,
      (SELECT argMaxIf(a, seq, sample_type = 3) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_mgr_rsp_task,
      (SELECT argMaxIf(b, seq, sample_type = 3) FROM audio_pipeline WHERE run_id='{run}') AS last_scheduler_rsp_task,
      (SELECT argMaxIf(c, seq, sample_type = 3) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_sc_task_state,
      (SELECT argMaxIf(a, seq, sample_type = 6) FROM audio_pipeline WHERE run_id='{run}') AS audio_mgr_timeouts,
      (SELECT argMaxIf(b, seq, sample_type = 6) FROM audio_pipeline WHERE run_id='{run}') AS audio_mgr_successes,
      (SELECT argMaxIf(c, seq, sample_type = 6) FROM audio_pipeline WHERE run_id='{run}') AS audio_mgr_exhausted_bursts,
      (SELECT bitAnd(toUInt32(argMaxIf(d, seq, sample_type = 6)), 65535)
         FROM audio_pipeline WHERE run_id='{run}') AS audio_mgr_consecutive_timeouts,
      (SELECT bitShiftRight(toUInt32(argMaxIf(d, seq, sample_type = 6)), 16)
         FROM audio_pipeline WHERE run_id='{run}') AS audio_mgr_max_consecutive_timeouts,
      (SELECT argMaxIf(a, seq, sample_type = 7) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_update_phase,
      (SELECT argMaxIf(b, seq, sample_type = 7) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_update_phase_a,
      (SELECT argMaxIf(c, seq, sample_type = 7) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_update_phase_b,
      (SELECT argMaxIf(d, seq, sample_type = 7) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_update_phase_task,
      (SELECT argMaxIf(a, seq, sample_type = 8) FROM audio_pipeline WHERE run_id='{run}') AS audio_dma_submits,
      (SELECT argMaxIf(b, seq, sample_type = 8) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_dma_dev_addr,
      (SELECT argMaxIf(c, seq, sample_type = 8) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_dma_size,
      (SELECT argMaxIf(d, seq, sample_type = 8) FROM audio_pipeline WHERE run_id='{run}') AS last_audio_dma_queue,
      (SELECT argMaxIf(a, seq, sample_type = 9) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_stage,
      (SELECT argMaxIf(b, seq, sample_type = 9) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_note,
      (SELECT argMaxIf(c, seq, sample_type = 9) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_update,
      (SELECT argMaxIf(d, seq, sample_type = 9) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_part,
      (SELECT argMaxIf(a, seq, sample_type = 10) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_sample_addr,
      (SELECT argMaxIf(b, seq, sample_type = 10) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_sample_end,
      (SELECT argMaxIf(c, seq, sample_type = 10) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_loop_start,
      (SELECT argMaxIf(d, seq, sample_type = 10) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_loop_end,
      (SELECT argMaxIf(a, seq, sample_type = 11) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_processed,
      (SELECT argMaxIf(b, seq, sample_type = 11) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_target,
      (SELECT argMaxIf(c, seq, sample_type = 11) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_sample_pos,
      (SELECT argMaxIf(d, seq, sample_type = 11) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_iteration,
      (SELECT argMaxIf(a, seq, sample_type = 12) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_codec,
      (SELECT argMaxIf(b, seq, sample_type = 12) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_medium,
      (SELECT argMaxIf(c, seq, sample_type = 12) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_frequency,
      (SELECT argMaxIf(d, seq, sample_type = 12) FROM audio_pipeline WHERE run_id='{run}') AS last_synth_samples_to_load,
      (SELECT argMaxIf(a, seq, sample_type = 13) FROM audio_pipeline WHERE run_id='{run}') AS audio_thread_pc,
      (SELECT argMaxIf(b, seq, sample_type = 13) FROM audio_pipeline WHERE run_id='{run}') AS audio_thread_sp,
      (SELECT argMaxIf(c, seq, sample_type = 13) FROM audio_pipeline WHERE run_id='{run}') AS audio_thread_ra,
      (SELECT bitShiftRight(toUInt32(argMaxIf(d, seq, sample_type = 13)), 16)
         FROM audio_pipeline WHERE run_id='{run}') AS audio_thread_state,
      (SELECT argMaxIf(a, seq, sample_type = 14) FROM audio_pipeline WHERE run_id='{run}') AS audio_fault_a0,
      (SELECT argMaxIf(b, seq, sample_type = 14) FROM audio_pipeline WHERE run_id='{run}') AS audio_fault_badvaddr,
      (SELECT argMaxIf(c, seq, sample_type = 14) FROM audio_pipeline WHERE run_id='{run}') AS audio_fault_cause,
      (SELECT bitShiftRight(toUInt32(argMaxIf(d, seq, sample_type = 14)), 16)
         FROM audio_pipeline WHERE run_id='{run}') AS audio_thread_flags,
      (SELECT argMaxIf(a, seq, sample_type = 15) FROM audio_pipeline WHERE run_id='{run}') AS last_seq_channel,
      (SELECT argMaxIf(b, seq, sample_type = 15) FROM audio_pipeline WHERE run_id='{run}') AS last_seq_layer,
      (SELECT argMaxIf(c, seq, sample_type = 15) FROM audio_pipeline WHERE run_id='{run}') AS last_seq_layer_index,
      (SELECT argMaxIf(d, seq, sample_type = 15) FROM audio_pipeline WHERE run_id='{run}') AS last_seq_font,
      (SELECT argMaxIf(a, seq, sample_type = 16) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer_count,
      (SELECT argMaxIf(b, seq, sample_type = 16) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer,
      (SELECT argMaxIf(c, seq, sample_type = 16) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer_index,
      (SELECT argMaxIf(d, seq, sample_type = 16) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_font,
      (SELECT argMaxIf(a, seq, sample_type = 17) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_channel_ptr,
      (SELECT argMaxIf(b, seq, sample_type = 17) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_player,
      (SELECT argMaxIf(c, seq, sample_type = 17) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_channel,
      (SELECT argMaxIf(d, seq, sample_type = 17) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_audio_task,
      (SELECT argMaxIf(a, seq, sample_type = 18) FROM audio_pipeline WHERE run_id='{run}') AS slow_load_calls,
      (SELECT argMaxIf(b, seq, sample_type = 18) FROM audio_pipeline WHERE run_id='{run}') AS slow_load_font,
      (SELECT argMaxIf(c, seq, sample_type = 18) FROM audio_pipeline WHERE run_id='{run}') AS slow_load_inst,
      (SELECT argMaxIf(d, seq, sample_type = 18) FROM audio_pipeline WHERE run_id='{run}') AS slow_load_sample,
      (SELECT argMaxIf(a, seq, sample_type = 19) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_count,
      (SELECT argMaxIf(b, seq, sample_type = 19) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_font,
      (SELECT argMaxIf(c, seq, sample_type = 19) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_inst,
      (SELECT argMaxIf(d, seq, sample_type = 19) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_sample,
      (SELECT argMaxIf(a, seq, sample_type = 20) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_channel_ptr,
      (SELECT argMaxIf(b, seq, sample_type = 20) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_pc,
      (SELECT argMaxIf(c, seq, sample_type = 20) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_location,
      (SELECT argMaxIf(d, seq, sample_type = 20) FROM audio_pipeline WHERE run_id='{run}') AS slow_load_is_done_ptr,
      (SELECT argMaxIf(a, seq, sample_type = 21) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_seq_data,
      (SELECT argMaxIf(b, seq, sample_type = 21) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_seq_offset,
      (SELECT argMaxIf(d, seq, sample_type = 21) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_audio_task,
      (SELECT argMaxIf(a, seq, sample_type = 22) FROM audio_pipeline WHERE run_id='{run}') AS graph_thread_pc,
      (SELECT argMaxIf(b, seq, sample_type = 22) FROM audio_pipeline WHERE run_id='{run}') AS graph_thread_sp,
      (SELECT argMaxIf(c, seq, sample_type = 22) FROM audio_pipeline WHERE run_id='{run}') AS graph_thread_ra,
      (SELECT bitShiftRight(toUInt32(argMaxIf(d, seq, sample_type = 22)), 16)
         FROM audio_pipeline WHERE run_id='{run}') AS graph_thread_state,
      (SELECT argMaxIf(a, seq, sample_type = 23) FROM audio_pipeline WHERE run_id='{run}') AS graph_fault_a0,
      (SELECT argMaxIf(b, seq, sample_type = 23) FROM audio_pipeline WHERE run_id='{run}') AS graph_fault_badvaddr,
      (SELECT argMaxIf(c, seq, sample_type = 23) FROM audio_pipeline WHERE run_id='{run}') AS graph_fault_cause,
      (SELECT bitShiftRight(toUInt32(argMaxIf(d, seq, sample_type = 23)), 16)
         FROM audio_pipeline WHERE run_id='{run}') AS graph_thread_flags,
      (SELECT argMaxIf(a, seq, sample_type = 24) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_opcode_word,
      (SELECT argMaxIf(b, seq, sample_type = 24) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_script_pc,
      (SELECT argMaxIf(c, seq, sample_type = 24) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_value,
      (SELECT argMaxIf(d, seq, sample_type = 24) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_depth,
      (SELECT argMaxIf(a, seq, sample_type = 25) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_unk22,
      (SELECT argMaxIf(b, seq, sample_type = 25) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_dyn_table,
      (SELECT argMaxIf(c, seq, sample_type = 25) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_layer0,
      (SELECT argMaxIf(d, seq, sample_type = 25) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_layer1,
      (SELECT argMaxIf(a, seq, sample_type = 26) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_layer2,
      (SELECT argMaxIf(b, seq, sample_type = 26) FROM audio_pipeline WHERE run_id='{run}') AS invalid_slow_load_layer3,
      (SELECT argMaxIf(a, seq, sample_type = 27) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_script_pc,
      (SELECT argMaxIf(b, seq, sample_type = 27) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_script_offset,
      (SELECT argMaxIf(c, seq, sample_type = 27) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_script_state,
      (SELECT argMaxIf(d, seq, sample_type = 27) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_unk22,
      (SELECT argMaxIf(a, seq, sample_type = 28) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_dyn_table,
      (SELECT argMaxIf(b, seq, sample_type = 28) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_stack0,
      (SELECT argMaxIf(c, seq, sample_type = 28) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_stack1,
      (SELECT argMaxIf(d, seq, sample_type = 28) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_stack2,
      (SELECT argMaxIf(a, seq, sample_type = 29) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_stack3,
      (SELECT argMaxIf(b, seq, sample_type = 29) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer0,
      (SELECT argMaxIf(c, seq, sample_type = 29) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer1,
      (SELECT argMaxIf(d, seq, sample_type = 29) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer2,
      (SELECT argMaxIf(a, seq, sample_type = 30) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_layer3,
      (SELECT argMaxIf(b, seq, sample_type = 30) FROM audio_pipeline WHERE run_id='{run}') AS invalid_seq_seq_data,
      (SELECT argMaxIf(a, seq, sample_type = 31) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_count,
      (SELECT argMaxIf(b, seq, sample_type = 31) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_player,
      (SELECT argMaxIf(c, seq, sample_type = 31) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_slot,
      (SELECT argMaxIf(d, seq, sample_type = 31) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_bad_ptr,
      (SELECT argMaxIf(a, seq, sample_type = 32) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_task,
      (SELECT argMaxIf(b, seq, sample_type = 32) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_seq_data,
      (SELECT argMaxIf(c, seq, sample_type = 32) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_misc_start,
      (SELECT argMaxIf(d, seq, sample_type = 32) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_misc_cur,
      (SELECT argMaxIf(a, seq, sample_type = 33) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch0,
      (SELECT argMaxIf(b, seq, sample_type = 33) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch1,
      (SELECT argMaxIf(c, seq, sample_type = 33) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch2,
      (SELECT argMaxIf(d, seq, sample_type = 33) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch3,
      (SELECT argMaxIf(a, seq, sample_type = 34) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch4,
      (SELECT argMaxIf(b, seq, sample_type = 34) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch5,
      (SELECT argMaxIf(c, seq, sample_type = 34) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch6,
      (SELECT argMaxIf(d, seq, sample_type = 34) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch7,
      (SELECT argMaxIf(a, seq, sample_type = 35) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch8,
      (SELECT argMaxIf(b, seq, sample_type = 35) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch9,
      (SELECT argMaxIf(c, seq, sample_type = 35) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch10,
      (SELECT argMaxIf(d, seq, sample_type = 35) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch11,
      (SELECT argMaxIf(a, seq, sample_type = 36) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch12,
      (SELECT argMaxIf(b, seq, sample_type = 36) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch13,
      (SELECT argMaxIf(c, seq, sample_type = 36) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch14,
      (SELECT argMaxIf(d, seq, sample_type = 36) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_ch15,
      (SELECT argMaxIf(a, seq, sample_type = 37) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_script_pc,
      (SELECT argMaxIf(b, seq, sample_type = 37) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_script_offset,
      (SELECT argMaxIf(c, seq, sample_type = 37) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_script_state,
      (SELECT argMaxIf(d, seq, sample_type = 37) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_seq_id,
      (SELECT argMaxIf(a, seq, sample_type = 38) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_stack0,
      (SELECT argMaxIf(b, seq, sample_type = 38) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_stack1,
      (SELECT argMaxIf(c, seq, sample_type = 38) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_stack2,
      (SELECT argMaxIf(d, seq, sample_type = 38) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_stack3,
      (SELECT argMaxIf(a, seq, sample_type = 39) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_source_ra,
      (SELECT argMaxIf(b, seq, sample_type = 39) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_matching_layer,
      (SELECT argMaxIf(c, seq, sample_type = 39) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_matching_layer_pc,
      (SELECT argMaxIf(d, seq, sample_type = 39) FROM audio_pipeline WHERE run_id='{run}') AS channel_ptr_corruption_matching_layer_note,
      (SELECT maxIf(a, sample_type = 4 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}')) -
              minIf(a, sample_type = 4 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}'))
         FROM audio_pipeline WHERE run_id='{run}') AS ai_submit_attempt_tail_delta,
      (SELECT maxIf(b, sample_type = 4 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}')) -
              minIf(b, sample_type = 4 AND frame + 60 >=
          (SELECT max(frame) FROM audio_pipeline WHERE run_id='{run}'))
         FROM audio_pipeline WHERE run_id='{run}') AS ai_submit_failure_tail_delta,
      (SELECT count() FROM quest_rite WHERE run_id='{run}') AS rite_samples,
      (SELECT max(frame) FROM quest_rite WHERE run_id='{run}') AS last_rite_frame,
      (SELECT argMaxIf(a, seq, sample_type = 0) FROM quest_rite WHERE run_id='{run}') AS last_ocarina_mode,
      (SELECT argMaxIf(b, seq, sample_type = 0) FROM quest_rite WHERE run_id='{run}') AS last_message_mode,
      (SELECT argMaxIf(c, seq, sample_type = 0) FROM quest_rite WHERE run_id='{run}') AS last_played_song,
      (SELECT argMaxIf(d, seq, sample_type = 0) FROM quest_rite WHERE run_id='{run}') AS last_song_latch,
      (SELECT argMaxIf(a, seq, sample_type = 1) FROM quest_rite WHERE run_id='{run}') AS last_statue_state,
      (SELECT argMaxIf(b, seq, sample_type = 1) FROM quest_rite WHERE run_id='{run}') AS last_statue_timer,
      (SELECT argMaxIf(c, seq, sample_type = 1) FROM quest_rite WHERE run_id='{run}') AS last_statue_fade_milli,
      (SELECT argMaxIf(d, seq, sample_type = 1) FROM quest_rite WHERE run_id='{run}') AS last_statue_has_parent,
      (SELECT countIf(sample_type = 2) FROM quest_rite WHERE run_id='{run}') AS rite_transitions,
      (SELECT argMaxIf(a, seq, sample_type = 2) FROM quest_rite WHERE run_id='{run}') AS last_rite_from_state,
      (SELECT argMaxIf(b, seq, sample_type = 2) FROM quest_rite WHERE run_id='{run}') AS last_rite_to_state
      ,(SELECT count() FROM sequence_flight WHERE run_id='{run}') AS sequence_flight_events
      ,(SELECT countIf(kind = 3) FROM sequence_flight WHERE run_id='{run}') AS sequence_write_events
      ,(SELECT countIf(kind = 7) FROM sequence_flight WHERE run_id='{run}') AS sequence_dma_overlap_events
      ,(SELECT countIf(kind = 4) FROM sequence_flight WHERE run_id='{run}') AS bad_stopchan_events
      ,(SELECT minIf(event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_seq
      ,(SELECT argMinIf(player, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_player
      ,(SELECT argMinIf(channel, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_channel
      ,(SELECT argMinIf(kind, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_kind
      ,(SELECT argMinIf(opcode, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_opcode
      ,(SELECT argMinIf(pc, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_pc
      ,(SELECT argMinIf(seq_data, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_seq_data
      ,(SELECT argMinIf(seq_offset, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_offset
      ,(SELECT argMinIf(a, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_a
      ,(SELECT argMinIf(b, event_seq, kind IN (4, 5, 8)) FROM sequence_flight WHERE run_id='{run}') AS first_flight_fault_b
    FORMAT JSONEachRow
    """
    metrics = query(args.db.resolve(), sql)
    flight_history = []
    if metrics["first_flight_fault_seq"] or metrics["bad_stopchan_events"]:
        history_sql = f"""
        SELECT event_seq, task, frame, kind, player, channel, opcode, pc, seq_data,
               seq_offset, a, b
        FROM sequence_flight
        WHERE run_id='{run}' AND event_seq <= {metrics['first_flight_fault_seq']}
        ORDER BY event_seq DESC
        LIMIT 128
        FORMAT JSONEachRow
        """
        flight_history = list(reversed(query_rows(args.db.resolve(), history_sql)))
    metrics["audio_thread_pc_symbol"] = resolve_symbol(args.map, metrics["audio_thread_pc"])
    metrics["audio_thread_ra_symbol"] = resolve_symbol(args.map, metrics["audio_thread_ra"])
    metrics["graph_thread_pc_symbol"] = resolve_symbol(args.map, metrics["graph_thread_pc"])
    metrics["graph_thread_ra_symbol"] = resolve_symbol(args.map, metrics["graph_thread_ra"])
    metrics["permanent_headroom"] = metrics["permanent_size"] - metrics["permanent_highwater"]
    metrics["cache_headroom"] = metrics["cache_size"] - metrics["cache_highwater"]
    slow_location = metrics["invalid_slow_load_location"] & 0xFFFFFFFF
    metrics["invalid_slow_load_player"] = (slow_location >> 24) & 0xFF
    metrics["invalid_slow_load_channel"] = (slow_location >> 16) & 0xFF
    metrics["invalid_slow_load_port"] = slow_location & 0xFFFF
    metrics["invalid_slow_load_opcode"] = (
        (metrics["invalid_slow_load_opcode_word"] & 0xFFFFFFFF) >> 24)
    invalid_seq_state = metrics["invalid_seq_script_state"] & 0xFFFFFFFF
    metrics["invalid_seq_depth"] = (invalid_seq_state >> 16) & 0xFFFF
    metrics["invalid_seq_value"] = invalid_seq_state & 0xFFFF
    if metrics["invalid_seq_value"] & 0x8000:
        metrics["invalid_seq_value"] -= 0x10000
    if metrics["invalid_slow_load_player"] == 0xFF:
        metrics["invalid_slow_load_player"] = -1
    if metrics["invalid_slow_load_channel"] == 0xFF:
        metrics["invalid_slow_load_channel"] = -1
    channel_ptr_state = metrics["channel_ptr_corruption_script_state"] & 0xFFFFFFFF
    metrics["channel_ptr_corruption_depth"] = (channel_ptr_state >> 16) & 0xFFFF
    metrics["channel_ptr_corruption_value"] = channel_ptr_state & 0xFFFF
    if metrics["channel_ptr_corruption_value"] & 0x8000:
        metrics["channel_ptr_corruption_value"] -= 0x10000
    sequence_end, dsce_last, dsce_last_name = sequence_span_from_map(args.map)
    metrics["sequence_0_advertised_end"] = sequence_end
    metrics["sequence_0_last_dsce_symbol"] = dsce_last
    metrics["sequence_0_last_dsce_symbol_name"] = dsce_last_name
    metrics["sequence_0_excluded_dsce_bytes"] = max(0, dsce_last + 1 - sequence_end)
    frontend, shutdown_abort = frontend_evidence(args.retroarch_log)

    findings = []
    if sequence_end and dsce_last >= sequence_end:
        findings.append({
            "severity": "critical",
            "code": "rom_audio_sequence_span_excludes_mario_sfx",
            "evidence": (
                f"the linked Sequence_0_End is 0x{sequence_end:X}, but {dsce_last_name} continues through "
                f"0x{dsce_last:X}. The generated channels were placed after "
                ".endseq, so the audio table allocated and loaded only the vanilla sequence span. "
                f"The next permanent audio allocations own sequence offsets 0x{sequence_end:X} and above; "
                "executing a Mario SFX there interprets soundfont bytes as sequencer opcodes"
            ),
        })
    if metrics["graph_thread_state"] == 1 and metrics["graph_thread_flags"] == 2:
        findings.append({
            "severity": "critical",
            "code": "rom_graph_thread_fault",
            "evidence": (
                f"the N64 graph/game thread stopped on a CPU fault at {metrics['graph_thread_pc_symbol']} "
                f"with RA={metrics['graph_thread_ra_symbol']}, badVAddr="
                f"0x{metrics['graph_fault_badvaddr'] & 0xFFFFFFFF:08X}, cause="
                f"0x{metrics['graph_fault_cause'] & 0xFFFFFFFF:08X}; this directly explains a frozen game "
                "while the independent audio thread continues"
            ),
        })
    if shutdown_abort and args.retroarch_exit_code != 0:
        findings.append({
            "severity": "warning",
            "code": "retroarch_shutdown_abort",
            "evidence": "RetroArch restored its video driver, then aborted during teardown with a mutex exception",
        })
    elif (args.termination_reason == "retroarch-exited" and args.retroarch_exit_code != 0
            and not args.launcher_terminated):
        findings.append({
            "severity": "critical",
            "code": "retroarch_process_crashed",
            "evidence": f"RetroArch exited on its own with process status {args.retroarch_exit_code}",
        })
    if metrics["request_count"] and metrics["last_active_note_frame"] == 0:
        findings.append({
            "severity": "critical",
            "code": "no_active_notes_observed",
            "evidence": "sound requests were recorded, but the synth never reported an active note",
        })
    elif metrics["last_request_frame"] > metrics["last_active_note_frame"] + 60:
        findings.append({
            "severity": "critical",
            "code": "audio_engine_stalled",
            "evidence": (f"requests continued through frame {metrics['last_request_frame']} after the last "
                         f"active synth note at frame {metrics['last_active_note_frame']}"),
        })
    if metrics["kernel_sound_hits"] and metrics["font41_live_samples"] == 0:
        findings.append({
            "severity": "critical",
            "code": "mario_font_load_failure",
            "evidence": "Mario sound mappings succeeded, but no live font-41 note was ever observed",
        })
    heard_silence = re.search(r"(?i)silent|inaudible|no sound", args.observation)
    observed_crash = re.search(r"(?i)crash|fault|hung|froze|frozen", args.observation)
    if observed_crash and metrics["rite_transitions"]:
        rite_names = ["idle", "ring", "fade", "give", "gone"]
        last_state = metrics["last_statue_state"]
        state_name = rite_names[last_state] if 0 <= last_state < len(rite_names) else str(last_state)
        findings.append({
            "severity": "critical",
            "code": "crash_during_song_of_healing_rite",
            "evidence": (f"the ROM entered the statue rite and its last completed update was state "
                         f"{state_name}, timer {metrics['last_statue_timer']}, fade "
                         f"{metrics['last_statue_fade_milli']}/1000; the last transition was "
                         f"{metrics['last_rite_from_state']}->{metrics['last_rite_to_state']}"),
        })
    audio_manager_terminated = (
        metrics["pipeline_samples"] >= 60
        and metrics["audio_task_tail_delta"] == 0
        and metrics["last_audio_mgr_interrupt_queue"] >= 30
        and metrics["last_audio_mgr_cmd_queue"] > 0
        and metrics["last_scheduler_rsp_task"] == 0
        and metrics["last_audio_sc_task_state"] == 0
    )
    recovered_channel_ptr = metrics["channel_ptr_corruption_count"] > 0
    if metrics["bad_stopchan_events"] > 0:
        fault_seq = metrics["first_flight_fault_seq"]
        fault_offset = metrics["first_flight_fault_offset"]
        prior_opcode = next(
            (item for item in reversed(flight_history)
             if item["event_seq"] < fault_seq and item["kind"] == 1
             and item["player"] == metrics["first_flight_fault_player"]
             and item["channel"] == metrics["first_flight_fault_channel"]
             and item["pc"] == metrics["first_flight_fault_pc"]),
            None,
        )
        matching_write = next(
            (item for item in reversed(flight_history)
             if item["event_seq"] < fault_seq and item["kind"] == 3
             and item["seq_data"] == metrics["first_flight_fault_seq_data"]
             and item["a"] == fault_offset),
            None,
        )
        overlap = next(
            (item for item in reversed(flight_history)
             if item["event_seq"] < fault_seq and item["kind"] == 7
             and item["player"] == metrics["first_flight_fault_player"]),
            None,
        )
        raw_text = (f"0x{prior_opcode['a'] & 0xFFFFFFFF:08X}" if prior_opcode else "not retained")
        origin = (
            f"The same flight history records a sequence-write opcode 0x{matching_write['opcode']:02X} "
            f"changing that offset from 0x{(matching_write['b'] >> 16) & 0xFFFF:04X} to "
            f"0x{matching_write['b'] & 0xFFFF:04X}."
            if matching_write else
            (f"An audio DMA overlapping this active sequence was recorded at event {overlap['event_seq']}."
             if overlap else
             "No MM sequence-write opcode or audio DMA overlap targeting this byte appears in the retained causal history.")
        )
        findings.append({
            "severity": "critical",
            "code": "rom_audio_stopchan_index_out_of_bounds",
            "evidence": (
                f"the audio-thread flight recorder caught sequence player "
                f"{metrics['first_flight_fault_player']}, channel {metrics['first_flight_fault_channel']} "
                f"executing opcode 0xCD at sequence offset 0x{fault_offset:X} with requested channel "
                f"index {metrics['first_flight_fault_a']}; valid indices are 0..15. The exact runtime "
                f"opcode word was {raw_text}, and channels[{metrics['first_flight_fault_a']}] resolves "
                f"to address 0x{metrics['first_flight_fault_b'] & 0xFFFFFFFF:08X}. {origin} The debug-only "
                "boundary stopped this channel before it could treat the player script PC as a channel and "
                "corrupt the audio lists"
            ),
        })
    if recovered_channel_ptr:
        bad_ptr = metrics["channel_ptr_corruption_bad_ptr"] & 0xFFFFFFFF
        seq_data = metrics["channel_ptr_corruption_seq_data"] & 0xFFFFFFFF
        misc_start = metrics["channel_ptr_corruption_misc_start"] & 0xFFFFFFFF
        misc_cur = metrics["channel_ptr_corruption_misc_cur"] & 0xFFFFFFFF
        bad_offset = bad_ptr - seq_data
        location = (f"inside sequence data at offset 0x{bad_offset:X}"
                    if 0 <= bad_offset < 0x100000 else "outside the owning sequence data")
        channel_array = ", ".join(
            f"0x{metrics[f'channel_ptr_corruption_ch{i}'] & 0xFFFFFFFF:08X}" for i in range(16))
        alias_evidence = (
            " The bad pointer exactly equals this player's script PC; because scriptState immediately follows "
            "the 16-entry channels array, this proves an opcode indexed channels[16]."
            if bad_ptr == (metrics["channel_ptr_corruption_script_pc"] & 0xFFFFFFFF) else "")
        channel_ptr_evidence = (
            f"before channel processing, sequence player {metrics['channel_ptr_corruption_player']} slot "
            f"{metrics['channel_ptr_corruption_slot']} contained 0x{bad_ptr:08X}, {location}, rather than a "
            f"SequenceChannel in misc-pool range 0x{misc_start:08X}..0x{misc_cur:08X}; audio task "
            f"{metrics['channel_ptr_corruption_task']}, sequence id {metrics['channel_ptr_corruption_seq_id']}, "
            f"player-script offset 0x{metrics['channel_ptr_corruption_script_offset'] & 0xFFFFFFFF:X}, depth "
            f"{metrics['channel_ptr_corruption_depth']}, value {metrics['channel_ptr_corruption_value']}, "
            f"stack [0x{metrics['channel_ptr_corruption_stack0'] & 0xFFFFFFFF:08X}, "
            f"0x{metrics['channel_ptr_corruption_stack1'] & 0xFFFFFFFF:08X}, "
            f"0x{metrics['channel_ptr_corruption_stack2'] & 0xFFFFFFFF:08X}, "
            f"0x{metrics['channel_ptr_corruption_stack3'] & 0xFFFFFFFF:08X}]; all channel pointers were "
            f"[{channel_array}]. The same pointer was stored in fixed layer "
            f"{metrics['channel_ptr_corruption_matching_layer']} (layer PC "
            f"0x{metrics['channel_ptr_corruption_matching_layer_pc'] & 0xFFFFFFFF:08X}, note "
            f"0x{metrics['channel_ptr_corruption_matching_layer_note'] & 0xFFFFFFFF:08X}), which identifies "
            "the layer/note playback path when the layer index is nonnegative. "
            f"{alias_evidence} "
            "Without the debug-only boundary guard MM treats sequence bytes as a channel, "
            "overwrites more sequence bytes, requests invalid samples, stops audio, and loses audio pacing"
        )
        if not audio_manager_terminated:
            findings.append({
                "severity": "critical",
                "code": "rom_audio_sequence_channel_pointer_corruption_recovered",
                "evidence": channel_ptr_evidence,
            })
    if not audio_manager_terminated and metrics["invalid_slow_load_count"] > 0:
        findings.append({
            "severity": "critical",
            "code": "rom_audio_illegal_sample_load_request_recovered",
            "evidence": (
                f"the first illegal sample load requested font {metrics['invalid_slow_load_font']}, "
                f"instrument {metrics['invalid_slow_load_inst']} from sequence player "
                f"{metrics['invalid_slow_load_player']}, channel {metrics['invalid_slow_load_channel']}, "
                f"port {metrics['invalid_slow_load_port']}, sequence offset "
                f"0x{metrics['invalid_slow_load_seq_offset'] & 0xFFFFFFFF:X}, opcode bytes "
                f"0x{metrics['invalid_slow_load_opcode_word'] & 0xFFFFFFFF:08X}, stack depth "
                f"{metrics['invalid_slow_load_depth']}; AudioLoad_GetFontSample "
                f"returned 0x{metrics['invalid_slow_load_sample'] & 0xFFFFFFFF:08X}. The debug guard rejected "
                "the request before MM could index instruments[-1]"
            ),
        })
    if audio_manager_terminated:
        phase_names = {
            0: "entered AudioThread_Update before the full-update branch",
            1: "waiting for per-frame audio DMA completions",
            2: "processing audio loads after the DMA drain",
            3: "processing script-load completion",
            4: "processing commands/reset state before synthesis",
            5: "inside AudioSynth_Update",
            6: "building the RSP task after synthesis",
            7: "after returning a complete audio task",
        }
        phase = metrics["last_audio_update_phase"]
        phase_text = phase_names.get(phase, f"unknown phase {phase}")
        synth_stage_names = {
            0: "not captured",
            1: "entering an update slice",
            2: "entering a note",
            3: "after reading sample metadata",
            4: "entering a sample part",
            5: "at the top of the decoder loop",
            6: "inside AudioLoad_DmaSampleData",
            7: "after AudioLoad_DmaSampleData",
            8: "after advancing decoder progress",
            9: "jumping to the sample loop point",
            10: "finishing a sample",
            11: "leaving a note",
            12: "leaving an update slice",
            13: "entering final reverb bookkeeping",
            14: "updating a final reverb entry",
            15: "after final reverb bookkeeping",
            16: "returning the completed ABI command list",
        }
        synth_stage = metrics["last_synth_stage"]
        synth_text = synth_stage_names.get(synth_stage, f"unknown synth stage {synth_stage}")
        sample_addr = metrics["last_synth_sample_addr"]
        sample_name = "Koto" if 0x004BB450 <= sample_addr < 0x004BFD00 else "unmapped"
        if synth_stage >= 13:
            synth_detail = (f"tail fields: index/count={metrics['last_synth_note']}, "
                            f"reverbCount={metrics['last_synth_update']}, "
                            f"framesToIgnore={metrics['last_synth_part']}")
        else:
            synth_detail = (f"note={metrics['last_synth_note']}, update={metrics['last_synth_update']}, "
                            f"part={metrics['last_synth_part']}, sample={sample_name}@"
                            f"0x{sample_addr & 0xFFFFFFFF:08X}, "
                            f"sampleEnd={metrics['last_synth_sample_end']}, "
                            f"loop={metrics['last_synth_loop_start']}..{metrics['last_synth_loop_end']}, "
                            f"progress={metrics['last_synth_processed']}/{metrics['last_synth_target']}, "
                            f"samplePos={metrics['last_synth_sample_pos']}, "
                            f"iteration={metrics['last_synth_iteration']}, codec={metrics['last_synth_codec']}, "
                            f"medium={metrics['last_synth_medium']}, frequency={metrics['last_synth_frequency']}")
        recovered_slow_load = metrics["invalid_slow_load_count"] > 0
        recovered_layer = metrics["invalid_seq_layer_count"] > 0
        faulted_layer = (metrics["audio_thread_state"] == 1 and (
            metrics["audio_thread_pc_symbol"].startswith("AudioScript_SeqLayerProcessScript+0x14") or
            (metrics["audio_thread_pc_symbol"].startswith("AudioList_PushBack+0x0") and
             metrics["audio_thread_ra_symbol"].startswith("AudioScript_SeqLayerFree"))))
        if recovered_channel_ptr:
            finding_code = "rom_audio_sequence_channel_pointer_corruption"
            finding_evidence = channel_ptr_evidence
        elif recovered_slow_load:
            finding_code = "rom_audio_invalid_slow_load_sample_pointer_recovered"
            finding_evidence = (
                f"the debug ROM rejected sample pointer 0x{metrics['invalid_slow_load_sample'] & 0xFFFFFFFF:08X} "
                f"returned for font {metrics['invalid_slow_load_font']}, instrument "
                f"{metrics['invalid_slow_load_inst']} from sequence player "
                f"{metrics['invalid_slow_load_player']}, channel {metrics['invalid_slow_load_channel']}, "
                f"sequence offset 0x{metrics['invalid_slow_load_seq_offset'] & 0xFFFFFFFF:X} "
                f"(opcode bytes 0x{metrics['invalid_slow_load_opcode_word'] & 0xFFFFFFFF:08X}, "
                f"script value {metrics['invalid_slow_load_value']}, stack depth "
                f"{metrics['invalid_slow_load_depth']}, dynTable "
                f"0x{metrics['invalid_slow_load_dyn_table'] & 0xFFFFFFFF:08X}, unk_22 "
                f"0x{metrics['invalid_slow_load_unk22'] & 0xFFFFFFFF:04X}) "
                f"by AudioLoad_GetFontSample; this occurred {metrics['invalid_slow_load_count']} time(s). "
                "This is the earliest captured ROM fault: unguarded code dereferences that pointer in "
                "AudioLoad_SlowLoadSample, stops the N64 audio thread, drains PCM, and removes audio pacing"
            )
        elif recovered_layer:
            operation = ("free" if metrics["invalid_seq_layer_index"] < 0 else "process")
            slot = (-1 - metrics["invalid_seq_layer_index"] if operation == "free"
                    else metrics["invalid_seq_layer_index"])
            finding_code = "rom_audio_sequence_layer_pointer_corruption_recovered"
            finding_evidence = (
                f"the debug ROM rejected invalid sequence-layer pointer "
                f"0x{metrics['invalid_seq_layer'] & 0xFFFFFFFF:08X} during {operation} of slot {slot}; "
                f"the owning context was sequence player {metrics['invalid_seq_player']}, channel "
                f"{metrics['invalid_seq_channel']}, font {metrics['invalid_seq_font']}, audio task "
                f"{metrics['invalid_seq_audio_task']}, script offset "
                f"0x{metrics['invalid_seq_script_offset'] & 0xFFFFFFFF:X}, depth "
                f"{metrics['invalid_seq_depth']}, value {metrics['invalid_seq_value']}, dynTable "
                f"0x{metrics['invalid_seq_dyn_table'] & 0xFFFFFFFF:08X}, stack "
                f"[0x{metrics['invalid_seq_stack0'] & 0xFFFFFFFF:08X}, "
                f"0x{metrics['invalid_seq_stack1'] & 0xFFFFFFFF:08X}, "
                f"0x{metrics['invalid_seq_stack2'] & 0xFFFFFFFF:08X}, "
                f"0x{metrics['invalid_seq_stack3'] & 0xFFFFFFFF:08X}]. This occurred "
                f"{metrics['invalid_seq_layer_count']} time(s); "
                "the guard is debug-only and proves the ROM sequencer received a pointer outside its fixed layer pool"
            )
        elif faulted_layer:
            finding_code = "rom_audio_invalid_sequence_layer_pointer"
            finding_evidence = (
                "the N64 audio thread was stopped by a CPU fault on the first load through a sequence-layer "
                f"pointer: a0=0x{metrics['audio_fault_a0'] & 0xFFFFFFFF:08X}, "
                f"badVAddr=0x{metrics['audio_fault_badvaddr'] & 0xFFFFFFFF:08X}, "
                f"cause=0x{metrics['audio_fault_cause'] & 0xFFFFFFFF:08X}; the channel loop last selected "
                f"channel=0x{metrics['last_seq_channel'] & 0xFFFFFFFF:08X}, layer slot "
                f"{metrics['last_seq_layer_index']}, layer=0x{metrics['last_seq_layer'] & 0xFFFFFFFF:08X}, "
                f"font={metrics['last_seq_font']}. The stopped sequencer prevents new audio tasks, PCM drains, "
                "and the game then runs without audio pacing"
            )
        else:
            finding_code = "rom_audio_update_blocked"
            finding_evidence = ("the completed RSP task left a message in the audio-manager command queue, "
                         "but its retrace queue filled to 30/30 while the scheduler had no running "
                         f"RSP task; the last audio-thread phase was {phase_text} "
                         f"(phase args={metrics['last_audio_update_phase_a']},"
                         f"{metrics['last_audio_update_phase_b']}, last DMA dev="
                         f"{metrics['last_audio_dma_dev_addr']}, size={metrics['last_audio_dma_size']}) "
                         f"The synth snapshot was {synth_text}: {synth_detail}; "
                         f"saved audio-thread PC={metrics['audio_thread_pc_symbol']} "
                         f"(0x{metrics['audio_thread_pc'] & 0xFFFFFFFF:08X}), "
                         f"RA={metrics['audio_thread_ra_symbol']} "
                         f"(state={metrics['audio_thread_state']}); "
                         f"(timeouts={metrics['audio_mgr_timeouts']}, exhausted bursts="
                         f"{metrics['audio_mgr_exhausted_bursts']})")
        findings.append({
            "severity": "critical",
            "code": finding_code,
            "evidence": finding_evidence,
        })
    elif heard_silence and metrics["pipeline_samples"] >= 60 and metrics["audio_task_tail_delta"] == 0:
        findings.append({
            "severity": "critical",
            "code": "rom_audio_thread_stalled",
            "evidence": (f"the ROM audio task counter stopped at {metrics['last_audio_task_count']} "
                         "through the final 60 gameplay frames"),
        })
    if (metrics["pipeline_samples"] >= 60 and metrics["audio_task_tail_delta"] > 0
            and metrics["ai_submit_attempt_tail_delta"] == 0):
        findings.append({
            "severity": "critical",
            "code": "rom_ai_submission_stopped",
            "evidence": (f"the ROM audio task counter advanced by {metrics['audio_task_tail_delta']} "
                         "while osAiSetNextBuffer made no attempt in the final 60 gameplay frames"),
        })
    if (metrics["ai_submit_attempt_tail_delta"] >= 10
            and metrics["ai_submit_failure_tail_delta"] == metrics["ai_submit_attempt_tail_delta"]):
        findings.append({
            "severity": "critical",
            "code": "rom_ai_submissions_all_rejected",
            "evidence": (f"all {metrics['ai_submit_attempt_tail_delta']} ROM AI submissions in the final "
                         "60 gameplay frames returned failure"),
        })
    elif metrics["ai_submit_failure_tail_delta"] > 0:
        findings.append({
            "severity": "warning",
            "code": "rom_ai_submission_failures",
            "evidence": (f"{metrics['ai_submit_failure_tail_delta']} of "
                         f"{metrics['ai_submit_attempt_tail_delta']} ROM AI submissions failed in the "
                         "final 60 gameplay frames"),
        })
    if metrics["audio_mgr_exhausted_bursts"] > 0 and not audio_manager_terminated:
        findings.append({
            "severity": "warning",
            "code": "rom_audio_manager_recovered_after_timeout_burst",
            "evidence": (f"the debug ROM exhausted {metrics['audio_mgr_exhausted_bursts']} timeout "
                         f"burst(s), reached {metrics['audio_mgr_max_consecutive_timeouts']} consecutive "
                         "32 ms timeouts, then resumed completing audio tasks"),
        })
    if (heard_silence and metrics["pipeline_samples"]
            and metrics["last_nonzero_pcm_frame"] + 20 < metrics["last_pipeline_frame"]):
        findings.append({
            "severity": "critical",
            "code": "rom_pcm_output_became_silent",
            "evidence": (f"the ROM's live AI buffer last contained nonzero PCM at frame "
                         f"{metrics['last_nonzero_pcm_frame']}, while telemetry continued through "
                         f"frame {metrics['last_pipeline_frame']}"),
        })
    if (heard_silence
            and metrics["seq_samples"]
            and metrics["last_active_note_frame"] + 1 >= metrics["last_seq_frame"]
            and not metrics["pipeline_samples"]):
        findings.append({
            "severity": "critical",
            "code": "failure_downstream_of_rom_sequencer",
            "evidence": (f"the user heard silence while the ROM synth still had active notes through "
                         f"frame {metrics['last_active_note_frame']}; the older capture did not include "
                         "the ROM's RSP/AI boundary telemetry"),
        })
    if metrics["permanent_size"] and metrics["permanent_headroom"] < 8192:
        findings.append({
            "severity": "warning",
            "code": "permanent_pool_low",
            "evidence": f"permanent audio pool reached {metrics['permanent_highwater']} / {metrics['permanent_size']} bytes",
        })
    if metrics["unhealthy_seq_tail_samples"]:
        findings.append({
            "severity": "warning",
            "code": "seqplayer_unhealthy_near_capture_end",
            "evidence": f"{metrics['unhealthy_seq_tail_samples']} end-of-run samples had a disabled or finished SFX sequencer",
        })
    if frontend:
        findings.append({
            "severity": "warning",
            "code": "retroarch_audio_or_pacing_warnings",
            "evidence": f"RetroArch emitted {len(frontend)} relevant warning/error lines",
        })
    if not findings:
        if metrics["seq_samples"] >= 120:
            findings.append({
                "severity": "info",
                "code": "healthy_to_capture_end",
                "evidence": "no known synth, font, pool, sequencer, or frontend warning signature was detected",
            })
        else:
            findings.append({
                "severity": "warning",
                "code": "insufficient_telemetry",
                "evidence": f"only {metrics['seq_samples']} sequencer samples were captured; at least 120 are required",
            })

    severity = "critical" if any(x["severity"] == "critical" for x in findings) else (
        "warning" if any(x["severity"] == "warning" for x in findings) else "healthy"
    )
    report = {
        "run_id": run,
        "status": severity,
        "findings": findings,
        "metrics": metrics,
        "retroarch_evidence": frontend,
        "process": {
            "exit_code": args.retroarch_exit_code,
            "termination_reason": args.termination_reason,
            "launcher_terminated": args.launcher_terminated,
        },
        "user_observation": args.observation,
        "sequence_flight_history": flight_history,
        "interpretation_note": (
            "The diagnosis follows the ROM path in order: sound request, sequencer/note state, "
            "audio-task clock, audio-manager timeout/queue state, RSP command list, live PCM buffer, "
            "then N64 AI DMA state."
        ),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "diagnosis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [f"DSCE debug diagnosis: {severity.upper()}", f"run: {run}", ""]
    if args.observation:
        lines.append(f"User observation: {args.observation}\n")
    if args.launcher_terminated:
        lines.append(f"Process note: launcher ended RetroArch ({args.termination_reason}); this is not classified as a crash.\n")
    lines.extend(f"[{item['severity'].upper()}] {item['code']}: {item['evidence']}"
                 for item in findings)
    lines.extend(["", report["interpretation_note"], "", "Metrics:"])
    lines.extend(f"  {key}: {value}" for key, value in sorted(metrics.items()))
    if flight_history:
        kind_names = {
            1: "channel-opcode", 2: "player-opcode", 3: "sequence-write",
            4: "bad-stopchan", 5: "bad-slowload", 6: "sequence-load",
            7: "dma-overlap", 8: "bad-pointer",
        }
        lines.extend(["", "Sequence flight recorder (oldest to first fault):"])
        lines.extend(
            f"  event={item['event_seq']} task={item['task']} frame={item['frame']} "
            f"kind={kind_names.get(item['kind'], item['kind'])} player={item['player']} "
            f"channel={item['channel']} opcode=0x{item['opcode']:02X} "
            f"pc=0x{item['pc'] & 0xFFFFFFFF:08X} offset=0x{item['seq_offset'] & 0xFFFFFFFF:X} "
            f"a=0x{item['a'] & 0xFFFFFFFF:08X} b=0x{item['b'] & 0xFFFFFFFF:08X}"
            for item in flight_history
        )
    if frontend:
        lines.extend(["", "RetroArch evidence:"] + [f"  {line}" for line in frontend])
    (args.out_dir / "diagnosis.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{severity}: {args.out_dir / 'diagnosis.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
