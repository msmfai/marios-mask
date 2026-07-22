# Mario's Mask v0.1 alpha

Turn into Mario and explore Termina with movement, jumps, attacks, voice, and
animations adapted from *Super Mario 64*.

[Screenshot: Mario standing in Clock Town beside Tatl, with the normal Majora's Mask HUD visible]

This is a small standalone builder, not a game download. You supply your own NTSC-US
*Super Mario 64* and *Majora's Mask* ROMs; the builder combines them locally and does
not upload anything.

## Which download do I choose?

| Your computer | Download |
|---|---|
| Windows 10 or 11, 64-bit | `MariosMaskBuilder-windows-x86_64.zip` |
| Mac with an M1, M2, M3, or M4 chip (Apple Silicon) | `MariosMaskBuilder-macos-apple-silicon.zip` |
| Older Mac with an Intel processor | `MariosMaskBuilder-macos-intel.zip` |
| 64-bit Linux | `MariosMaskBuilder-linux-x86_64.tar.gz` |

## How to use it

1. Extract the download and open **MariosMaskBuilder**.
2. Choose your two NTSC-US ROMs.
3. Choose where to save the new game.
4. Click **Build Mario's Mask**.
5. Open the resulting `Marios-Mask.z64` in your emulator or flash cart.

The downloads are only 3–4 MB and contain no Python runtime, WSL environment,
compiler, decomp tree, or ROM.

## Start on Day 1

When the game starts with fresh save data, File 1 contains a convenience save named
`Link` immediately after the opening tutorial. Choose it to start at the beginning of
Day 1, or use the empty File 2 to begin a normal new game. The prepared file can be
erased or replaced like any other save.

This is an early alpha, so back up your save. Please report problems on the
[Issues page](https://github.com/msmfai/marios-mask/issues), but never attach a ROM.
