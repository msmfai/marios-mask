# Mario's Mask v0.1.0-alpha.7

Play *Majora's Mask* as Mario, with movement, attacks, swimming, voice, and animations
adapted from *Super Mario 64*.

![Mario caught in Dinolfos fire breath](https://raw.githubusercontent.com/msmfai/marios-mask/v0.1.0-alpha.7/docs/screenshots/fire-breath.png)

## Doors, items, and solid objects

Mario can now use ordinary doors without facing backwards or briefly turning into
Link. He can pick up and throw native objects, including Cuccos, with a carry pose
tuned for his shorter body.

Bombs and Bombchus use the same native pickup and throw lifecycle. The bow and
hookshot hip-fire in Mario's facing direction, keep their native sound effects, and
give Mario a brief recoil that can be used as movement tech.

This release also adds Mario-aware collision for more actors, moving solids, boulders,
barriers, and puzzle targets, plus stability fixes for combat and room transitions.
Native Link behavior is unchanged.

This is still an early alpha and has not been exhaustively play-tested. Back up your
saves and expect rough edges.

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
