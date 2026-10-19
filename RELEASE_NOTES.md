# Mario's Mask Alpha 0.18.0

## What's changed

- Mario no longer tiptoes or turns on the spot with an original N64 controller whose stick doesn't rest exactly in the centre. His stick now gets the same deadzone as Super Mario 64 (GitHub #60).
- Taking off the Brother's Mask while wearing the Blast Mask no longer freezes the game.
- Taking off the Brother's Mask after wearing the Great Fairy's Mask no longer crashes the game.
- Music no longer cuts out when the background music, a second track and a fanfare all need their instruments at the same time.
- The retired Peach statue in the Laundry Pool, left over from an early alpha, has been removed.
- Mario now uses much less memory when you are not playing as him: his movement code, drawing code and animations are loaded only while he is around, and his animations and power-up textures stream from the cartridge the way Link's do. This is a large change under the hood. If you see a crash, freeze or missing animation that wasn't there in 0.17.0, please report it.

## Get the game

Use the [web patcher](https://msmfai.github.io/marios-mask/) with your own ROMs. All processing happens locally on your device. Download `MariosMaskBuilder-web.html` below for the same patcher offline.

Bring your own NTSC Nintendo 64 ROMs for Super Mario 64, Majora's Mask, and Ocarina of Time. Any NTSC revision of Ocarina of Time may be used.

## Downloads

| Platform | Asset |
|---|---|
| Browser / offline HTML | `MariosMaskBuilder-web.html` |
| Windows | `MariosMaskBuilder-windows-x86_64.zip` |
| Mac with Apple Silicon | `MariosMaskBuilder-macos-apple-silicon.zip` |
| Intel Mac | `MariosMaskBuilder-macos-intel.zip` |
| Linux | `MariosMaskBuilder-linux-x86_64.tar.gz` |
| Android | `MariosMaskBuilder-android.apk` |

## Known issues

This is still an alpha. Please include your mod version when reporting bugs.
