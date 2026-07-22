# Mario's Mask

Play *Majora's Mask* as Mario, with his movement, jumps, attacks, voice, and
animations from *Super Mario 64*.

[Screenshot: Mario standing in Clock Town beside Tatl, with the normal Majora's Mask HUD visible]

**[Download the latest Mario's Mask alpha](https://github.com/msmfai/marios-mask/releases)**

## What is this?

Mario's Mask is an early crossover mod for the Nintendo 64 version of *Majora's
Mask*. The Brother's Mask contains the spirit of a hero from another world. Put it
on and Link becomes Mario while you continue exploring Termina and playing through
*Majora's Mask*.

Mario can run, punch, swim, ground-pound, and use his familiar jumps. The alpha also
includes a ready-made `Link` save after the opening tutorial, so you can start more
quickly.

[Screenshot: The Brother's Mask in the pause-menu inventory, with its description visible]

[Screenshot: Mario performing a recognizable move in Termina, such as a triple jump or ground-pound]

## What you need

- Your own NTSC-US *Super Mario 64* ROM.
- Your own NTSC-US *Majora's Mask* ROM.
- An N64 emulator or flash cart for the finished game.

The builder never uploads your ROMs and does not need Python, WSL, a compiler, or an
internet connection.

## Make the game

1. Open the [Releases page](https://github.com/msmfai/marios-mask/releases).
2. Download the builder for your computer:
   - **Windows:** `MariosMaskBuilder-windows-x86_64.zip`
   - **Mac with Apple Silicon (M1/M2/M3/M4):** `MariosMaskBuilder-macos-apple-silicon.zip`
   - **Older Intel Mac:** `MariosMaskBuilder-macos-intel.zip`
   - **Linux:** `MariosMaskBuilder-linux-x86_64.tar.gz`
3. Extract the download and open **MariosMaskBuilder**.
4. Choose your *Super Mario 64* ROM.
5. Choose your *Majora's Mask* ROM.
6. Choose where to save the new game, then click **Build Mario's Mask**.
7. Open `Marios-Mask.z64` in your emulator or flash cart.

[Screenshot: The Mario's Mask Builder with both ROMs chosen and the Build Mario's Mask button visible; hide personal folder names]

`.z64`, `.v64`, `.n64`, `.zip`, and `.gz` inputs work. *Majora's Mask* can be
internally compressed or decompressed.

### If your computer blocks the app

- **Mac:** Control-click the app, choose **Open**, then choose **Open** again.
- **Windows:** If SmartScreen appears, choose **More info**, then **Run anyway**.
- **Linux:** Extract the whole archive before opening the builder.

## Alpha warning

This is an early alpha. Back up your save files and expect some rough edges. If you
find a problem, [open an issue](https://github.com/msmfai/marios-mask/issues) and say
what you were doing when it happened. Do not upload or attach either ROM.

Project source is released under [GPL-3.0](LICENSE).
