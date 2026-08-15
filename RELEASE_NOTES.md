# Mario's Mask Alpha 0.11.0

Alpha 0.11 is a major gameplay update. It adds Metal Mario, elemental powers, a
new way to use the bow, new world content, and a broad pass over Mario's combat,
movement, and interactions.

## Metal Mario and the Cavern of the Metal Cap

- A new portal in Clock Tower leads to the Cavern of the Metal Cap.
- Pressing the green switch unlocks Metal Cap boxes placed around Ikana.
- Metal Mario is invincible, has his proper heavy movement sounds and music,
  sinks to the floor underwater, and can punch while walking on the seabed.
- Metal Mario can smash underwater obstacles, including the wooden barriers at
  Pirates' Fortress. Enhanced swimming can also break through them at speed.
- Reflected sunlight now charges Metal Mario's body. His next attack releases
  the stored light, allowing him to activate mirrors, sun switches, sun blocks,
  and light-sensitive enemies.

## Fire, Ice, and Light powers

- Fire, Ice, and Light Arrows now give Mario a matching elemental power instead
  of putting him into Link's bow stance.
- Each activation uses the normal arrow and magic cost, changes Mario's powered
  appearance, and charges his next three attacks.
- Punches, kicks, and other attacks launch elemental projectiles. Ground pounds
  create an elemental burst around Mario.
- Fire and Ice projectiles bounce through the environment before bursting;
  Light attacks retain their native puzzle and enemy interactions.

## Mario's new bow

- The ordinary Hero's Bow now works like a Mario cannon: hold the item button to
  charge, aim Mario, then release to launch him along the shot line.
- Draw strength controls launch speed, from a short hop to a full cannon blast.
- Mario, the bow, arrow, pulled string, camera, sounds, smoke, and impact effects
  now follow one shared aim direction.
- The Great Fairy's Sword is now a throwable Mario weapon with its own flight,
  impact, and landing presentation.

## Combat overhaul

- Enhanced Mode is now a traversal power rather than a damage upgrade. Mario's
  ordinary attacks retain their full strength without consuming magic.
- Normal punches deal 3 damage. Movement attacks such as jump kicks, slide
  kicks, and dives deal 6.
- Mario can smash expected breakables such as rocks, snowballs, pots, and jars
  without Enhanced Mode.
- Ground pounds now carry Goron ground-pound force, including flipping Snappers
  and activating enemies and objects that respond to Goron impacts.
- Bosses accept Mario's attacks across their active vulnerable bodies instead
  of demanding Link-sized precision. Mario can, for example, attack Goht across
  its body rather than trying to hit one exact point.
- Mario's attacks now win against ordinary enemy body contact. Clearly visible
  weapons and hazards such as swords, blades, large horns, lasers, and spikes
  still beat him.
- Enemy and boss attack surfaces were reviewed individually, making punches,
  kicks, dives, lunges, and ground pounds far more consistent.

## World and traversal changes

- Mario can stand and run on Southern Swamp lily pads, climb onto them directly
  from the water, and still jump for a brief moment after leaving an edge.
- A well-aimed lunge defeats the giant Octoroks, opening a Mario-style shortcut
  through the swamp.
- A new Snapper encounter has been added to Termina Field.
- Song of Storms now drains and refills the moat outside Peach's Castle.
- Mario can climb cleanly over the top of ladders that previously trapped him
  in a rapid climbing loop.
- Gold Skulltula tokens are easier for Mario's larger body to collect.
- Diving into a Cucco grabs it without hurting it or provoking a Cucco attack.
- Mario's movement timing has been retuned for Majora's Mask's 20 Hz gameplay,
  improving action windows and animation timing throughout his move set.

## Presentation and progression fixes

- The Brother's Mask now uses a native Mario-faced model and properly aligned
  inventory art, without the Circus Leader's tear effect.
- Playing Elegy of Emptiness as Mario now creates a solid Talon statue. Its
  collision forms safely and moves Mario out of the way instead of overlapping
  him.
- Mario's animation root motion has been restored, so his pelvis and feet move
  correctly during idle animations instead of pumping through the floor.
- Mario's fire animation no longer restores the missing M emblem on his cap.
- Mario's death now completes its Bowser laugh and transition without playing
  Majora's Mask's Game Over music or hanging on a black screen.
- Woodfall's Gekko and Snapper interactions have been restored for Mario.

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
