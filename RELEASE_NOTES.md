# Mario's Mask Alpha 0.9.2

Alpha 0.9.2 replaces Mario's old post-step speed-up with a single dimensional
conversion from Super Mario 64's 30 Hz physics to Majora's Mask's 20 Hz player
loop. Movement is now corrected where velocity, acceleration, turning, damping,
and collision are integrated instead of moving Mario a second time after the
native action step.

## Improved

- Ground, air, swimming, Metal Mario water movement, poles, flight, shells,
  whirlpools, and tail-spinning now share the same 20 Hz physics model.
- Linear and angular velocities use the 30-to-20 Hz time ratio; acceleration
  and gravity use its square; friction and damping preserve their real-time
  decay.
- Mario turns more like his Super Mario 64 counterpart, and swimming responds
  more naturally without a separate movement-speed workaround.
- Collision now resolves the converted movement directly. The removed
  corrected-endpoint pass can no longer push Mario beyond the position the
  action's own collision step accepted.

## Validation

- Source and architecture contracts enforce the dimensional conversion and
  reject restoration of the retired post-step speed knobs.
- Fresh acquisition and kernel fixture ROMs passed the no-mask boot check and
  all 717 Mario interaction assertions.
- The uninstrumented 8 MiB release build is required to pass the exhaustive
  vanilla Majora's Mask area-memory comparison before publication.

## Known issues

- Some unusual Mario dialogue, quest, and cutscene combinations remain early
  alpha paths. Keep save states as well as normal in-game saves.
- Many opposite-game soundfont arrangements still use programmatic instrument
  conversions rather than fully hand-authored arrangements.
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
