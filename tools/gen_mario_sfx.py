#!/usr/bin/env python3
"""Mint SM64's real SFX for the MM ROM (PC parity: on PC, SM64's own audio engine plays
every sound; here we pre-render each sound EXACTLY as SM64's sound player performs it).

Parses .work/sm64/sound/sequences/00_sound_player.s (the authoritative soundID ->
bank/instrument/notes tables) + sound_banks/*.json (instrument -> sample aiff), renders
each kernel-reachable sound to a 32kHz mono WAV (same notes, pitches 2^((n-39)/12),
velocities, note timing at tempo 120 / 48ppqn), and emits:
  out-dir/*.wav                  the rendered sounds
  out-dir/manifest.json          [{name, wav, bank, id}]
  <map-header>                   soundBits(bank,id) -> NA_SE_DSCE index for the shim

Usage: gen_mario_sfx.py <sm64-root> <out-dir> <map-header>
"""
import json
import os
import re
import struct
import subprocess
import sys

RATE = 32000
TICK = 60.0 / (120 * 48)  # tempo 120, 48 ppqn

# (bank, id): mint name. SHARED entries map several ids onto one mint (perceptually
# identical in SM64: tiptoe = quiet step, twirl = spin, heavy terrain layer ~= default).
TERR = ["default", "grass", "water", "stone", "spooky", "snow", "ice", "sand"]
MINTS = {}
SHARES = {}
for t in range(8):
    MINTS[(0, 0x00 + t)] = f"jump_{TERR[t]}"
    MINTS[(0, 0x08 + t)] = f"land_{TERR[t]}"
    MINTS[(0, 0x10 + t)] = f"step_{TERR[t]}"
    MINTS[(0, 0x18 + t)] = f"bodyhit_{TERR[t]}"
    SHARES[(0, 0x20 + t)] = f"step_{TERR[t]}"      # tiptoe -> step
    SHARES[(0, 0x60 + t)] = "heavy_land"           # heavy landing (one render)
MINTS[(0, 0x60)] = "heavy_land"
MINTS[(0, 0x37)] = "spin"
SHARES[(0, 0x38)] = "spin"                          # twirl == spin (same sound)
MINTS[(0, 0x33)] = "swim"
SHARES[(0, 0x47)] = "swim"                          # swim_fast
MINTS[(0, 0x45)] = "bonk"
MINTS[(0, 0x44)] = "hit"
MINTS[(0, 0x35)] = "throw"
SHARES[(0, 0x3F)] = "throw"                         # pat_back
MINTS[(0, 0x5A)] = "side_flip"
MINTS[(0, 0x30)] = "plunge"
MINTS[(0, 0x31)] = "splash"
MINTS[(0, 0x32)] = "splash_small"
MINTS[(0, 0x2E)] = "quicksand_step"
MINTS[(0, 0x48)] = "unstuck"
MINTS[(1, 0x18)] = "slide"                          # SOUND_MOVING_TERRAIN_SLIDE id
MINTS[(1, 0x10)] = "lava_burn"                      # SOUND_MOVING_LAVA_BURN id
# Voice bank: every id the vendored kernel requests, 1:1.  Keep these names aligned
# with channel2_table, not merely with the instrument sample name: several ids alias
# the same sequence (notably 0x2B..0x2D are all Yahoo).
VOICE_IDS = {
    0x00: "vo_yah", 0x01: "vo_wah", 0x02: "vo_hoo", 0x03: "vo_hoohoo",
    0x04: "vo_yahoo", 0x05: "vo_uh", 0x06: "vo_hrmm", 0x07: "vo_wah2",
    0x08: "vo_whoa", 0x09: "vo_eeuh", 0x0A: "vo_attacked", 0x0B: "vo_ooof",
    0x0C: "vo_here_we_go", 0x0D: "vo_yawning", 0x0E: "vo_snoring1",
    0x0F: "vo_snoring2", 0x10: "vo_waaaooow", 0x11: "vo_haha", 0x12: "vo_panting1_alias",
    0x13: "vo_uh2", 0x14: "vo_on_fire", 0x15: "vo_dying", 0x16: "vo_panting_cold",
    0x17: "vo_coughing3_alias", 0x18: "vo_panting1", 0x19: "vo_panting2",
    0x1A: "vo_panting3", 0x1B: "vo_coughing1", 0x1C: "vo_coughing2",
    0x1D: "vo_coughing3",
    0x1E: "vo_punch_yah", 0x1F: "vo_punch_hoo", 0x20: "vo_mama_mia",
    0x22: "vo_pound_wah", 0x23: "vo_drowning", 0x24: "vo_punch_wah",
    0x2B: "vo_yahoo2", 0x2C: "vo_yahoo3", 0x2D: "vo_yahoo4",
    0x2E: "vo_waha", 0x2F: "vo_yippee", 0x30: "vo_doh",
    0x35: "vo_snoring3", 0x36: "vo_so_long", 0x37: "vo_ima_tired",
}
# The semantic table labels are a compile-time contract.  A shifted hard-coded id
# silently gives a perfectly valid but completely wrong Mario voice.
VOICE_REFS = {
    0x00: "sound_mario_jump_yah", 0x01: "sound_mario_jump_wah", 0x02: "sound_mario_jump_hoo",
    0x03: "sound_mario_hoohoo", 0x04: "sound_mario_yahoo", 0x05: "sound_mario_uh",
    0x06: "sound_mario_hrmm", 0x07: "sound_mario_wah2", 0x08: "sound_mario_whoa",
    0x09: "sound_mario_eeuh", 0x0A: "sound_mario_attacked", 0x0B: "sound_mario_ooof",
    0x0C: "sound_mario_here_we_go", 0x0D: "sound_mario_yawning",
    0x0E: "sound_mario_snoring1", 0x0F: "sound_mario_snoring2",
    0x10: "sound_mario_waaaooow", 0x11: "sound_mario_haha", 0x12: "sound_mario_panting1",
    0x13: "sound_mario_uh2", 0x14: "sound_mario_on_fire", 0x15: "sound_mario_dying",
    0x16: "sound_mario_panting_cold", 0x17: "sound_mario_coughing3",
    0x18: "sound_mario_panting1", 0x19: "sound_mario_panting2",
    0x1A: "sound_mario_panting3", 0x1B: "sound_mario_coughing1",
    0x1C: "sound_mario_coughing2", 0x1D: "sound_mario_coughing3",
    0x1E: "sound_mario_punch_yah", 0x1F: "sound_mario_punch_hoo",
    0x20: "sound_mario_mama_mia", 0x22: "sound_mario_ground_pound_wah",
    0x23: "sound_mario_drowning", 0x24: "sound_mario_punch_wah",
    0x2B: "sound_mario_yahoo", 0x2C: "sound_mario_yahoo", 0x2D: "sound_mario_yahoo",
    0x2E: "sound_mario_waha", 0x2F: "sound_mario_yippee", 0x30: "sound_mario_doh",
    0x35: "sound_mario_snoring3", 0x36: "sound_mario_so_longa_bowser",
    0x37: "sound_mario_ima_tired",
}
assert set(VOICE_IDS) == set(VOICE_REFS)
for i, n in VOICE_IDS.items():
    MINTS[(2, i)] = n


def preprocess_us(src):
    """Select the VERSION_US branches without depending on a host C preprocessor."""
    defined = {"VERSION_US"}

    def condition(expr):
        # The sequence source only uses defined(X), !, && and || in its conditions.
        def atom(value):
            value = value.strip()
            invert = value.startswith("!")
            value = value.lstrip("!").strip()
            match = re.fullmatch(r"defined\((\w+)\)", value)
            if not match:
                raise ValueError(f"unsupported preprocessor condition: {expr}")
            result = match.group(1) in defined
            return not result if invert else result

        return any(all(atom(a) for a in term.split("&&")) for term in expr.split("||"))

    result = []
    active = True
    stack = []  # (parent_active, any_branch_taken)
    for number, line in enumerate(src.splitlines(), 1):
        directive = line.strip()
        if directive.startswith("#ifdef "):
            take = directive.split()[1] in defined
            stack.append((active, take))
            active = active and take
        elif directive.startswith("#ifndef "):
            take = directive.split()[1] not in defined
            stack.append((active, take))
            active = active and take
        elif directive.startswith("#if "):
            take = condition(directive[4:])
            stack.append((active, take))
            active = active and take
        elif directive.startswith("#elif "):
            if not stack:
                raise ValueError(f"unmatched #elif at line {number}")
            parent, taken = stack[-1]
            take = (not taken) and condition(directive[6:])
            stack[-1] = (parent, taken or take)
            active = parent and take
        elif directive == "#else":
            if not stack:
                raise ValueError(f"unmatched #else at line {number}")
            parent, taken = stack[-1]
            stack[-1] = (parent, True)
            active = parent and not taken
        elif directive == "#endif":
            if not stack:
                raise ValueError(f"unmatched #endif at line {number}")
            active = stack.pop()[0]
        elif active:
            result.append(line)
    if stack:
        raise ValueError("unterminated preprocessor conditional")
    return "\n".join(result)


def parse_player(path):
    """Interpret the finite US sound-player channel/layer scripts used by SFX."""
    src = preprocess_us(open(path).read())
    lines = [ln.split("//")[0].strip() for ln in src.splitlines()]

    labels = {}
    label_pc = {}
    program = []
    cur = None
    for ln in lines:
        m = re.match(r"^\.([A-Za-z0-9_]+):", ln)
        if m:
            cur = m.group(1)
            labels[cur] = []
            label_pc[cur] = len(program)
        elif cur and ln:
            labels[cur].append(ln)
            program.append(ln)

    def layer_notes(lbl):
        notes = []
        transpose = 0
        continuous = False
        portamento = None
        play_percentage = 0
        pc = label_pc[lbl]
        calls = []
        loops = []
        operations = 0
        visited = set()
        while pc < len(program):
            state = (pc, transpose, continuous, portamento, tuple(calls),
                     tuple((start, count) for start, count in loops))
            if state in visited:
                # Moving-bank layers loop for as long as their sound is active.
                # One complete cycle is the finite offline-rendering unit.
                break
            visited.add(state)
            operations += 1
            if operations > 4096:
                raise ValueError(f"layer {lbl} exceeded the finite interpreter limit")
            ln = program[pc]
            pc += 1
            m = re.match(r"layer_note1(?:_long)?\s+(\S+?),\s*(\S+?),\s*(\S+)", ln)
            if m:
                p, d, v = (int(x, 0) for x in m.groups())
                play_percentage = d
                notes.append({"pitch": p + transpose, "duration": d, "velocity": v,
                              "continuous": continuous, "portamento": portamento})
                if portamento is not None and (portamento[0] & 0x7F) in (1, 2):
                    portamento = None
            elif ln.startswith("layer_note0"):
                p, d, v, _note_duration = (int(x.strip(), 0) for x in
                                            ln.split(None, 1)[1].split(","))
                play_percentage = d
                notes.append({"pitch": p + transpose, "duration": d, "velocity": v,
                              "continuous": continuous, "portamento": portamento})
                if portamento is not None and (portamento[0] & 0x7F) in (1, 2):
                    portamento = None
            elif ln.startswith("layer_note2"):
                p, v, _note_duration = (int(x.strip(), 0) for x in
                                         ln.split(None, 1)[1].split(","))
                notes.append({"pitch": p + transpose, "duration": play_percentage,
                              "velocity": v, "continuous": continuous,
                              "portamento": portamento})
                if portamento is not None and (portamento[0] & 0x7F) in (1, 2):
                    portamento = None
            elif ln.startswith(("layer_delay", "layer_delay_long")):
                d = int(ln.split()[1].rstrip(","), 0)
                notes.append({"pitch": None, "duration": d, "velocity": 0,
                              "continuous": continuous, "portamento": None})
            elif ln.startswith("layer_transpose"):
                transpose = int(ln.split()[1].rstrip(","), 0)
            elif ln == "layer_somethingon":
                continuous = True
            elif ln == "layer_somethingoff":
                continuous = False
            elif ln.startswith("layer_portamento"):
                mode, target, time = (int(x.strip(), 0) for x in
                                      ln.split(None, 1)[1].split(","))
                portamento = (mode, target + transpose, time)
            elif ln == "layer_disableportamento":
                portamento = None
            elif ln.startswith("layer_jump"):
                pc = label_pc[ln.split()[1].lstrip(".")]
            elif ln.startswith("layer_call"):
                calls.append(pc)
                pc = label_pc[ln.split()[1].lstrip(".")]
            elif ln.startswith("layer_loop "):
                count = int(ln.split()[1].rstrip(","), 0) or 256
                loops.append([pc, count])
            elif ln == "layer_loopend":
                if not loops:
                    raise ValueError(f"unmatched layer_loopend in {lbl}")
                loops[-1][1] -= 1
                if loops[-1][1]:
                    pc = loops[-1][0]
                else:
                    loops.pop()
            elif ln == "layer_end":
                if calls:
                    pc = calls.pop()
                else:
                    break
        return notes

    def channel_layers(lbl):
        bank = None
        instr = 0
        value = 0
        onset = 0
        layers_out = []
        pc = label_pc[lbl]
        operations = 0
        while pc < len(program):
            operations += 1
            if operations > 1024:
                raise ValueError(f"channel {lbl} does not terminate")
            ln = program[pc]
            pc += 1
            if ln.startswith("chan_setbank"):
                bank = int(ln.split()[1], 0)
            elif ln.startswith("chan_setinstr"):
                instr = int(ln.split()[1], 0)
            elif ln.startswith("chan_setval"):
                value = int(ln.split()[1], 0)
            elif ln.startswith("chan_setlayer"):
                if bank is None:
                    raise ValueError(f"channel {lbl} starts a layer before selecting a bank")
                target = ln.split(",")[1].strip().lstrip(".")
                layers_out.append({"bank": bank, "instr": instr, "onset": onset,
                                   "events": layer_notes(target), "label": target})
            elif ln.startswith(("chan_delay ", "chan_delay_long ")):
                onset += int(ln.split()[1].rstrip(","), 0)
            elif ln == "chan_delay1":
                onset += 1
            elif ln.startswith("chan_call"):
                target = ln.split()[1].lstrip(".")
                if target == "delay":
                    # .delay consumes the current channel value as an interruptible
                    # delay. One tick separates Mario's voice and punch-swish layers.
                    onset += value
            elif ln.startswith("chan_jump"):
                pc = label_pc[ln.split()[1].lstrip(".")]
            elif ln == "chan_end":
                break
        return layers_out

    out = {}
    requested = set(MINTS) | set(SHARES)
    for ch, tbl in ((0, "channel0_table"), (1, "channel1_table"), (2, "channel2_table")):
        refs = [ln.split()[1].lstrip(".") for ln in labels.get(tbl, [])
                if ln.startswith("sound_ref")]
        for sid, ref in enumerate(refs):
            if (ch, sid) not in requested:
                continue
            lyrs = channel_layers(ref)
            if not lyrs:
                continue
            out[(ch, sid)] = {"ref": ref, "layers": lyrs}
    return out


def load_banks(root):
    banks = {}
    bdir = os.path.join(root, "sound", "sound_banks")
    for fn in os.listdir(bdir):
        m = re.match(r"([0-9A-F]{2})", fn)
        if not m:
            continue
        d = json.load(open(os.path.join(bdir, fn)))
        sb = d["sample_bank"]
        while isinstance(sb, dict):
            sb = sb.get("else") if "else" in sb else sb.get("then")
        d["sample_bank"] = sb
        insts = []
        for name in d["instrument_list"]:
            if name is None:
                insts.append(None)
                continue
            snd = d["instruments"][name].get("sound")
            while isinstance(snd, dict):
                snd = snd.get("else") if "else" in snd else snd.get("then")
            if snd is None:
                insts.append(None)
                continue
            insts.append(os.path.join(root, "sound", "samples",
                                      d["sample_bank"], snd + ".aiff"))
        banks[int(m.group(1), 16)] = insts
    return banks


def decode(path):
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1",
         "-ar", str(RATE), "-"])
    n = len(raw) // 4
    return list(struct.unpack("<%df" % n, raw[:n * 4]))


def pitch_ratio(pitch):
    return 2.0 ** ((pitch - 39) / 12.0)


def decoded_source(layer, banks, cache):
    src_path = banks[layer["bank"]][layer["instr"]]
    if src_path not in cache:
        cache[src_path] = decode(src_path)
    return cache[src_path]


def render_layer(layer, banks, cache):
    """Render a layer while preserving its note cursor and portamento state."""
    src = decoded_source(layer, banks, cache)
    events = layer["events"]
    if not any(event["pitch"] is not None for event in events):
        raise ValueError(f"parsed no notes from layer {layer['label']}")

    segments = []
    time_frames = int(layer["onset"] * TICK * RATE)
    source_pos = 0.0
    previous_continuous = False
    portamento_target = None

    for event_index, event in enumerate(events):
        duration = max(0, int(event["duration"] * TICK * RATE))
        if event["pitch"] is None:
            time_frames += duration
            previous_continuous = False
            continue
        if not (event["continuous"] and previous_continuous):
            source_pos = 0.0

        current_ratio = pitch_ratio(event["pitch"])
        start_ratio = end_ratio = current_ratio
        transition_time = 0
        portamento = event["portamento"]
        if portamento is not None:
            mode, target, transition_time = portamento
            mode_kind = mode & 0x7F
            if mode_kind == 5:
                if portamento_target is None:
                    portamento_target = target
                start_ratio = pitch_ratio(portamento_target)
                end_ratio = current_ratio
                portamento_target = event["pitch"]
            elif mode_kind in (1, 3):
                start_ratio = pitch_ratio(target)
                end_ratio = current_ratio
            elif mode_kind in (2, 4):
                start_ratio = current_ratio
                end_ratio = pitch_ratio(target)
            else:
                raise ValueError(f"unsupported portamento mode {mode:#x}")

        if duration == 0:
            duration = int(len(src) / max(0.01, min(start_ratio, end_ratio)))
        samples = []
        for index in range(duration):
            if source_pos + 1 >= len(src):
                break
            if start_ratio != end_ratio:
                if portamento[0] & 0x80:
                    progress = (index / max(1, duration - 1)) * (255.0 / max(1, transition_time))
                else:
                    elapsed_ticks = index / (RATE * TICK)
                    progress = elapsed_ticks / max(1, transition_time)
                fraction = min(1.0, progress)
                ratio = start_ratio * ((end_ratio / start_ratio) ** fraction)
            else:
                ratio = current_ratio
            i0 = int(source_pos)
            frac = source_pos - i0
            samples.append((src[i0] * (1.0 - frac) + src[i0 + 1] * frac)
                           * (event["velocity"] / 127.0))
            source_pos += ratio

        next_continuous = (event_index + 1 < len(events)
                           and events[event_index + 1]["pitch"] is not None
                           and event["continuous"]
                           and events[event_index + 1]["continuous"])
        if not next_continuous:
            for index in range(1, min(160, len(samples)) + 1):
                samples[-index] *= index / 160.0
        segments.append((time_frames, samples))
        time_frames += int(event["duration"] * TICK * RATE)
        previous_continuous = event["continuous"]
    return segments


def render(spec, banks, cache):
    tracks = [render_layer(layer, banks, cache) for layer in spec["layers"]]
    total = max(onset + len(samples) for track in tracks for onset, samples in track)
    mix = [0.0] * (total + 64)
    for evs in tracks:
        for onset, samples in evs:
            for index, sample in enumerate(samples):
                mix[onset + index] += sample
    peak = max(1e-9, max(abs(v) for v in mix))
    if peak > 0.98:
        mix = [v * 0.98 / peak for v in mix]
    return b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in mix)


def main():
    root, outdir, hdr = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    # The output is a generated staging directory. Remove only this tool's known
    # products so renamed/removed voices cannot survive and get copied into a later
    # build as unreferenced stale samples.
    generated = re.compile(
        r"(?:dsce_.*\.wav|Soundfont_(?:41|42)\.xml|manifest\.json|"
        r"(?:samples\.xml|playerbank|voicebank|seq_include|seq_heal_player|seq)\.frag)"
    )
    for filename in os.listdir(outdir):
        if generated.fullmatch(filename):
            os.unlink(os.path.join(outdir, filename))
    specs = parse_player(os.path.join(root, "sound", "sequences", "00_sound_player.s"))
    for sound_id, expected_ref in VOICE_REFS.items():
        actual = specs.get((2, sound_id), {}).get("ref")
        if actual != expected_ref:
            raise SystemExit(
                f"voice table contract failed at 0x{sound_id:02X}: "
                f"expected {expected_ref}, found {actual}"
            )
    yahoo = specs[(2, 0x2B)]["layers"]
    yahoo_notes = [event for layer in yahoo for event in layer["events"]
                   if event["pitch"] is not None]
    if len(yahoo) != 1 or len(yahoo_notes) != 2 or not all(
            event["continuous"] for event in yahoo_notes) or [
                (event["pitch"], event["duration"], event["portamento"])
                for event in yahoo_notes
            ] != [(40, 0x1E, (0x85, 37, 255)), (37, 0x41, (0x85, 37, 255))]:
        raise SystemExit(
            "Yahoo render contract failed: expected the US two-command continuous portamento"
        )
    # Regression contracts for the three classes of audible failure found in play.
    # These deliberately bind each layer at the moment chan_setlayer executes; using
    # a sound's final bank/instrument for every layer caused all three defects.
    contracts = {
        "first jump": ((2, 0x00), [(10, 9, 0, "layer_C5A")]),
        "punch yah": ((2, 0x1E), [(10, 9, 0, "layer_DFE"), (0, 0, 1, "layer_538")]),
        "punch hoo": ((2, 0x1F), [(10, 10, 0, "layer_E17"), (0, 0, 1, "layer_548")]),
        "punch wah": ((2, 0x24), [(8, 1, 0, "layer_E62"), (0, 0, 1, "layer_536")]),
        "wall hit": ((0, 0x44), [(7, 3, 0, "layer_618")]),
        "wall bonk": ((0, 0x45), [(7, 3, 0, "layer_659")]),
    }
    for description, (key, expected) in contracts.items():
        actual = [(layer["bank"], layer["instr"], layer["onset"], layer["label"])
                  for layer in specs[key]["layers"]]
        if actual != expected:
            raise SystemExit(f"{description} layer contract failed: {actual} != {expected}")
    first_jump = [event for event in specs[(2, 0x00)]["layers"][0]["events"]
                  if event["pitch"] is not None]
    if [(event["pitch"], event["duration"], event["portamento"])
            for event in first_jump] != [(36, 0x24, (0x82, 37, 200))]:
        raise SystemExit(f"first-jump pitch contract failed: {first_jump}")
    banks = load_banks(root)
    cache = {}
    durations = {}
    rendered = {}
    manifest = []
    misses = []
    for (bank, sid), name in sorted(MINTS.items()):
        if name in rendered:
            continue
        spec = specs.get((bank, sid))
        valid_layers = spec is not None and all(
            layer["bank"] in banks
            and layer["instr"] < len(banks[layer["bank"]])
            and banks[layer["bank"]][layer["instr"]] is not None
            for layer in spec["layers"]
        )
        if not valid_layers:
            misses.append((bank, sid, name))
            continue
        pcm = render(spec, banks, cache)
        durations[name] = len(pcm) // 2  # samples
        wav = os.path.join(outdir, f"dsce_{name}.wav")
        with open(wav, "wb") as f:  # minimal WAV header
            f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
                    + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16)
                    + b"data" + struct.pack("<I", len(pcm)) + pcm)
        rendered[name] = True
        manifest.append({"name": name, "wav": os.path.basename(wav)})
    order = [m["name"] for m in manifest]
    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w"), indent=1)

    def cname(n):
        return "DSCE_" + n.upper()

    def na_se(n):
        return ("NA_SE_VO_" if n.startswith("vo_") else "NA_SE_PL_") + cname(n)

    def chan(n):
        return ("CHAN_VO_" if n.startswith("vo_") else "CHAN_PL_") + cname(n)

    # staging fragments (consumed by tools/stage-mario-sfx.sh)
    with open(os.path.join(outdir, "samples.xml.frag"), "w") as f:
        for n in order:
            f.write(f'    <Sample Name="{cname(n)}" '
                    f'Path="$(BUILD_DIR)/assets/audio/samples/SampleBank_0/dsce_{n}.aifc"/>\n')
    # Already-rendered clips are MM one-shot effects, not pitched instruments.  The
    # aseq notedv opcode stores an effect id in its six-bit pitch field, so split the
    # clips into two fonts whose effect tables each stay below the hard 64-entry
    # limit.  This matches vanilla Link voice playback (FONTANY_INSTR_SFX + effect id)
    # and cannot leak an arbitrary instrument program into the next dispatched sound.
    font_groups = (
        (41, [n for n in order if not n.startswith("vo_")]),
        (42, [n for n in order if n.startswith("vo_")]),
    )
    # Sequence 0's compiled font list is reverse-indexed by the audio engine.
    # With the generated headers included, its list is [1, 41, 42, 0], so the
    # bytecode operands are local selectors 2 -> global font 41 and 1 -> global
    # font 42. Passing the global ids here is memory-unsafe: 41 resolves through
    # bytes before Fonts_0 (0xDD in the affected build), while 42 aliases font 1.
    # check_sfx_font_selectors.py proves these selectors against the compiled ELF.
    font_selector = {41: 2, 42: 1}
    effect_slot = {}
    for font_id, names in font_groups:
        assert 0 < len(names) <= 64, (font_id, len(names))
        with open(os.path.join(outdir, f"Soundfont_{font_id}.xml"), "w") as f:
            f.write(f'<Soundfont Name="Soundfont_{font_id}" Index="{font_id}" '
                    'Medium="MEDIUM_CART" CachePolicy="CACHE_LOAD_PERMANENT" '
                    'SampleBank="$(BUILD_DIR)/assets/audio/samplebanks/SampleBank_0.xml">\n')
            f.write('    <Samples>\n')
            for n in names:
                f.write(f'        <Sample Name="{cname(n)}"/>\n')
            f.write('    </Samples>\n    <Effects>\n')
            for i, n in enumerate(names):
                effect_slot[n] = (font_id, i)
                f.write(f'        <Effect Name="{cname(n)}" Sample="{cname(n)}"/>\n')
            f.write('    </Effects>\n</Soundfont>\n')
    assert len(effect_slot) == len(order)
    with open(os.path.join(outdir, "playerbank.frag"), "w") as f:
        for n in order:
            if not n.startswith("vo_"):
                f.write(f"DEFINE_SFX({chan(n)}, {na_se(n)}, 0x30, 0, 0, 0, "
                        "SFX_FLAG_FREQ_NO_DIST | SFX_PARAM_RAND_FREQ_SCALE)\n")
    with open(os.path.join(outdir, "voicebank.frag"), "w") as f:
        for n in order:
            if n.startswith("vo_"):
                f.write(f"DEFINE_SFX({chan(n)}, {na_se(n)}, 0x30, 0, 0, 0, "
                        "SFX_FLAG_FREQ_NO_DIST | SFX_PARAM_RAND_FREQ_SCALE)\n")
    with open(os.path.join(outdir, "seq_include.frag"), "w") as f:
        f.write('#include "Soundfont_41.h"\n#include "Soundfont_42.h"\n')
    # Reset both font and instrument mode.  Restoring only font 0 left the previous
    # normal-instrument selector live, so vanilla effect notes became grotesquely
    # pitched Soundfont_0 instruments after a generated sound.
    with open(os.path.join(outdir, "seq_heal_player.frag"), "w") as f:
        f.write("    fontinstr Soundfont_0_ID, FONTANY_INSTR_SFX // DSCE-HEAL-P\n")
    with open(os.path.join(outdir, "seq.frag"), "w") as f:
        f.write("\n// DSCE: Mario 64 SFX mint (generated; staged by stage-mario-sfx.sh)\n")
        for n in order:
            font_id, _ = effect_slot[n]
            # REAL duration in seq ticks (~10.42ms at tempo 120): a 0-duration note
            # never releases its bank channel and starves every other sound
            ticks = max(2, int(durations[n] / RATE / TICK) + 2)
            if os.environ.get("DSCE_BREAK_DUR") == "1":
                ticks = 0  # VALIDATION: reintroduce the channel-starvation bug
            # PURE vanilla shape: dyncalled channel scripts must return without ever
            # yielding (delay/delay1 inside the dyncall corrupts the handler's polling
            # -- the "sound dies + game runs 1.5x" hang). Font healing lives in the
            # dispatch handler instead (stage script inserts font-reset per dispatch).
            if os.environ.get("DSCE_BREAK_DELAY") == "1":
                # VALIDATION: the dyncall-wedge bug (delay inside a dispatched channel
                # script) -- the user's "sound dies + game runs 1.5x" failure
                f.write(f".channel {chan(n)}\n"
                        f"    fontinstr {font_selector[font_id]}, FONTANY_INSTR_SFX\n"
                        f"    ldlayer 0, LAYER_{cname(n)}\n"
                        f"    delay {ticks + 1}\n"
                        f"    fontinstr 0, FONTANY_INSTR_SFX\n    end\n\n"
                        f".layer LAYER_{cname(n)}\n"
                        f"    notedv SF{font_id}_{cname(n)}, {ticks}, 127\n"
                        "    end\n\n")
                continue
            f.write(f".channel {chan(n)}\n"
                    f"    fontinstr {font_selector[font_id]}, FONTANY_INSTR_SFX\n"
                    f"    ldlayer 0, LAYER_{cname(n)}\n    end\n\n"
                    f".layer LAYER_{cname(n)}\n"
                    f"    notedv SF{font_id}_{cname(n)}, {ticks}, 127\n"
                    "    end\n\n")
    # shim map header: soundBits key -> mint ordinal (foley: player bank 0x9D0+ord;
    # voice: voice bank appended after its last id -- resolved by the staging script,
    # which knows the real base ids; here we emit ordinals + name table)
    with open(hdr, "w") as f:
        f.write("/* GENERATED by gen_mario_sfx.py -- SM64 soundBits -> minted SFX ordinal.\n"
                " * Rendered from 00_sound_player.s exactly as SM64 performs each id. */\n")
        f.write(f"#define DSCE_MSFX_COUNT {len(order)}\n")
        f.write("/* key = (bank << 8) | soundID; val = ordinal into the minted table */\n")
        f.write("static const unsigned short sDsceMsfxKeys[] = {\n")
        pairs = [((bank << 8) | sid, name)
                 for (bank, sid), name in sorted({**MINTS, **SHARES}.items())
                 if name in rendered]
        for key, name in pairs:
            f.write(f"    0x{key:04x}, /* {name} */\n")
        f.write("};\n")
        f.write("static const unsigned short sDsceMsfxIds[] = {\n")
        for key, name in pairs:
            pre = "NA_SE_VO_DSCE_" if name.startswith("vo_") else "NA_SE_PL_DSCE_"
            f.write(f"    {pre}{name.upper()},\n")
        f.write("};\n")
        f.write(f"#define DSCE_MSFX_MAP_LEN {len(pairs)}\n")
    print(f"minted {len(manifest)} sounds ({len(pairs)} id mappings); misses: {misses}")


if __name__ == "__main__":
    main()
