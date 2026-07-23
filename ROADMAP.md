# Brother's Mask (N64 ROM) — roadmap

The pipeline turns the user's two baseroms (SM64 + MM) into one modded MM ROM where
wearing the Brother's Mask makes Link play as green (Luigi-fied) Mario with faithful
SM64 physics, body, animations, and voice. What's DONE is proven by the headless suite
(`make test`, ~5s), the 8-scene matrix, and the visual pixel check.

## Done (see STATE.md for the engineering log)
- ✅ Pipeline: patch+stage+build+revert over pristine `.work/mm`; per-ROM .va sidecars;
  testboot scene/spawn knobs; tuning.yaml (the PC ImGui options as a file)
- ✅ Physics: full SM64 moveset incl. swim, hazards (poison bounce), water heal, KB
- ✅ Body: SM64 model in MM's F3DEX2, 20-part skeleton, 151 anims, ground lift
- ✅ Look: Luigi green + gold Triforce cap emblem (YAML-driven, staged, no tracked edits)
- ✅ Voice: 5 voice families via the Fierce Deity donor sample bank
- ✅ The mask: equipping it runs MM's REAL transformation cutscene (raise + white flash +
  scene reload) via a dedicated PLAYER_FORM_MARIO (67 form-arrays extended) + Mario's scream
  at the transform-voice cue; then the Mario takeover spawns. Toggle back to human = MM's own
  transform-back. (Regression-free vs baseline; end-to-end transform pending user play-test —
  the headless harness can't run the cutscene. See STATE.md.)
- ✅ Test rig: headless emulator, telemetry, savestate cache, metamorphic suite,
  Termina matrix, visual assert

## Open work — one goal file each (n64/goals/, see goals/README.md)
The Mac play stack now works (RetroArch Metal arm64 + mfi + arm64 core; memory
`mac-n64-controller-emulator`), so the validation gate is unblocked.

Gate: validation (the user's court)
- [U] goals/01-validation-play-pass.md — USER-ONLY: play -> I fix findings (assistant can't play)
- [U] goals/02-voice-calibration.md    — USER-ONLY: ear-check (assistant can't hear)
- [U] goals/03-everdrive-hardware.md   — USER-ONLY: EverDrive HUD numbers (assistant can't run hardware)

## Next up (ordered)
1. ~~**The Brother's Mask as a proper item**~~ ✅ DONE — ITEM_MASK_BROTHERS 0xCD, HMS
   backpack-cameo icon (green), name texture, floating plaza pickup in South Clock Town.
   (Remaining polish: pause-hover name visual check; a give-cutscene/chest instead of
   the floating pickup; the shared-slot tradeoff means it displaces the Troupe Leader's
   Mask if you own both.)
2. ~~**Terrain foley**~~ ✅ DONE — bank-0 bridge -> MM surface-aware foley
   (walk/jump/land + surface material, body-hit, bonk, swim, splash); SPIN/TWIRL
   swooshes left silent (no clean MM analog).
3. ~~**Phase 2b body polish**~~ ✅ DONE — blink cycle, hand states (fists/open/peace),
   torso tilt + head turn, root Y-bounce. (Cap-off variant + eye directions remain
   unused -- no reachable states need them.)
4. ~~**Camera pass**~~ ✅ DONE — SM64 follow cam (PC-ported math, post-Camera_Update
   hook) + D-PAD orbit/zoom (vanilla MM never uses the d-pad). Ocarina offsets N/A
   (singing is PC-only).
5. ~~**Green Mario, properly**~~ ✅ DONE — Link's tunic green (24,88,22), matched by
   side-by-side renders; icon + billboard tinted to match; Triforce + Troupe Leader
   untouched.
6. ~~**Scene-ambient lighting blend**~~ ✅ DONE — per-frame Lights1 rescale from
   envCtx light settings; dims correctly in interiors.
7. ~~**Song of Healing acquisition (the Peach statue method)**~~ ✅ DONE — stone Peach
   at the Laundry Pool walkway; Song of Healing within earshot heals her into the mask
   pickup; plaza freebie retired. (Polish ideas: the PC's ring/fade cutscene states,
   a textbox, statue pedestal.)

Stretch features
- [x] goals/04-interaction-depth.md    — DONE: real AC_HIT knockback (colChkInfo.damage + attacker yaw) + Deku-flower launch; debug combo now testboot-only
- [x] goals/05-object-group-actions.md — DONE: standing-B punch combo live; grab/throw dormant (no MM objects)
- [x] goals/06-per-form-arrays.md      — DONE: Mario dialogue identity table (textId->Mario line, mask-gated) + form audit
- [x] goals/07-perf-headroom.md        — DONE: swamp p50 5136->3769us, ratchet 16000->13000, bit-identical

Polish
- [x] goals/08-acquisition-polish.md   — heal RITE DONE; textbox/pedestal/name-hover CLOSED as deferred polish

## Research
- [x] Cross-game metamorphic rig (goal 10, INLINE goal 2026-07-08) — `make test-xgame`:
  the real SM64 ROM as Mario's oracle. GREEN: R1 jump action-chain identical, R2 ascent
  ballistics BIT-EXACT, airtime 21==21 ticks. First true finding: idle->sleep onset
  ~88 ticks vs SM64's ~930 (F1, open). Full research doc: docs/XGAME_METAMORPHIC.md.

## Housekeeping
- [x] goals/09-pc-housekeeping.md — probes STRIPPED; committing the PC mod CLOSED as the user's branch/remote decision (can't build-verify here)
- Keep this file + STATE.md + the goals/ checkboxes updated at each goal boundary

- [x] **XTEST — totalistic headless testing (2026-07-08):** matched corridor arena in both
  games, full-moveset cross-game parity green (12 scenarios, 38 actions bit-exact), F3/F4
  kernel fixes shipped, F2 speed-multiplier decision pending. `make test-xtest`.
- [x] **XTEST completion (2026-07-09):** pending tail authored (22/22, 54 actions,
  variants B/C), F1 closed (F4 was the root cause), F2 decided+verified
  (test-xtest-shipped green under the declared 1.5x transform), R3 sound report green
  (families+ticks aligned, all scenarios). `make test-xtest{,-shipped,-sounds}`.
- [x] **DEBUG firehose (2026-07-09):** DSCE_DEBUG event ring + lossless drain +
  ClickHouse ontology + canned queries + RA savestate extractor; break switches for the
  three audio bugs; byte-identical gate green (bisected). Real-failure capture is the
  RetroArch black-box path (user reproduces, saves state, one command ingests).
