# Mario's Mask Alpha 0.11.4

Alpha 0.11.4 improves Mario's world interactions and fixes soundtrack switching.

## Changes

- Mario's ground pound now also triggers beneficial interactions that normally require Goron Link's ground pound, including flipping Snappers.
- Fixed Mario music routing so special Mario cues no longer borrow unrelated Majora's Mask sequence identities.
- Fixed music sometimes going silent instead of restarting after changing the music or sound-font setting.
- Fixed the wrong theme playing after defeating the King of Ikana with Mario music and instruments enabled.
- Added a browser builder at https://msmfai.github.io/marios-mask/ so the three required ROMs can be patched locally without installing an app.

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

Choose the **MariosMaskBuilder** file for your platform under **Assets**, or use the browser builder.

## Build Mario's Mask

1. Open the browser builder, or extract and open **MariosMaskBuilder**.
2. Choose your own USA Nintendo 64 ROMs for *Super Mario 64*, *Ocarina of Time* (NTSC 1.1), and *Majora's Mask*.
3. Choose Mario's outfit colour and where to save the new game.
4. Click **Build Mario's Mask**.
5. Open `Marios-Mask.z64` in an N64 emulator or flash cart.

Both builders combine the three game files locally on your device. On Android, install the APK, choose the ROMs through Android's document picker, and save the finished ROM directly to your device. The app requests no network or broad storage permission.
