# Mario's Mask Alpha 0.8.3

Alpha 0.8.3 is a critical memory-stability update. It completes the memory
optimisations begun in Alpha 0.8.2.

## What players will notice

- Areas now have substantially more memory available for their normal scenery,
  characters, enemies, and objects. This fixes cases where content could silently
  disappear, especially in busy areas such as Termina Field with a full inventory.
- Mario's bow, Hookshot, bombs, Bombchus, model, animations, and dialogue continue
  to work normally, but no longer reserve large amounts of memory while unused.
- Serious asset-load failures still stop with a visible fatal-load report instead
  of letting play continue with a partially loaded area.
- No vanilla level content was removed or altered to obtain these savings.

## Technical details

- Mario's Arrow, Hookshot, Bomb, and Bombchu actor overlays now use Majora's Mask's
  normal demand-loading path. Together they return 33,584 bytes to ZeldaArena while
  the tools have no active instances.
- Mario's 133,568-byte model stays uncompressed in ROM and is loaded only while
  Mario is active, trading ROM space and a bounded form-load copy for lower
  permanent RAM use.
- The ROM-resident dialogue and animation data, scene-selective Peach data,
  demand-resident cap objects, and fatal-load diagnostics introduced in Alpha 0.8.2
  remain in place.
- The release build passes 16,013 structural and memory invariants with 3,831,952
  bytes of static arena headroom. The exhaustive scene/layer preflight is also a
  required release gate.

## Known issues

- Some Mario-specific dialogue paths may still fail to return control and
  soft-lock the game.
- Many opposite-game soundfont arrangements still use programmatic instrument
  conversions rather than fully hand-authored arrangements.
- This remains an early alpha. Back up your saves and expect rough edges.

## Choose your download

| Your computer | Download |
|---|---|
| Windows 10 or 11, 64-bit | `MariosMaskBuilder-windows-x86_64.zip` |
| Mac with Apple Silicon (M1 or newer) | `MariosMaskBuilder-macos-apple-silicon.zip` |
| Mac with an Intel processor | `MariosMaskBuilder-macos-intel.zip` |
| 64-bit Linux | `MariosMaskBuilder-linux-x86_64.tar.gz` |

Choose one of the four **MariosMaskBuilder** files under **Assets**.

## Build Mario's Mask

1. Extract the download and open **MariosMaskBuilder**.
2. Choose your own USA Nintendo 64 ROMs for *Super Mario 64* and *Majora's Mask*.
3. Choose where to save the new game.
4. Click **Build Mario's Mask**.
5. Open `Marios-Mask.z64` in an N64 emulator or flash cart.

The builder combines your two game files locally on your computer.
