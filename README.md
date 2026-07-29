# Mario's Mask

**Play *Majora's Mask* as Mario.**

![Mario in Termina](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/hero.png)

Mario's Mask brings Mario's movement, attacks, voice, animations, and playful
physics from *Super Mario 64* into the world and adventure of *Majora's Mask*.
Termina, its story, three-day cycle, quests, dungeons, and characters remain at
the heart of the game—you explore them with a very different hero.

**[Download Mario's Mask](https://github.com/msmfai/marios-mask/releases/latest)**

> **Early alpha:** back up your saves and expect some rough edges.

## Find the Brother's Mask

The Brother's Mask contains the spirit of a hero from another world. Find the
stone Peach in Clock Town's Laundry Pool and play the Song of Healing nearby to
receive it. Put on the mask to become Mario; remove it to return to Link.

![Link meeting the stone Peach](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/peach-statue.png)

![The Brother's Mask in the inventory](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/brothers-mask.png)

With fresh save data, File 1 is named `Link` and begins on Day 1 just after the
opening tutorial. File 2 begins a completely new game. The prepared file is
included for convenience—you can still play the introduction whenever you want.

## Move through Termina like Mario

![Mario running through Clock Town](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/clock-town.png)

Mario can run, punch, kick, crouch, crawl, swim, climb ledges, long-jump,
side-flip, triple-jump, wall-jump, and ground-pound. His momentum, aerial
control, rebounds, falls, voice, and animation make familiar places feel new and
open unexpected routes through them.

Movement is adapted to *Majora's Mask* rather than pasted into it unchanged.
Mario respects the world's walls, floors, voids, water, hazards, moving actors,
and scene transitions while retaining the expressive movement that defines
*Super Mario 64*.

![Mario swimming underwater](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/mario-swimming.png)

Mario's camera has three zoom levels, including a close native-style view. His
magic ability opens up exaggerated movement, wall climbing, and the strength to
move or break heavy obstacles.

## Discover classic power-ups

The Wing, Metal, and Vanish Caps are hidden around Termina. Their movement,
appearance, music, and timers follow Mario across the places where their power
remains active.

Mario can also glide with a carried Cucco, climb the Great Bay Turtle's shell,
deflect attacks with a punch, and find other traversal routes designed around
his abilities.

## Change the music

Two secret songs shown on the sign beside the Laundry Pool bell control the
soundtrack. One switches between *Majora's Mask* music and mapped *Super Mario
64* compositions. The other switches the instrument palette. The settings are
independent, giving each save file four persistent soundtrack configurations.

The alpha uses a mixture of hand-authored arrangements and automatic instrument
conversions. More arrangements will be refined as development continues.

## Fight the creatures of Majora's Mask

Mario has specific interaction logic for the full catalogue of enemies and
bosses. They keep their original attack patterns and hitboxes, while Mario
responds with appropriate stomps, rebounds, punches, knockback, damage,
invulnerability, grabs, burning, freezing, or other Mario-style behavior.

![Mario caught in Dinolfos fire breath](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/fire-breath.png)

Fire can send Mario running with smoke trailing behind him. Ice traps him in a
block. Underwater, air drains his health and surfacing restores it a little at a
time. When Mario loses his last heart, his own defeat sequence replaces Link's.

This is still an alpha, so unusual encounters and scripted fights may need more
play-testing.

## Use the world and its items

Mario can open Termina's doors, talk to its characters, collect rewards, activate
switches, open chests, pick up and throw objects, and carry creatures such as
Cuccos. Handle-operated and automatic doors preserve their different behavior
while using Mario-appropriate movement.

![Mario carrying a bomb in Termina Field](https://github.com/msmfai/marios-mask/releases/download/v0.8.0/selected-mario-bomb-jump.png)

Usable items are adapted to Mario's controls. Bombs and other throwables can be
carried and thrown. The bow and Hookshot fire in the direction Mario faces, with
a deliberately physical recoil. Native item sounds remain alongside Mario's
reactions.

Mario can play songs and participate in the conversations and quest systems
needed to continue the adventure. Where the original game expects Link's form,
the mod aims to provide a Mario-compatible route without changing how ordinary
Link plays.

Version 0.8.0 expands Mario-aware conversation and quest routing across Termina.
Some of these paths remain experimental and can still soft-lock, so save before
trying long quest sequences as Mario.

## Build your game

Bring your own USA Nintendo 64 versions of *Super Mario 64* and *Majora's Mask*.
The builder combines them locally on your computer.

1. [Open the latest release](https://github.com/msmfai/marios-mask/releases/latest).
2. Under **Assets**, download **MariosMaskBuilder** for Windows, macOS, or Linux.
3. Extract it and open **MariosMaskBuilder**.
4. Choose both game files and where to save the result.
5. Click **Build Mario's Mask**.
6. Open the new `Marios-Mask.z64` in an N64 emulator or flash cart.

Raw `.z64`, `.v64`, and `.n64` files work, as do `.zip` and `.gz` archives.

Having trouble opening the builder?

- **Mac:** Control-click it, choose **Open**, then choose **Open** again.
- **Windows:** Choose **More info**, then **Run anyway** if SmartScreen appears.
- **Linux:** Extract the whole archive before opening it.

Found a bug? [Tell us what happened](https://github.com/msmfai/marios-mask/issues/new/choose)
and keep both game files private.

## About the builder

Mario's Mask is free software under [GPL-3.0](LICENSE). This repository contains
the standalone builder, not a playable game. Its documented
[two-input recipe format](patcher/recipe/FORMAT.md) builds locally from the two
files you select.

## What alpha means

Mario's Mask will remain in alpha until it is ready for stronger stability and
compatibility promises.

- New versions may be released without extensive testing.
- Save compatibility between alpha versions is not guaranteed.
- Soft-locks are expected. Keep save states as you play, in addition to normal
  in-game saves.
- Some content is placeholder or procedurally generated.
- Features, controls, and balance may change between versions.

When the project reaches beta, development will split into stable and nightly
releases. Save games will remain compatible or receive a conversion path, and
procedurally generated content will be restricted to local development builds.

> [!NOTE]
> Due to the rapidly changing features of the mod during alpha, the README and
> release notes are machine-generated directly from the code to ensure they stay
> up to date.
>
> Rest assured, this is a human-led project.
