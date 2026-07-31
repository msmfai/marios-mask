# Mario's Mask Alpha 0.8.2

Alpha 0.8.2 is an urgent memory-stability release.

## Fixed

- Fixed a serious failure mode where N64 memory exhaustion could make the game
  silently refuse to load actors, objects, or other assets, leaving visible
  parts of areas missing without reporting an error.
- Optimised Mario-specific data residency so dialogue, animations, and the
  Peach statue and object data stay in ROM or load only when needed. This
  restores memory for affected vanilla area content, including the trees by
  the Astral Observatory and the Part-Time Employee in Termina Field.
- Critical load failures now stop with a visible fatal-load report instead of
  silently continuing with missing content.
- No vanilla level content was removed to obtain these memory savings.

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
