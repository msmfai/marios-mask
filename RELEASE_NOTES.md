# Mario's Mask Alpha 0.11.2

Alpha 0.11.2 fixes a collision regression introduced in Alpha 0.11.1 and adds new Mario interactions, minigame support, and presentation improvements.

## Changes

- Fixed the Alpha 0.11.1 collision regression that could let Mario slip beneath low banks and fall through poisoned swamp water when pushed against a wall.
- Mario keeps the Alpha 0.11.1 tight-passage fix, including access to the Deku Palace entrance, without making his world collision wider or taller than Human Link's.
- Added an *Ocarina of Time* NTSC 1.1 ROM dependency so the builder can derive Ocarina of Time assets locally, including the complete Talon model.
- The public builder now lets you choose green Mario, original red Mario, or a custom outfit colour.
- Cancelling Mario's bow flight with the Hookshot now leaves the ridden arrow flying on its original trajectory and lets Mario recover quickly.
- Mario can now carry and hip-fire the Pictograph Box in the direction he is facing, or throw it for one point of damage. Hitting a Giant Octorok with it defeats the Octorok and takes a picture from the impact.
- Added a dedicated Mario state for the Southern Swamp boat tour: Mario stays aboard, can jump, turns relative to the boat with the analogue stick, retains D-pad camera control, and keeps the Pictograph Box ready.
- Beaver races now show Mario's hearts and magic and restore his health when a race starts or retries.
- Shell-riding Mario now brings Leevers out sooner and keeps them above ground long enough to hit, and a shell impact can instantly defeat Takkuri with extended hit-stop.
- Fixed Mario retaining an old head lean in unrelated poses.
- Fixed Mario's loading and cutscene pose alignment, including sinking or facing sideways before control returns.
- Fixed the back texture of the Brother's Mask.
- Fixed Mario inheriting water movement in the dry climb to Stone Tower Temple.
- Fixed Mario's cap appearing in his hand during unrelated presentation states, including after burning.

## Builder requirements

The builder now asks for your own USA ROMs for *Super Mario 64*, *The Legend of Zelda: Ocarina of Time* (NTSC 1.1), and *The Legend of Zelda: Majora's Mask*. The additional Ocarina of Time input supplies its required assets locally; no copyrighted game asset is distributed with the patcher.

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
