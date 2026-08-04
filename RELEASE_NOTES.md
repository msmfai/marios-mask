# Mario's Mask Alpha 0.9.1

Alpha 0.9.1 is a major native-systems refactor focused on stability. Mario now
uses more of Majora's Mask's existing form, bottle, music, and audio-resource
paths instead of maintaining parallel special cases.

## Improved

- Mario's form and underwater bottle interactions now route through the native
  mask and Zora-manager paths. This keeps ordinary Mario swimming and Metal
  Mario's underwater walking aligned with the game's established state rules.
- Mario music variants are native audio assets streamed from ROM on demand,
  reducing permanent RAM pressure and keeping transitions under the normal
  sequence-player lifecycle.
- Music and soundfont cache eviction is now asset-aware. Changing Roads,
  Borrowed Voices, combat music, and area transitions share the same ownership
  rules instead of independently invalidating live audio resources.
- Native ocarina song storage has been prepared for the two Mario songs without
  relying on the retired takeover shortcut.
- Audio-resource invariants are documented beside the code so future changes
  fail close to the architectural boundary instead of surfacing as intermittent
  missing music or a dead audio engine.

## Validation

- The uninstrumented 8 MiB release build matched vanilla Majora's Mask across
  all 453 base entrance/spawn cases and all 918 day/time schedule cases.
- The release sweep recorded no out-of-memory failures, resource-limit errors,
  critical headroom cases, fragmentation flags, or unexpected actor changes.

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
