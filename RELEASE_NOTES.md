# Mario's Mask Alpha 0.14.0

## What's changed

- **Brother's Mask now follows the game's native transformation flow more closely.** Removed extra cutscene-waiting behavior and stale transformation state that could interfere with changing forms.
- **Switch directly between Mario and your other transformation forms.** Using Brother's Mask as Goron, Zora or Deku Link now selects Mario correctly. Using it as Mario removes it correctly, even when he is wearing another mask.
- **More consistent mask controls and pause-menu behavior.** Brother's Mask now follows transformation-mask availability rules, including greyed-out C-buttons, underwater restrictions and the Moon. The pause menu also correctly protects the button assigned to your current Mario form.
- Mario's transformation now has its own first-use/skip tracking, without sharing unrelated dialogue progress flags. Existing saves may show the full transformation once before it becomes skippable again.
- Corrected which form's ceiling clearance is checked when using Brother's Mask. Interrupted transformations no longer leave a delayed Mario scream queued after the transformation has ended.
- Cap boxes use normal visibility culling again, avoiding unnecessary drawing when they are out of view.

Mario still stays equipped after death. His movement, abilities, appearance and ordinary wearable-mask support are unchanged.

## Get the game

Use the [web patcher](https://msmfai.github.io/marios-mask/) with your own ROMs. All processing happens locally on your device. The self-contained `MariosMaskBuilder-web.html` is also available below for offline use.

Bring your own NTSC Nintendo 64 ROMs for *Super Mario 64*, *The Legend of Zelda: Majora's Mask*, and *The Legend of Zelda: Ocarina of Time*. Any NTSC revision of *Ocarina of Time* may be used.

## Downloads

| Platform | Asset |
|---|---|
| Browser / offline HTML | `MariosMaskBuilder-web.html` |
| Windows 10 or 11, 64-bit | `MariosMaskBuilder-windows-x86_64.zip` |
| Mac with Apple Silicon | `MariosMaskBuilder-macos-apple-silicon.zip` |
| Intel Mac | `MariosMaskBuilder-macos-intel.zip` |
| 64-bit Linux | `MariosMaskBuilder-linux-x86_64.tar.gz` |
| Android 8.0 or newer, 64-bit | `MariosMaskBuilder-android.apk` |

## Known issues

- Some unusual Mario dialogue, quest, and cutscene combinations remain early alpha paths. Keep save states as well as normal in-game saves.
- Many opposite-game instrument arrangements are still automatically converted rather than fully hand-authored.
- Save compatibility is not yet guaranteed between alpha releases.
