# Mario's Mask Alpha 0.8.0

Version 0.8.0 makes Mario a more complete resident of Termina, adds four ways to hear
the soundtrack, introduces a hidden classic power-up, and improves exploration,
camera control, conversations, and transitions.

## Added

- Four persistent music configurations: Majora's Mask or mapped Super Mario 64
  compositions, each using either game's instrument palette.
- A classic power-up hidden somewhere in Termina.
- A hybrid Mario camera with three zoom levels and a close native-style view.
- Magic movement mode, wall climbing, heavy-object strength, punch deflection,
  and expanded traversal interactions.
- Broader Mario-aware dialogue, quest, traversal, and carrying support.

## Improved

- Mario behaves more consistently across rooms, cutscenes, items, doors,
  targeting, Tatl, and other scripted interactions.
- Context actions are easier to activate, including while swimming and using
  lock-on interactions.
- Save initialization preserves existing files and only supplies the optional
  post-tutorial `Link` file when no save data exists.
- Game assets and music data load more selectively, reducing scene-transition
  memory pressure.

## Fixed

- Mario's form, power-up, music, carried objects, and interaction state survive
  scene changes more reliably.
- Dialogue, doors, targeting, items, and scripted interactions return control
  more consistently.

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

The small standalone builder combines your two game files locally on your computer.

With fresh save data, File 1 starts as `Link` on Day 1 after the tutorial.
File 2 begins a completely new game.

This is an early alpha, so back up your saves. Report problems on the
[Issues page](https://github.com/msmfai/marios-mask/issues) and keep both ROMs private.
