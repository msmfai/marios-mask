# Cross-game metamorphic tests — the SM64 ROM as Mario's oracle (goal 10)

North star (2026-07-08): *"as if Mario jumped into a painting and landed in Termina"* —
Mario behaves IDENTICALLY to SM64, with only common-sense Termina adaptations. This rig
makes that falsifiable: the real SM64 ROM runs headless beside the mod, both stream
tick-indexed MarioState, and a comparator demands equality under the known transforms.

Run it: `make test-xgame` (needs `out/mm-dsce-test.z64` + the sm64 decomp built once).
Tool: `tools/xgame_test.py`. First green: 2026-07-08.

## Answers to the research questions (all MEASURED, not assumed)

### 1. SM64 boot-to-gameplay
**None needed.** The decomp-built ROM (`.work/sm64/build/us/sm64.us.z64`) boots STRAIGHT
into playable gameplay: Mario is `ACT_IDLE` on the castle grounds at **tick 4**, no
title/file-select/intro. (The built ROM is NOT byte-identical to the baserom — 8.5M vs
8.4M, different md5 — which is why its own `sm64.us.map` must be, and is, the address
source.) Determinism: two identical runs produce **bit-identical telemetry CSVs**.
No savestate cache needed at these lengths (a 900-tick run ≈ seconds headless).

### 2. Arena matching
SM64 spawn = castle grounds apron, floorH exactly 0, flat. Mod testboot = Termina Field
apron, floor 205.92 (SM64 units), flat. Absolute floor heights DIFFER, so total jump
airtime depends on floor only at the descent end — measured **21 ticks vs 21 ticks**
anyway. The exact-match tier therefore uses **floor-independent windows** (ascent
ballistics, action chains) rather than trying to equalize arenas. A matched-height
arena hunt is unnecessary for v1.

### 3. Telemetry parity
Both sides read the SAME `struct MarioState` layout — the mod runs the vendored SM64
kernel, and its state (`gDsceMarioState`, made non-static, exported in the `.va`
sidecar) is in SM64 units. So no /4.29 conversion appears anywhere in the comparator:
internal-state comparison is exact by construction. The plugin gained `CT_TICK_ADDR`:
one CSV row per sim-tick increment (tick,x,y,z,yaw,action,floorH; %.9g floats).
CSV is sufficient for v1; the JSONL rig is not needed for kinematics.

**Tick sources (the load-bearing detail):**
- SM64: `gGlobalTimer` (map). Polls == ticks (1:1), rule frames == ticks.
- Mod: `gDsceTelemetry.frame` (VA+4) — the TAKEOVER's counter, incremented AFTER the
  sandbox tick. Sampling on `gDscePlayFrame` (increments at Play_Update START) captured
  MID-FRAME state: split deltas (31.4/48.3 instead of 42/38). Post-tick counters only.
- Mod poll:tick ≈ 7:1 with a boot offset — rules are authored per side; the comparator
  aligns by ACTION EDGE (first ACT_JUMP), never absolute ticks.

### 4. Relations — status
- **R1 action-stream: PASSING (exact).** Jump chain JUMP → JUMP_LAND → JUMP_LAND_STOP
  → IDLE identical; airtime 21 == 21 ticks.
- **R2 kinematics: PASSING (bit-exact).** Pristine-idle jump ascent deltas
  `38,34,30,26,22,18,14,10,6,2` — identical arrays both games. Same C code, same
  emulated MIPS FPU, zero tolerance. Scenario control matters: SM64 jump vel =
  `42 + 0.25*forwardVel`, so ANY residual walk contaminates it (we measured +0.064/tick
  from a 0.256 leftover; a wall-press wobble gave −0.19). The scenario jumps from
  verified pristine idle.
- **R3 sound events: REPORT TIER GREEN (2026-07-09).** `make test-xtest-sounds`: both
  sides log every kernel play_sound (SM64: a staged 48-byte ring in external.c drained
  by the plugin; mod: Dsce_Log("snd") with the sandbox tick). Compared as FAMILIES
  (the shim's own buckets — act.JUMP/LAND/STEP/BODYHIT/SPLASH/SWIM/BONK/HEAVY,
  voi.YAH_WAH_HOO/YAHOO_WAHA_YIPPEE) because the kernel adds rand%3/rand%5 id
  variation that is not cross-game deterministic. Result: ALL 12 A-variant scenarios
  MATCH — families AND relative ticks aligned (3-19 events each, 134 total). The
  kernel requests the right sounds at the right ticks; remaining north-star sound work
  is entirely in the MM-side renderer (what the foley adapter plays), not the stream.
- **R4 invariances: NOT BUILT** (rotation/mirror symmetry).
- **R5 anim-stream: NOT BUILT** (animIds 1:1 by construction).

### 5. Comparator design
`tools/xgame_test.py`, standalone (invoked by `make test-xgame`), action-edge aligned,
prints PASS/FAIL per relation with both arrays on failure. Known divergences are
reported as `[FINDING]` XFAIL lines — the harness stays green while the divergence is
tracked here. Tolerance policy: the flat tier is EXACT; slope/water tiers (future) get
per-relation epsilons declared next to the scenario.

## Findings (true divergences the rig has caught)

### F1 — idle→sleep onset: mod ~88 ticks vs SM64 ~930 ticks (CLOSED 2026-07-09, fixed by F4)
Mario fell asleep ~10x too fast. Root cause was **F4** (not the suspected camera
scaffolding): act_idle's head-turn cycles are ANIM-GATED, and the stale-assist anim
bug fast-forwarded every fresh animation, so the idle fidget cycle raced through its
count. After the verbatim geo_update_animation_frame port, measured onset is 934
(sm64) vs 931 (mod) absolute with **phase durations exactly equal** (idle→
START_SLEEPING and START_SLEEPING→SLEEPING both bit-identical). S11 is now a hard
equality gate on the calibration streams; the old XFAIL is deleted.

## XTEST — totalistic moveset parity on a matched arena (goal XTEST, GREEN 2026-07-08)

Goal 10 compared one jump on unmatched terrain. XTEST removes the terrain caveat: ONE
arena, defined once in `tools/gen_xtest_arena.py`, compiled into BOTH games.

- **SM64 side**: `make sm64-xtest` stages the generated collision over the south (area 1)
  slot of the SM64+Clock Town tree (backup/restore; RAM symbols asserted stable) ->
  `out/sm64-xtest.z64`.
- **Mod side**: `make mod TESTBOOT=1 XTEST=1` -> `out/mm-dsce-test-xtest.z64`. The
  find_floor/ceil/water/walls shims route to a VERBATIM vendored copy of SM64's own
  surface algorithms (read_surface_data normal math, vertex1-height sort with stable
  ties, s16 truncation, 78-unit buffers, first-hit-break, X/Z wall projection) over the
  same triangles. The hook auto-spawns the takeover at the SM64 spawn point and seeds
  MarioState with the exact constants. `DSCE_XTEST=0` compiles ALL of it out — the
  shipped ROM carries none of this.
- **Arena (v4, "the corridor")**: every feature ON the walking line heading -z from
  spawn — flat apron, lava strip (jumpable), water channel (long-jumpable), 51-degree
  slide ramp, ledge step, end wall — because straight cardinal pushes are the one
  heading where both cameras provably align (x stays bit-equal). The rear wall sits
  2700 units behind spawn: closer and SM64's Lakitu gets squeezed into a yaw epsilon.
- **Protocol**: per side, calibration run 1 maps ticks->polls and finds the sleep onset;
  run 2 (walk-and-release probe) measures press AND release input latency empirically.
  Scenarios are authored in burst-relative ticks, compiled per side, and burst EARLY
  (sm64 t0=150, mod t0=75) from settled untouched idle — before SM64's idle camera
  drifts and before the mod's F1 sleep.
- **Relations per scenario**: R1 action-stream equality, R2 ABSOLUTE position equality
  (same spawn + same floors -> bit-equal), RF floorH-stream equality (the continuous
  arena-identity gate, subsuming the grid probe). Anchor at first non-idle action; a
  bounded two-sided slip absorbs constant phase skew; windows stop before F1's tail.
- **Coverage gate**: the union of observed actions must include every CORE mechanic
  (26 ids); PENDING (wall-kick, ledge-grab, side-flip, bonk-KB families — approaches
  not yet authored) is declared and printed, never silently skipped.

`make test-xtest`: **22 checks PASS, 0 failures, 54 distinct actions cross-verified
bit-exact** (2026-07-09; grown from the initial 12/38). Arena variants (one generator):
A "corridor" (travel moves), B "the box" (bonk/wall-kick/ledge family), C "the descent"
(box + 42-degree down-slope — the ONE butt-slide-able orientation this geometry
admits). New tail scenarios S13-S20: side-flip, soft-bonk, wall-kick, ledge-grab +
slow/fast climbs, hard bonk (long-jump at the face), dive-bonk, and the descent
(grab→climb→walk-off→BUTT_SLIDE). Authoring rule: facing-reversing air moves
(side-flip, wall-kick) must RELEASE the stick once the move triggers — the mod's
camera chases the flipped facing instantly while Lakitu doesn't, so a held stick
becomes air-control through different camera yaws; ballistic arcs fly bit-exact.
PENDING is now EMPTY; CORE = 39 mechanic ids.

## Findings (continued — XTEST catches)

### F2 — MarioSpeedMul 1.5 framerate compensation (DECIDED 2026-07-08: KEEP)
The rig's first totalistic run showed every mod walk delta exactly 1.5x SM64's
(14.710/9.807 = 1.5000): `DSCE_MarioSpeedMul 1.5` (tuning.yaml), the 20-vs-30fps
wall-clock feel compensation. **User decision (2026-07-08): KEEP it** — and confine
unavoidable original-vs-framerate tradeoffs to purely stylistic channels; the physics
must FEEL identical. The implementation already satisfies this: the multiplier scales
ONLY the post-step horizontal displacement (dsce_mario_sandbox.c); velocities,
vertical motion, action durations and anim pacing are all native, so jump vel
(42 + 0.25*forwardVel) never sees a multiplied speed.

`make test-xtest-shipped` is the acceptance test for the confinement (GREEN,
2026-07-09). Relations under the DECLARED transform: R2y (y stream bit-exact), R2s
(mod horizontal delta == f32(prev + f32(1.5*sm64_delta)) - prev, exact to a few
position-ULPs — bit-exactness is impossible from positions alone since f32 rounding
is position-dependent and the two sides sit at different coordinates by design), plus
the cumulative |displacement| ratio == 1.5 to 1e-6 over the pre-arrival window.
Geometry arrival (the mod covers 1.5x ground/tick, reaching features sooner — walls
clamp it ticks before any action changes) ends the window and is EVIDENCE, not
failure.

**Post-arrival containment fix (2026-07-21):** the old acceptance window ended at that
first clamp and therefore missed a fault immediately after it: the wrapper multiplied
the already-resolved endpoint, crossing the wall plane (`z=942.48/953.76/948.12` around
a legal `z>=950` center limit). The final scaled candidate now goes through the same
lower/upper-body collision bridge before it is published. S14-S20 additionally gate the
post-arrival position while Mario is below the synthetic box top; wall penetration is a
test failure rather than excluded evidence.

#### F2 evidence table (test-xtest-shipped, 2026-07-09)
| scenario | exact window / aligned | earlier-arrival divergence |
|---|---|---|
| S1 walk-jump-land | 48/125 | +48: sm64 WALKING z=845 vs mod LAVA_BOOST z=372 |
| S2 jump-chain | 45/160 | +45: sm64 TRIPLE_JUMP z=788 vs mod LAVA_BOOST z=281 |
| S3 long-jump | 62/140 | +62: sm64 LONG_JUMP_LAND z=-217 vs mod LONG_JUMP z=-1266 |
| S4 backflip | 100/100 | none — identical over the horizon |
| S5 ground-pound | 90/90 | none |
| S6 punch + crouch-crawl | 155/155 | none |
| S7 dive-rollout | 140/140 | none |
| S8 lava boost | 44/160 | +44: mod boosts 1.5x sooner |
| S9 water plunge-swim-exit | 44/270 | +44: mod reaches lava/water sooner |
| S10 deep-corridor gauntlet | 44/370 | +44: same |
| S12 walk-decelerate | 78/78 | none |
| S13 side-flip | 111/111 | none |
| S14–S20 (walls/ledges/descent) | 31-32/125-250 | geometry clamp: the mod meets the face mid-air ticks earlier |

Reading: stationary/vertical moves are IDENTICAL under the shipped config; traveling
moves obey exactly the declared 1.5x horizontal law until they meet geometry sooner.
The compensation is confined exactly as the design demands.

### F3 — sandbox never set INPUT_UNKNOWN_5 / ABOVE_SLIDE / IN_WATER (FIXED, ships)
Without INPUT_UNKNOWN_5 ("zero movement"), act_walking NEVER exits at zero stick —
forwardVel oscillates around 0 forever instead of braking to idle (player-visible:
Mario jittering in place instead of stopping). The two geometry flags gate slide and
water exits. All three now ported verbatim from update_mario_inputs/geometry_inputs.

### F4 — sandbox anim advance ended anim-gated actions early (FIXED, ships)
The stand-in stepped the stale animFrameAccelAssist even at animAccel==0, but
set_mario_animation resets animFrame (startFrame-1) WITHOUT resetting the assist, so
every fresh animation jumped ahead and anim-gated actions (punch, crouch-start,
pound-land, lava-land) ran ticks short vs the oracle. Replaced with a verbatim port of
geo_update_animation_frame (accel==0 -> animFrame+1; backward + NOLOOP + FLAG_2 paths).
After this one fix, five scenarios flipped to bit-exact simultaneously.

### F5 — shared-edge quarter-step tie-break transient (DOCUMENTED, tolerated)
Crossing a surface-type boundary (lava/apron shared edge), one coordinate wobbles by
~1e-6 for <=3 ticks, then the streams RETURN TO BIT-EQUALITY. An integrating physics
divergence never re-equalizes, so the comparator passes a <=6-tick, <=1e-4 transient
that reconverges exactly, and prints a [NOTE]. Root: find_floor tie order between
same-height triangles differs at exactly-truncated edge points.

## Next relations (effort guesses)
1. R2 full-arc on matched floor heights (spawn a flat test platform at SM64 floor 0 in
   the testboot scene, or compare descent shifted by floor delta) — S.
2. R1/R2 for double/triple-jump chains + long jump + ground pound arc (needs scripted
   run-ups; watch forwardVel purity) — M.
3. R3 sound-event stream (SM64 play_sound tick offsets vs mod foley/voice requests;
   feeds the SM64-sounds north-star work directly) — M.
4. R4 stick-yaw rotation invariance both games (catches camera-yaw mapping bugs) — S.
5. F1 root-cause: instrument act_idle's cycle counters both sides via the JSONL rig — S.
