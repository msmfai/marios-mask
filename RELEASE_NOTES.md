# Mario's Mask Alpha 0.11.0

Alpha 0.11.0 promotes 7 tested changes from the private release train.

## Changes

- Implement configurable Mario attack priority.
- Refine Southern Swamp Mario traversal.
- Merge configurable Mario attack priority.
- Ignore local nested worktrees.
- Fix expanded Mario attack kernel expectations.
- Document reviewed Termina memory substitutions.
- Resume dirty public release checkpoints.

## Validation

- The uninstrumented 8 MiB release build passed the exhaustive vanilla-MM area-memory comparison.
- The downloaded builder is required to reproduce the approved ROM byte-for-byte from both supported Majora's Mask input forms.

## Known issues

- Some unusual Mario dialogue, quest, and cutscene combinations remain early
  alpha paths. Keep save states as well as normal in-game saves.
- Many opposite-game instrument arrangements are still automatically converted
  rather than fully hand-authored.
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
2. Choose your own USA Nintendo 64 ROMs for *Super Mario 64* and *Majora's Mask*.
3. Choose where to save the new game.
4. Click **Build Mario's Mask**.
5. Open `Marios-Mask.z64` in an N64 emulator or flash cart.

The builder combines your two game files locally on your computer.
On Android, install the APK, choose both ROMs through Android's document picker,
and save the finished ROM directly to your device. The app requests no network
or broad storage permission.
