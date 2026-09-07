# Mario's Mask Alpha 0.12.0

Alpha 0.12.0 is a substantial Mario gameplay and stability release.

## Changes

- Mario now behaves as a compact fifth transformation form, improving mask removal, re-equipping, scene changes, and memory use without replacing Link.
- Water recovery has been rebuilt across normal swimming, poison water, enemy knockback, Deku-flower entries, and room transitions.
- Death now returns you as Mario when appropriate, plays only the short Mario death jingle, and no longer stalls the game-over flow across music configurations.
- Hole and grotto transitions, block pushing, carried-object throws, climbing recovery, stairs, and several native-player handoffs now work correctly as Mario.
- Mario can fight the Gekko and Snapper miniboss more reliably, receives stronger Big Octo knockback, and retains his intended attack behavior around world objects.
- Major rewards use Mario's star celebration; minor chest rewards no longer sink him into the floor.
- Mario-specific dialogue and presentation have been expanded in shops, Southern Swamp, Deku Palace, owl-statue saves, the Pictograph interaction, and other form-sensitive scenes.
- The Deku Palace monkey performance now shows Mario's instrument and uses the intended sounds.
- Camera handoffs at doors and difficult rooms are more stable.
- Mario music routing, the short death sequence, Hoot Hoot arrangement, Deku Palace and Woodfall soundfonts, credits, and post-credits audio have been corrected.
- Canonical red Mario is preserved in the bridge, Song of Healing, Peach, and Lens of Truth presentations instead of inheriting the playable outfit palette.
- Owl statues now support reusable persistent saves during the alpha, can be activated by Mario's attacks, and recognize the bearer of the fist beyond this world.
- The builder now offers six independent Mario colour controls for his cap and shirt, overalls, gloves, shoes, skin, and hair. The canonical green and original red presets remain one-click choices.
- The browser builder now includes labelled Player 1 and Player 2 N64 controller diagrams, alternate-camera guidance, and the four music/instrument combinations.

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

Choose the **MariosMaskBuilder** file for your platform under **Assets**, or use
the browser builder at https://msmfai.github.io/marios-mask/.

## Build Mario's Mask

1. Open the browser builder, or extract and open **MariosMaskBuilder**.
2. Choose your own NTSC Nintendo 64 ROMs for *Super Mario 64*, *Ocarina of Time*, and *Majora's Mask*.
3. Choose Mario's colours and where to save the new game.
4. Click **Build Mario's Mask**.
5. Open `Marios-Mask.z64` in an N64 emulator or flash cart.

All builders combine the three game files locally on your device. No copyrighted game asset is distributed with the patcher. On Android, install the APK, choose the ROMs through Android's document picker, and save the finished ROM directly to your device. The app requests no network or broad storage permission.
