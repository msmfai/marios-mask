#!/usr/bin/env python3
"""Cheap pre-build guards for Brother's Mask integration contracts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from gen_mask_item_art import png_read


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"content contract failed: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--mm", type=Path, required=True)
    parser.add_argument("--original-logo", type=Path, required=True)
    parser.add_argument("--staged-logo", type=Path, required=True)
    args = parser.parse_args()

    project = args.project
    sandbox = (project / "src/sm64/game/dsce_mario_sandbox.c").read_text()
    actor = (project / "src/ovl_Dsce_Mario/z_dsce_mario.c").read_text()
    dialogue = (project / "src/dsce_mario_dialogue.c").read_text()
    hook = (project / "src/dsce_hook.c").read_text()
    adapters = (project / "src/dsce_adapters.c").read_text()
    makefile = (project / "Makefile").read_text()
    tuning = (project / "tuning.yaml").read_text()
    integration_patch = (project / "patches/0001-dsce-hooks.patch").read_text()
    sram = (args.mm / "src/code/z_sram_NES.c").read_text()

    for token in ("void Dsce_SeedPostTutorialSave", "Dsce_FlashCopyPlayerDataStatus",
                  "Dsce_FlashHasSeedMarker", "Dsce_WriteSeedMarker",
                  "DSCE_FLASH_SECTOR_PAGES 0x80", "DSCE_FILE1_SECTOR_PAGE 0x000",
                  "DSCE_SEED_MARKER_SECTOR_PAGE 0x380", "DSCE_SEED_MARKER_PAGE 0x3FF",
                  "DSCE_SEED_MARKER_OFFSET", "DSCE_FLASH_WRITE_SYNC_ALIGNED",
                  "DsceFlashWriteStartMustBeSectorAligned", "allZero", "allErased", "sLinkName",
                  "threeDayResetCount = 1", "isMagicAcquired = true",
                  "INV_CONTENT(ITEM_OCARINA_OF_TIME) = ITEM_OCARINA_OF_TIME",
                  "INV_CONTENT(ITEM_MASK_DEKU) = ITEM_MASK_DEKU",
                  "SET_QUEST_ITEM(QUEST_SONG_TIME)", "SET_QUEST_ITEM(QUEST_SONG_HEALING)",
                  "WEEKEVENTREG_59_04", "WEEKEVENTREG_31_04",
                  "permanentSceneFlags[SCENE_INSIDETOWER].switch0 = 1"):
        require(token in hook, f"post-tutorial File 1 contract is missing {token}")
    seed_support = hook[hook.index("#define DSCE_FLASH_SECTOR_PAGES"):
                        hook.index("/* [DSCE TESTBOOT]")]
    require(seed_support.count("SysFlashrom_WriteSync(") == 1,
            "seed support must route every write through its compile-time alignment guard")
    require("Lib_MemCpy(&sramCtx->saveBuf[0x2000], &gSaveContext.save, sizeof(Save))" in seed_support,
            "File 1 main and backup must be assembled into one physical flash sector")
    require("DSCE_FLASH_WRITE_SYNC_ALIGNED(sramCtx->saveBuf, DSCE_FILE1_SECTOR_PAGE, "
            "DSCE_FLASH_SECTOR_PAGES)" in seed_support,
            "File 1 seed must use one sector-aligned 0x80-page write")
    require("SysFlashrom_Read(sramCtx->saveBuf, DSCE_SEED_MARKER_SECTOR_PAGE, "
            "DSCE_FLASH_SECTOR_PAGES)" in seed_support,
            "marker update must preserve the complete options-backup sector")
    require("ITEM_MASK_CIRCUS_LEADER" not in
            hook[hook.index("void Dsce_SeedPostTutorialSave"):hook.index("/* [DSCE TESTBOOT]")],
            "seeded post-tutorial file must not grant the Brother's Mask")
    verify_start = sram.index("void func_801457CC")
    verify_end = sram.index("void Sram_EraseSave", verify_start)
    require("Dsce_SeedPostTutorialSave(sramCtx)" in sram[verify_start:verify_end],
            "fresh-Flash verifier must invoke the post-tutorial File 1 seeder")
    new_start = sram.index("void Sram_InitSave")
    new_end = sram.index("void Sram_WriteSaveOptionsToBuffer", new_start)
    require("Dsce_SeedPostTutorialSave" not in sram[new_start:new_end],
            "ordinary New Game creation must remain vanilla")

    require("short* facingYaw, short* visualYaw" in sandbox,
            "sandbox must export separate facing and visual yaw")
    for token in ("sandbox_update_published_facing", "atan2s(dz, dx)",
                  "DSCE_TWIRL_MOVE_EPSILON_SQ", "DSCE_TWIRL_TURN_STEP",
                  "DSCE_TWIRL_REVERSE_FRAMES", "DSCE_TWIRL_EXIT_FRAMES",
                  "twirl_rejects_reverse_spike", "twirl_landing_settles"):
        require(token in sandbox,
                f"movement-led twirl camera contract is missing {token}")
    require("*facingYaw = sPublishedFacingYaw;" in sandbox and
            "*visualYaw = sPublishedFacingYaw +" in sandbox,
            "twirl camera and model must share the filtered movement heading as their stable base")
    require("player->actor.shape.rot.y = facingYaw;" in actor and
            "this->actor.shape.rot.y = visualYaw;" in actor,
            "camera authority must use facing yaw while only Mario's model uses visual yaw")
    for token in ("PLAYER_STATE2_USING_OCARINA", "if (!ocarinaOut)",
                  "Math_Vec3f_Yaw", "DSCE_SingTurnSpeed",
                  "DSCE_MarioOcarinaCamDist", "DSCE_MarioOcarinaCamHeight",
                  "DSCE_MarioOcarinaCamLook", "cam->up.x = 0.0f",
                  "DSCE_MarioOcarinaCamX", "DSCE_MarioOcarinaCamY",
                  "DSCE_MarioOcarinaCamZ"):
        require(token in hook, f"PC-parity singing camera contract is missing {token}")
    for token in ("singFrame", "singNoteSeen", "singActive",
                  "Dsce_MarioAnimPoseById", "DSCE_SingAnimId",
                  "DSCE_SingAnimSpeed", "DSCE_SingNotePulse"):
        require(token in actor, f"PC-parity singing animation contract is missing {token}")
    require("this->singActive ? DSCE_SingAnimId" in actor,
            "telemetry does not report the animation actually drawn while singing")
    takeover_init = actor[actor.index("gDsceSpikeAlive = 1;"):actor.index("void DsceMario_Destroy")]
    require("ACTOR_FLAG_UPDATE_DURING_OCARINA" in takeover_init,
            "MM would freeze Mario's singing clock throughout the ocarina modal")
    require("int Dsce_MarioAnimPoseById" in sandbox and "dsce_eval_anim_pose" in sandbox,
            "singing performance must evaluate its chosen SM64 animation on an independent clock")
    require("u32 gDsceSingNoteCount = 0" in adapters and
            "gDsceSingNoteCount++;" in integration_patch,
            "each played Mario note must pulse the singing animation")
    require("u16 gDsceSingSfxId = NA_SE_VO_DSCE_VO_PUNCH_HOO" in adapters and
            "AudioSfx_PlaySfx(gDsceSingSfxId" in integration_patch and
            "AudioSfx_PlaySfx(0x6814" not in integration_patch,
            "singing must use fixed-pitch Punch Hoo, not the variable-pitch vanilla hup channel")
    anim_ids = makefile[makefile.index("DSCE_ANIM_IDS :="):].splitlines()[0].split(":=", 1)[1].split()
    require("1D" in anim_ids, "the default PC singing animation 0x1D must be staged into the ROM")
    for setting in ("MarioOcarinaCamDist: 212.0", "MarioOcarinaCamHeight: 49.0",
                    "MarioOcarinaCamLook: 11.0", "MarioOcarinaCamX: -1.0",
                    "MarioOcarinaCamY: 6.0", "MarioOcarinaCamZ: -5.0",
                    "SingBaseSemitone: 9.0", "SingSample: 5"):
        require(setting in tuning, f"PC's saved singing-camera tuning is missing {setting}")
    for token in ("Audio_SetSfxVolumeExceptSystemAndOcarinaBanks(0x40)",
                  "SFX_CHANNEL_VOICE0, 0, 0x7F", "SFX_CHANNEL_VOICE1, 0, 0x7F",
                  "SingVolume 0.6 is silently halved"):
        require(token in integration_patch,
                f"Mario singing must undo MM's voice-bank ocarina duck: missing {token}")
    require("Contains the spirit of a" in dialogue and "hero from another world." in dialogue,
            "Brother's Mask get-item description is missing")
    for text_id in ("0x0083", "0x173D", "0x1FF4", "0x210A", "0x2341"):
        require(text_id in dialogue, f"global Brother's Mask text override {text_id} is missing")
    require("Toto's Reward" in dialogue and "ITEM_RUPEE_HUGE" in dialogue,
            "Toto notebook text/icon must describe the replacement reward")

    _w, _h, donor_pixels = png_read(str(args.original_logo))
    donor_opaque = sum(alpha >= 128 for _r, _g, _b, alpha in donor_pixels)
    byte_values = [int(value, 16) for value in
                   re.findall(r"0x([0-9a-fA-F]{2})", args.staged_logo.read_text())]
    require(len(byte_values) == 2048, "generated cap logo must contain 1024 RGBA16 texels")
    texels = [(byte_values[i] << 8) | byte_values[i + 1]
              for i in range(0, len(byte_values), 2)]
    generated_opaque = sum(texel & 1 for texel in texels)
    require(0 < generated_opaque < 1024, "cap badge must contain both opaque and transparent texels")
    require(generated_opaque == donor_opaque,
            f"cap badge must preserve donor alpha mask ({generated_opaque} != {donor_opaque})")

    toto = (args.mm / "src/overlays/actors/ovl_En_Toto/z_en_toto.c").read_text()
    reward_start = toto.rindex("void func_80BA4CB4")
    reward_func = toto[reward_start:toto.index("void EnToto_Update", reward_start)]
    require("GI_RUPEE_HUGE" in reward_func and "GI_MASK_CIRCUS_LEADER" not in reward_func,
            "Toto's final cue must award 200 rupees, not the replaced mask")
    require("SET_WEEKEVENTREG(WEEKEVENTREG_50_01)" in toto and
            "SET_WEEKEVENTREG(WEEKEVENTREG_51_80)" in toto and
            "BOMBERS_NOTEBOOK_EVENT_RECEIVED_CIRCUS_LEADERS_MASK" in toto,
            "Toto quest completion and notebook flags must remain intact")

    notebook = (args.mm / "include/tables/notebook_table.h").read_text()
    event_line = next(line for line in notebook.splitlines()
                      if "DEFINE_EVENT(BOMBERS_NOTEBOOK_EVENT_RECEIVED_CIRCUS_LEADERS_MASK" in line)
    require("BOMBERS_NOTEBOOK_EVENT_ICON_RIBBON" in event_line,
            "Toto's displaced mask event must be presented as a generic completed reward")

    print(f"content contracts OK: twirl + PC singing camera/animation, "
          f"{generated_opaque}/1024 badge texels opaque, Toto reward=200 rupees with quest flags retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
