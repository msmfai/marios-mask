# Mario's Mask Alpha 0.12.1

Alpha 0.12.1 is a focused bug-fix release for progression and Enhanced Mode.

## Fixes

- Drinking Chateau Romani no longer makes Mario's elemental powers stop working after their first three-shot charge. Fire, ice, and light powers can now be activated repeatedly while Chateau's unlimited magic is active.
- Mario can once again grab and push Mikau to shore, allowing the Zora Mask quest to be completed while wearing the Brother's Mask.
- The Enhanced Mode sign in Peach's Castle now correctly tells players to press **C-Up** instead of the old **R** control.

## Browser builder

Build locally in your browser at https://msmfai.github.io/marios-mask/. A self-contained `MariosMaskBuilder-web.html` is also available under Assets. All ROM processing happens locally on your device.

## Validation

- The uninstrumented 8 MiB release build passed the exhaustive vanilla-*Majora's Mask* area-memory comparison.
- The release runtime suite covers Mikau's native push interaction and repeated elemental-power activation after drinking Chateau Romani.
- The downloaded builder must reproduce the approved release ROM byte-for-byte from both supported *Majora's Mask* input forms.

## Builder requirements

The builder asks for your own NTSC Nintendo 64 ROMs for *Super Mario 64*, *The Legend of Zelda: Majora's Mask*, and *The Legend of Zelda: Ocarina of Time*. Any NTSC revision of *Ocarina of Time* may be used.

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
| Any modern desktop browser (single offline file) | `MariosMaskBuilder-web.html` |

Choose the **MariosMaskBuilder** file for your platform under **Assets**, or use the browser builder linked above.

## Build Mario's Mask

1. Open the browser builder, or extract and open **MariosMaskBuilder**.
2. Choose your own NTSC Nintendo 64 ROMs for *Super Mario 64*, *Ocarina of Time*, and *Majora's Mask*.
3. Choose Mario's colours and where to save the new game.
4. Click **Build Mario's Mask**.
5. Open `Marios-Mask.z64` in an N64 emulator or flash cart.

All builders combine the three game files locally on your device. No copyrighted game asset is distributed with the patcher. On Android, install the APK, choose the ROMs through Android's document picker, and save the finished ROM directly to your device. The app requests no network or broad storage permission.
