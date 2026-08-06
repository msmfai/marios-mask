# Mario's Mask Alpha 0.10.0

Alpha 0.10.0 gives Mario a proper instrument and improves how his Super Mario
64 animations look and sound inside Majora's Mask.

## What's new

- Mario now plays songs with Guru-Guru's hand-cranked music box instead of an
  ocarina. He holds it between both hands and uses its familiar accordion voice.
- Mario squashes with each note while you play and while a completed song is
  played back to you.
- Mario's animation poses are now smoothed for Majora's Mask's frame rate, so
  movement looks faster and more fluid.
- Heel turns no longer make Mario briefly face backwards before returning to
  the correct direction.
- Mario's accordion sound no longer leaks into Peach's Castle doors or other
  unrelated effects.
- The Happy Mask Salesman's Mario-specific conversation now pauses on
  "So what exactly..." before "Are you?", accompanied by his uncanny laugh.

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
