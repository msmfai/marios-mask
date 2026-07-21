# DSCE firehose — debug-ROM diagnostic telemetry → ClickHouse

Judgement-free debugging: when something dies, the answer is a query over captured
evidence. Selected debug ROMs (`make mod DEBUG=1 …` → `out/*-debug*.z64`) carry a tagged event
ring; a lossless drain spools it; an ingester loads runs into a persistent ClickHouse
ontology. **Non-debug ROMs are byte-identical** (verified: shipped md5 `a06b8ea…` with
every firehose block compiled out; the one md5 change vs the pre-goal baseline was the
*removal* of a leftover always-on debug log — bisected to the byte).

## Compile-time groups

Logging is not one monolith. These Make variables accept exactly `0` or `1`; release
builds force all of them to zero:

| setting | linked evidence | principal runtime cost |
|---|---|---|
| `DBG_AUDIO` | audio pipeline snapshots, pointer/load guards, per-op sequence flight recorder | high |
| `DBG_GAMEPLAY` | Mario action/sound-resolution and Song-of-Healing state events | low |
| `DBG_LEGACY` | older 48-byte string-tag ring, mirrored to the firehose | medium/redundant |
| `DBG_HUD` | GfxPrint timing/arena/action overlay | rendering only |

The firehose ring itself exists only when legacy, audio, or gameplay evidence is
enabled. Audio trace state and the 32 KiB sequence-flight ring exist only when
`DBG_AUDIO=1`. The linked-symbol audit both requires enabled groups and rejects disabled
groups. A custom combination is encoded in its ROM filename as `-debug-dbgLAGH`.

## On-ROM ring (`dsce_hook.c`, `#if DSCE_DBG_FIREHOSE`)
1024 × 32-byte records `{seq, domain, flags, tag, tick, playFrame, a,b,c,d}` (32KB BSS,
debug only). `Dsce_Fh(domain, tag, a,b,c,d)` is a plain struct write — no game-side I/O.
Overflow is detected by the drain via seq gaps and reported as explicit drop records.

| domain | table | contents |
|---|---|---|
| 0 | legacy_log | every `Dsce_Log` mirrored (tag = first 2 chars) |
| 1 | audio_requests | the WHOLE game's SfxRequest stream (polled from `sSfxRequests` — non-static, no patch) |
| 2 | seqplayer_state | per frame: seq-player-0 flags, full font bytes of SFX channels 0-2/13-15, channel-enabled bits, **active synth-note count**, count of live notes with fontId 41 |
| 3 | heap_levels | permanent + cache pool fill vs size, per frame |
| 4 | audio_pipeline | audio-task clock, AI buffer lengths/status, RSP scheduler state, and nonzero PCM energy sampled from uncached RDRAM |
| 5 | kernel_actions | SM64 action transitions (action, prev, forwardVel) |
| 6 | kernel_sounds | every SM64 soundBits→msfx resolution, hits AND misses (tag 1 = miss) |

## Capture
**Headless (standalone mupen):** the inputbot plugin drains per input-poll —
`CT_FH_ADDR=<gDsceFhHead va> CT_FH_RING=<gDsceFhRing va> CT_FH_DIR=<dir>` (vas are in
the ROM's `.va` sidecar) → `<dir>/<ts>.fh.jsonl`. Measured 0 drops at ~20k events/run.

**RetroArch (read-only recorder):** the canonical debug launcher drains the ring with
RetroArch's built-in `READ_CORE_MEMORY` network command. It never writes core memory,
patches the frontend/core, or saves/restores machine state:
```
tools/run_debug_release.py [out/mm-dsce-test-laundry-pool-nomask-debug.z64]
```

The launcher writes `config/core-options.opt` for an isolated pure-interpreter +
CXD4 LLE + one-thread/high-sync Angrylion run, disables external per-game overrides,
and records both executable hashes. This changes no emulator/core binary and may run
more slowly than performance-oriented global settings.
It reads every second, so overlapping 1024-record windows are de-duplicated into
one session timeline. A separate debug-only 1024-record audio-thread flight recorder
captures channel/player opcodes, every sequencer write into sequence RAM, overlapping
audio DMAs, sequence loads, and the first invalid pointer/load/index. It freezes on the
first fault; the launcher then prints that enough evidence has been captured. Close
RetroArch normally (or press Ctrl-C in the launcher) to
ingest and diagnose. The older manual savestate extractor remains supported:
```
tools/firehose_from_savestate.py ~/Library/.../states/<rom>.state --symbols <rom>.z64.va
tools/firehose_ingest.py <state>.fh.jsonl --rom <debug rom> --notes "RA failure"
```
Yields the last ~1024 events (~10s of per-frame audio state) before the save.

### Strict per-run tree
Everything is private, regenerable, and covered by `out/` in `.gitignore`:
```
out/debug-runs/<YYYY-MM-DDTHH-MM-SSZ>/
├── run.json                     input identity + completion status
├── config/                      exact RetroArch append config + argv
├── database/clickhouse/         this run's only ClickHouse-local database
├── firehose/
│   ├── captures/                raw read-only RDRAM telemetry windows
│   └── session.fh.jsonl         de-duplicated whole-session timeline
├── sequence-flight/
│   ├── captures/                raw sequencer instruction-history windows
│   └── session.jsonl            de-duplicated history, frozen at first fault
├── logs/                        RetroArch, capture, ingest, and diagnosis logs
├── reports/                     diagnosis.txt + diagnosis.json
└── symbols/                     exact .va/.map sidecars used for extraction
```
The launcher refuses filenames without a debug suffix, missing `.va` sidecars, and
sidecars without a firehose ring. The sequence-flight stream is optional and captured
only when the ROM was built with `DBG_AUDIO=1`. It therefore cannot turn logging on
for the ordinary release ROM by accident.

## Ingest + query
`tools/firehose_ingest.py <spool> --rom <rom> [--notes …] [--db <path>]` → per-domain MergeTree
tables (including `sequence_flight`) + a tagged `runs` row (run_id, ts, rom, git rev, notes, events, drops) at
`out/firehose/clickhouse` (clickhouse local; nix-sourced binary). Canned post-mortems:
```
tools/firehose_query runs                      # all captured runs
tools/firehose_query audio-death <run>         # synth-death verdict + font-41 note evidence + requests after death
tools/firehose_query pools <run>               # pool highwater vs budget
tools/firehose_query fonts-at <run> <frame>    # channel fonts/enables/notes around a frame
tools/firehose_query actions <run>             # kernel action history
tools/firehose_query last-audio <run>          # last 50 events across audio domains
```
For an isolated automatic run, add
`--db out/debug-runs/<timestamp>/database/clickhouse` before the query name. The
launcher also runs `firehose_diagnose.py`, which reports synth death, font-41 load
failure, permanent-pool pressure, unhealthy SFX sequencer state, a stalled ROM audio
thread, zeroed PCM output, and a stuck N64 AI FIFO. Diagnosis follows the ROM path in
order and does not modify or presume a fault in the emulator.

## Validation: GATE PASSED (run 246be0b43601 vs control 38ab45c5d59b)
Bug #1 (total sfx mute: the unbudgeted permanent font) reintroduced via
`DSCE_BREAK_POOL=1`, captured headless, and pinned by the canned query with no guessing:
`audio-death` returns **"MARIO FONT NEVER SOUNDED: minted requests flowed but no
font-41 note ever played -- font load failure; check pools + permanent budget"** on the
broken run (kernel_sounds hits present, max(notes_font41)=0 across the whole run;
`pools` shows the un-budgeted permanent pool) and "mario font healthy (font-41 notes
observed)" on the healthy control. The fault mechanism is identified from evidence.

## Confirmed cutout/speed-up root cause
The failing builds appended the generated Mario channels after `.endseq Sequence_0`.
The object therefore contained bytes through `0xCB0E`, while `Sequence_0_End` and the
audio table still advertised the vanilla `0xC740` bytes. The permanent audio heap
loaded only that advertised span, then allocated Soundfont 2 at the same RAM addresses
as the omitted Mario-channel tail. The runtime byte word captured at sequence offset
`0xC99D` (`1B04A2FD`) is the corresponding Soundfont 2 data, byte for byte.

When the sequencer dispatched a Mario sound in that tail it interpreted soundfont data
as opcodes, eventually issued an invalid sample load, and stopped the N64 audio thread.
PCM then drained to silence; without audio-buffer back-pressure, frontend presentation
ran faster. This is a ROM construction error, not an emulator fault.

`stage-mario-sfx.sh` now inserts the generated channels before `.endseq`. The patched
audio-sequence macros make the assembler reject sequence sections outside an open
`.startseq/.endseq` pair. Every build then runs `check_sequence_span.py` across all 123
sequence objects and fails unless each exported Start/End/Size triple agrees with the
complete object `.data` size. This second layer also catches raw data directives that
bypass the structural macros. For older captured runs,
`firehose_diagnose.py --map ...` emits the critical finding
`rom_audio_sequence_span_excludes_mario_sfx` directly from their linker map.

The font reset, nonzero note duration, immediate return from dyncalled channel scripts,
and permanent-pool budget remain independent audio invariants. Their break switches are
only for throwaway diagnostic validation: `DSCE_BREAK_FONT`, `DSCE_BREAK_DUR`,
`DSCE_BREAK_DELAY`, and `DSCE_BREAK_POOL`.
