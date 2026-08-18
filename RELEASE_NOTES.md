# Mario's Mask Alpha 0.11.3

Alpha 0.11.3 corrects the Brother's Mask artwork.

## Changes

- Fixed the Brother's Mask portrait mapping so Mario's cap logo is no longer stretched and his face texture no longer bleeds onto the cap visor.
- Fixed the mask's rear wood texture bleeding onto front-facing edges.

## Builder requirements

The builder asks for your own USA ROMs for *Super Mario 64*, *The Legend of Zelda: Ocarina of Time* (NTSC 1.1), and *The Legend of Zelda: Majora's Mask*. The Ocarina of Time input supplies its required assets locally; no copyrighted game asset is distributed with the patcher.

## Known issues

- Some unusual Mario dialogue, quest, and cutscene combinations remain early alpha paths. Keep save states as well as normal in-game saves.
- Many opposite-game instrument arrangements are still automatically converted rather than fully hand-authored.
- Save compatibility is not yet guaranteed between alpha releases.

## Choose your download

| Your computer | Download |
|---|---|
| Windows 10 or 11, 64-bit | `MariosMaskBuilder-windows-x86_64.zip` |
| Mac with Apple Silicon (M1 or newer) | `MariosMaskBuilder-macos-apple-silicon.zip` |
| Mac with an Intel processor | `MariosMaskBuilder-macos-intel.zip` |
| 64-bit Linux | `MariosMaskBuilder-linux-x86_64.tar.gz` |
| Android 8.0 or newer, 64-bit | `MariosMaskBuilder-android.apk` |

Choose the **MariosMaskBuilder** file for your platform under **Assets**.

## Build Mario's Mask

1. Extract the download and open **MariosMaskBuilder**.
2. Choose your own USA Nintendo 64 ROMs for *Super Mario 64*, *Ocarina of Time* (NTSC 1.1), and *Majora's Mask*.
3. Choose Mario's outfit colour and where to save the new game.
4. Click **Build Mario's Mask**.
5. Open `Marios-Mask.z64` in an N64 emulator or flash cart.

The builder combines your three game files locally on your computer.
On Android, install the APK, choose the ROMs through Android's document picker,
and save the finished ROM directly to your device. The app requests no network
or broad storage permission.
