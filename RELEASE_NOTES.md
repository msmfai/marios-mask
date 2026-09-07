# Mario's Mask Alpha 0.12.0

Alpha 0.12.0 is the largest Mario gameplay update since the mask was introduced. It makes Mario a more complete fifth transformation, adds several new ways to play, and substantially improves progression and stability throughout Majora's Mask.

## Major changes

- Mario is now integrated as a compact fifth transformation form. Link remains fully playable, while Mario now follows the game's native rules for loading, mask changes, conversations, doors, items, cutscenes, shops, deaths, scene changes, and other shared actions.
- Mario's appearance is now configurable. Choose the canonical **L(ink) Is Real** green palette, classic red Mario, or independently customise his cap and shirt, overalls, gloves, shoes, skin, and hair.
- Mario's controls have been reorganised: **R** now Z-targets, **C-Up** activates Enhanced Mode, **Z** keeps Mario's crouch and ground-pound controls, the other C buttons remain items, and the D-pad controls the camera. A second controller's stick also works as an alternate analogue camera.
- Enhanced Mode now surrounds Mario with gold sparkles and uses pipe-appearance and pipe-disappearance sounds when switched on and off, replacing the old green glow. Enhanced Mode remains focused on traversal rather than extra combat damage.
- Mario can now use Deku Sticks as throwable weapons. They preserve momentum, can be lit from either end, ignite torches and webs, and burst on impact while burning.
- Town and Swamp Shooting Galleries now have a dedicated Mario mode. Mario aims from a fixed third-person position and uses unlimited thrown Deku Sticks, fireballs, and light balls while the original targets, timers, scoring, and rewards remain intact.
- Riding Epona as Mario now has its own deliberately ridiculous solution: Mario ties himself to the horse and becomes a ragdolling, X-eyed, six-damage projectile. Tatl comments the first time it happens.
- Mario can now wear ordinary masks without leaving Mario form, create the three persistent heavy Mario/Talon statues needed for the Elegy of Emptiness, complete the Swordsman's School with Mario moves, and activate the large Gossip Stones with the appropriate transformation songs.
- Major rewards now use Mario's SM64 star dance and peace sign, with corrected positioning and recovery afterwards.
- Owl Statues now provide reusable persistent saves during the alpha instead of forcing a return to the title screen. Mario can activate them with his attacks and receives Mario-specific “bearer of the fist beyond this world” dialogue.

## Progression, combat, and interaction

- Mario can enter and complete more Deku Palace progression, including form-aware guard conversations and the captive monkey's Sonata of Awakening sequence.
- Mario can damage the mounted Gekko without making the Snapper itself universally vulnerable; defeating Gekko on the turtle now completes the encounter correctly.
- Giant Octoroks now throw Mario far enough clear of the water to prevent repeated-hit softlocks.
- Mario once again pushes and pulls puzzle blocks through the native block solver.
- Carrying and throwing grass, Cuccos, jars, and other held actors now uses the native item lifecycle with Mario presentation, including moving and airborne throws.
- Water ownership and recovery have been rebuilt for ordinary swimming, poison water, enemy knockback, Deku-flower water entries, surfacing, and room transitions.
- Falling through holes and entering or leaving grottos no longer strands Mario in an invalid Link state.
- Mario now recovers correctly after being hit while climbing, animates on stairs, and retains the proper form across death and respawn.
- Shops, doors, bottles, Deku Nuts, the Hookshot, Pictograph interactions, ocarina use, item rewards, and other native actions now hand control to and from Mario more reliably.
- The Southern Swamp guide can give Mario the Pictograph Box before Koume is rescued, supporting Mario's existing Pictograph interactions and Giant Octorok route.

## Presentation, dialogue, and audio

- Canonical red Mario is now kept separate from the playable palette for the bridge encounter, Song of Healing, Peach scenes, and other story appearances. The Lens of Truth also reveals Mario's original colours regardless of the selected outfit.
- Mario-specific dialogue has been expanded and rewritten across shops, Southern Swamp, Deku Palace, the Pictograph guide, Swordsman's School, Owl Statues, and other form-sensitive conversations.
- Mario now visibly performs with his instrument during the captive monkey's Sonata lesson, and the scene uses the intended instrument dialogue and sounds.
- Music routing has been corrected across rewards, bosses, shells, deaths, scene changes, and credits. Death uses only the short Mario jingle; the Hoot Hoot melody is restored; and the Deku Palace and Woodfall Mario-instrument arrangements have been refined.
- The ending and post-credits sequence now advance correctly with alternate music settings. Mario receives his own final run, footsteps, and jump presentation, followed by Peach's Castle exterior ambience and “Thank you so much for playing my game” at **THE END**.
- Peach's Castle and the Metal Cap Course now use the same SM64-to-Majora's-Mask scale as Mario, while preserving their established placement in the world.
- Camera ownership is more stable around doors, native cutscenes, combat, and troublesome rooms.

## Builder and documentation

- The browser builder has been redesigned as a minimal self-contained page with the complete six-part Mario palette editor.
- The builder now includes labelled Player 1 and Player 2 N64 controller diagrams, the alternate-camera controls, both soundtrack-toggle songs, and all four Zelda/Mario music and instrument combinations.
- The downloadable `MariosMaskBuilder-web.html` is the same self-contained patcher used by the project website and performs all ROM processing locally.

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
