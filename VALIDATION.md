# Brother's Mask N64 — validation checklist (joint debug pass)

Canonical builds:
- **mm-dsce-test.z64** — boots straight into Termina Field with the mask on **C-LEFT**.
  Use this for everything below (emulator or EverDrive).
- **mm-dsce.z64** — the real mod: normal boot. THE BROTHER'S MASK is earned at the
  LAUNDRY POOL: a stone Peach statue stands on the walkway — stand near her and play
  the SONG OF HEALING (ocarina required). She heals into the floating mask; touch it,
  it lands on C-LEFT, equip to transform. Pause masks page shows its icon+name.

Build and launch the acquisition test through the canonical path:

```sh
tools/build_from_roms.sh --laundry-healing SM64_US.z64 MM_US.z64 \
  out/mm-dsce-test-laundry-pool-nomask-debug.z64
tools/run_debug_release.py
```

For an interactive performance-oriented debug run, omit the expensive audio opcode
recorder while retaining action/sound/quest events:

```sh
gmake mod TESTBOOT=1 TB_SCENE=LAUNDRY_POOL TB_GRANT_MASK=0 DEBUG=1 \
  DBG_AUDIO=0 DBG_GAMEPLAY=1 DBG_LEGACY=0 DBG_HUD=0
tools/run_debug_release.py \
  out/mm-dsce-test-laundry-pool-nomask-debug-dbg0010.z64
```

Use the full default debug build when diagnosing audio or sequence failures. The
strict RetroArch CPU/RSP/RDP profile has a substantial independent performance cost,
so compare ROM logging overhead only under the same core profile.

Headless boundary investigation uses the real C-left mask transformation, never the
test-only L+R+Z takeover. It disables the input bot's automatic unsticking hop and
writes one ignored, timestamped evidence tree per invocation:

```sh
tools/headless_wall_probe.py --oob
tools/headless_wall_probe.py --geometry-oob
tools/headless_wall_probe.py --geometry-oob --only late_jump_east_wall_spawn
```

`--oob` runs 24 cardinal/corner walk, jump, long-jump, and dive sweeps.
`--geometry-oob` runs 24 walk-up-then-pressure cases against six dry points derived
from `Z2_ALLEYCollisionHeader_0028A8`. Each scenario retains rules, raw samples, wall
push counters, actor/action lifecycle transitions, emulator logs, and a summary under
`out/headless-wall-runs/<timestamp>/`. Water entries are classified separately and do
not count as invisible-wall failures.

The launcher isolates a pure-interpreter + CXD4 LLE + Angrylion accuracy profile for
the run. It does not modify RetroArch or its core. Do not substitute Glide64/GLideN64
for hardware-safety validation; see `docs/N64_INVARIANTS.md`.

## The mask
- [ ] C-LEFT equips → Link becomes green Mario instantly (no cutscene)
- [ ] C-LEFT again → back to Link, controls normal
- [ ] Walk through a loading zone while transformed → Mario persists
- [ ] Save/inventory intact after several equip cycles

## The look
- [ ] Green cap/shirt/arms (Luigi-fied), blue overalls, correct skin/hair
- [ ] Gold **Triforce** on the cap's white circle (look at him head-on)
- [ ] Readable in dark interiors (shops) and bright field, feet ON the ground

## The moveset (all SM64-faithful)
- [ ] Walk/run accel + skid; A jump; A again = double; again = triple somersault
- [ ] Long jump (Z+A while running) — should cover big distance
- [ ] Ground pound (Z mid-air), dive (B while running) + belly slide
- [ ] Ledge grab (walk off slow / jump at a ledge)
- [ ] Swim (Laundry Pool or any water): A strokes propel; wall-slide along walls
- [ ] Southern Swamp west poison strip → bounce off with a hurt reaction
- [ ] Float at a clean water surface after damage → hearts refill
- [ ] L+R+B (debug hit) → backward knockback tumble, brief invulnerability

## The camera (new — feel pass)
- [ ] Transformed: camera hangs back SM64-style (wider + higher than MM's default)
- [ ] D-pad LEFT/RIGHT orbits around Mario; releases drift back behind him
- [ ] D-pad UP/DOWN steps the zoom (close / normal / far)
- [ ] Unequip: MM's normal camera returns without a snap or black frame
- [ ] Cutscenes/dialogue: camera behaves vanilla (no fighting)

## The foley (new — materials by ear)
- [ ] Footsteps change with the surface: grass field vs stone bridge vs wood dock
- [ ] Jump push-off + landing thud match the surface
- [ ] Wall bonk thumps; ground pound lands with a heavy bound
- [ ] Swimming strokes + a splash when plunging into water

## The voice (calibrate by ear — mappings are one-liners to fix)
- [ ] Jump grunts (yah/wah/hoo rotation) on jumps
- [ ] Bigger shout on long jump / triple jump
- [ ] "Hoo-hoo!" on double jump
- [ ] Hurt gasp on the L+R+B hit
- [ ] Fall scream on a big drop (West gate bridge → field works)
- [ ] Unmasked Link still sounds like Link (only Fierce Deity's bank was donated)

## Hardware only (NTSC N64 + Expansion Pak)
- [ ] Ordinary release ROM completes acquisition, transform, scene load, unmask/remask,
      pause/save/reload, repeated jump/voice/foley, and swamp-swim paths
- [ ] Native pacing remains stable; no hitching, crackle, missing sound, visual RDP
      corruption, freeze, or spontaneous reset
- [ ] Optional conservative stress run with the debug ROM: HUD `TICK MAX <= 8000us`
      and `ARENA MIN >= 50000` after ~10 minutes (debug logging itself adds overhead)

An emulator pass does not waive this hardware gate.

Report anything off — say WHAT you did, WHAT you saw/heard, and WHERE (scene). Voice
mis-mappings, colors, offsets, and physics feel all have single-file fixes standing by.
