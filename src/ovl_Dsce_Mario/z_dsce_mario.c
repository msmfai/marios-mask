/* [DSCE N64] Phase P spike actor: runs the vendored SM64 moveset kernel and drives the player's
 * position with it. Spawned by Dsce_PlayUpdateHook (dsce_hook.c, code segment) on L+R+Z.
 * Telemetry: GfxPrint HUD (tick us, arena free, action) + gDsceTelemetry RDRAM block for the
 * mupen input-script plugin. Link's model is intentional -- this stage measures physics, not looks. */
#include "global.h"
#include "zelda_arena.h"
#include "libu64/gfxprint.h"
#include "../dsce_config.h"
#include "../dsce_mario_compat.h"
#include "../dsce_telemetry.h"

#define THIS ((DsceMarioActor*)thisx)

typedef struct DsceMarioActor {
    Actor actor;
    s32 ticks;
    s16 donTimer;  /* mask-don grow-in frames remaining */
    s16 healTimer; /* statue: frame counter within a cutscene state (csTimer) */
    s16 csState;   /* statue: DSCE_PEACH_CS_* (inherited PC SoH state machine) */
    f32 fadeAlpha; /* statue: 255->0 as she dissolves into the floor */
    f32 origY;     /* statue: placed floor Y (the give is offered from here, not the sunk pos) */
    f32 singFrame; /* takeover: independent PC-style performance-animation clock */
    u32 singNoteSeen;
    u8 singActive;
    ColliderCylinder atCylinder; /* takeover: Mario's attacks; statue: her solid OC body */
} DsceMarioActor;

/* [DSCE] Peach-statue SoH cutscene states -- INHERITED 1:1 from the PC (z_actor.c DSCE_PEACH_CS_*). */
#define DSCE_PEACH_CS_IDLE 0 /* standing; solid + talk ("I will never finish that cake...") */
#define DSCE_PEACH_CS_RING 1 /* SoH played: warp-pillar light rising; brief beat */
#define DSCE_PEACH_CS_FADE 2 /* chime fired; shrinking + sinking into the floor */
#define DSCE_PEACH_CS_GIVE 3 /* gone: offer the Brother's Mask (real get-item) */
#define DSCE_PEACH_CS_GONE 4 /* taken: pin the shared slot to BROTHERS until the textbox closes */

/* statue collider: OC only (a solid prop; she doesn't fight or take damage) -- PC init, verbatim */
static ColliderCylinderInit sDscePeachColliderInit = {
    {
        COL_MATERIAL_NONE,
        AT_NONE,
        AC_NONE,
        OC1_ON | OC1_TYPE_ALL,
        OC2_TYPE_2,
        COLSHAPE_CYLINDER,
    },
    {
        ELEM_MATERIAL_UNK0,
        { 0x00000000, 0x00, 0x00 },
        { 0x00000000, 0x00, 0x00 },
        ATELEM_NONE,
        ACELEM_NONE,
        OCELEM_ON,
    },
    { 28, 90, 0, { 0, 0, 0 } },
};

/* Mario's attacks land as MM's own bare-hand damage class (the Goron punch: every enemy's
 * damage table has a reaction for it; MM's unarmed melee row is { DMG_GORON_PUNCH, 2 }).
 * Attached to the PLAYER actor so enemies attribute the hit to the player (aggro, knockback
 * direction, "attacked by player" checks). Active only while the SM64 action is ATTACKING. */
static ColliderCylinderInit sDsceAtCylinderInit = {
    {
        COL_MATERIAL_NONE,
        AT_ON | AT_TYPE_PLAYER,
        AC_NONE,
        OC1_NONE,
        OC2_NONE,
        COLSHAPE_CYLINDER,
    },
    {
        ELEM_MATERIAL_UNK0,
        { DMG_GORON_PUNCH, 0x00, 0x02 },
        { 0x00000000, 0x00, 0x00 },
        ATELEM_ON | ATELEM_NEAREST,
        ACELEM_NONE,
        OCELEM_NONE,
    },
    { 25, 50, 0, { 0, 0, 0 } },
};
#define DSCE_SM64_ACT_FLAG_ATTACKING 0x00800000 /* sm64.h ACT_FLAG_ATTACKING (punch/kick/dive/slide) */

/* sandbox driver (overlay-local, src/dsce/sm64) */
extern void Dsce_MarioSandboxInit(float mmx, float mmy, float mmz, short yaw);
extern void Dsce_MarioSandboxTick(float stickX, float stickY, unsigned short btnDown,
                                  unsigned short btnPressed, short camYaw);
extern void Dsce_MarioSandboxGetState(float* mmx, float* mmy, float* mmz, short* facingYaw,
                                      short* visualYaw, unsigned* action, float* fwdVel);
extern int gDsceWorldAuthority;
extern PlayState* gDsceAuthorityPlay;

/* Telemetry block lives in dsce_hook.c (CODE segment, fixed VA -- overlays relocate, so it
 * can't live here). Same u32 layout: magic/frame/tickUs/tickUsMax/arenaFree/arenaFreeMin/action. */
extern int gDsceSpikeAlive;

/* Phase 2 body draw: parts table (dsce_mario_model.c), pose evaluator (driver). */
extern const DsceMarioPart gDsceMarioParts[];
extern Lights1* const gDsceMarioLightGroups[6];
extern const Gfx* const gDsceMarioEyeDls[3];
extern const Gfx* const gDsceMarioHandDls[2][3];
extern int Dsce_MarioAnimPose(s16 outTrans[3], s16 outRot[][3]);
extern int Dsce_MarioAnimPoseById(s32 animId, s32 frame, s16 outTrans[3], s16 outRot[][3]);
extern int Dsce_MarioBodyState(s16 out[10]);
static const s8 sDsceBlinkPattern[7] = { 1, 2, 1, 0, 1, 2, 1 }; /* SM64 gMarioBlinkAnimation */
extern u32 gDsceAnimFallbacks;
/* SM64 geo root scale (0.25, GEO_SCALE 16384) folded with SM64->MM world scale (1/4.29) */
#include "../dsce_tuning.h"
#define DSCE_MARIO_DRAW_SCALE (0.25f / 4.29f)
static ActorFunc sDsceSavedPlayerDraw = NULL;

/* THE BROTHER'S MASK PICKUP (actor params == 1): a floating, spinning mask billboard in
 * the South Clock Town plaza; touching it grants the Brother's Mask. The takeover spike
 * is params == 0. */
#include "dsce_mask_pickup_tex.h"
int gDscePickupDied = 0; /* tells the hook its pickup was claimed/freed */

/* THE PEACH STATUE (params == 2): a stone Peach at the Laundry Pool; playing the Song
 * of Healing within earshot heals the trapped soul into the Brother's Mask pickup. */
extern const DsceMarioPart* const gDscePeachParts;
extern const int gDscePeachPartCount;
extern struct DsceAnimOpaque; /* not needed: evaluate via the mario-compat Animation */
extern const void* const gDscePeachPoseAnim;
int gDsceStatueDied = 0;
int gDsceStatueUp = 0;
int gDscePickupUp = 0;
int gDsceDebugSong = 0; /* testboot combo sets this: "Song of Healing just played" */
int gDsceSongHealLatch = 0; /* SoH grace window, set by the hook (the statue is frozen at song time) */
static s16 sDsceStatueRot[32][3];
static int sDsceStatuePosed = 0;
static Vtx sDsceMaskPickupVtx[4] = {
    { { { -24, 48, 0 }, 0, { 0, 0 }, { 255, 255, 255, 255 } } },
    { { { 24, 48, 0 }, 0, { 32 << 6, 0 }, { 255, 255, 255, 255 } } },
    { { { 24, 0, 0 }, 0, { 32 << 6, 32 << 6 }, { 255, 255, 255, 255 } } },
    { { { -24, 0, 0 }, 0, { 0, 32 << 6 }, { 255, 255, 255, 255 } } },
};

void DsceMario_Init(Actor* thisx, PlayState* play) {
    Player* player = GET_PLAYER(play);

    if (thisx->params == 1) { /* pickup mode: no takeover machinery at all */
        Actor_SetScale(thisx, 1.0f);
        gDscePickupUp = 1;
        return;
    }
    if (thisx->params == 2) { /* statue mode */
        Actor_SetScale(thisx, DSCE_PeachStatueScale);
        ((DsceMarioActor*)thisx)->csState = DSCE_PEACH_CS_IDLE;
        ((DsceMarioActor*)thisx)->fadeAlpha = 255.0f;
        ((DsceMarioActor*)thisx)->origY = thisx->world.pos.y;
        /* [DSCE] PC-inherited statue flags. UPDATE_DURING_OCARINA is THE load-bearing one:
         * without it MM freezes this actor for the whole song sequence, so it never sees
         * ocarinaMode == OCARINA_MODE_EVENT and the rite silently never starts. */
        thisx->flags |= ACTOR_FLAG_UPDATE_DURING_OCARINA; /* keep ticking while the ocarina plays */
        thisx->flags |= ACTOR_FLAG_ATTENTION_ENABLED;     /* Z-targetable */
        thisx->attentionRangeType = ATTENTION_RANGE_3;    /* lock-on / talk range */
        thisx->colChkInfo.mass = MASS_IMMOVABLE;          /* Link can't shove the statue */
        Collider_InitCylinder(play, &((DsceMarioActor*)thisx)->atCylinder);
        Collider_SetCylinder(play, &((DsceMarioActor*)thisx)->atCylinder, thisx, &sDscePeachColliderInit);
        gDsceStatueUp = 1;
        {
            extern void Dsce_Log(const char*, s32, s32, s32, s32);
            Dsce_Log("peach.spawn", (s32)thisx->world.pos.x, (s32)thisx->world.pos.y,
                     (s32)thisx->world.pos.z, 0);
        }
        return;
    }
    gDsceSpikeAlive = 1;
    /* MM otherwise freezes every actor lacking this exception for the entire
     * ocarina modal. The camera hook lives in Play_Update and would keep moving,
     * but Mario's independent PC performance clock would never advance. */
    thisx->flags |= ACTOR_FLAG_UPDATE_DURING_OCARINA;
    Actor_SetScale(thisx, DSCE_MARIO_DRAW_SCALE);
    ((DsceMarioActor*)thisx)->donTimer = 12; /* mask-don flourish (was a bare swap) */
    Collider_InitCylinder(play, &((DsceMarioActor*)thisx)->atCylinder);
    Collider_SetCylinder(play, &((DsceMarioActor*)thisx)->atCylinder, &player->actor, &sDsceAtCylinderInit);
    {
        extern void Dsce_AdapterPlayVoice(int kind);
        Dsce_AdapterPlayVoice(1); /* SHOUT: the mask-don "yahoo" */
    }
    Dsce_MarioSandboxInit(player->actor.world.pos.x, player->actor.world.pos.y,
                          player->actor.world.pos.z, player->actor.shape.rot.y);
    /* Mario IS the body now: hide Link's model (the sanctioned way -- z_player itself
     * NULLs actor.draw for invisibility) but keep all his logic running. */
    if (player->actor.draw != NULL) {
        sDsceSavedPlayerDraw = player->actor.draw;
        player->actor.draw = NULL;
    }
}

void DsceMario_Destroy(Actor* thisx, PlayState* play) {
    Player* player = GET_PLAYER(play);

    if (thisx->params == 1) {
        gDscePickupDied = 1;
        gDscePickupUp = 0;
        return;
    }
    if (thisx->params == 2) {
        {
            extern void Dsce_Log(const char*, s32, s32, s32, s32);
            Dsce_Log("peach.died", ((DsceMarioActor*)thisx)->csState, 0, 0, 0);
        }
        gDsceStatueDied = 1;
        gDsceStatueUp = 0;
        return;
    }
    gDsceSpikeAlive = 0;
    gDsceWorldAuthority = 0;
    Collider_DestroyCylinder(play, &((DsceMarioActor*)thisx)->atCylinder);
    if ((sDsceSavedPlayerDraw != NULL) && (player != NULL) && (player->actor.draw == NULL)) {
        player->actor.draw = sDsceSavedPlayerDraw;
    }
    sDsceSavedPlayerDraw = NULL;
}

/* rising gold sparkles for the Peach rite (PC pillar-of-light equivalent; gameplay_keep) */
static void DscePeach_RiteSparkles(DsceMarioActor* this, PlayState* play) {
    if ((this->ticks++ % 2) == 0) {
        Vec3f pos = this->actor.world.pos;
        Vec3f vel = { 0.0f, 3.0f, 0.0f };
        Vec3f accel = { 0.0f, 0.3f, 0.0f };
        Color_RGBA8 prim = { 255, 235, 150, 255 }; /* the PC rite's gold */
        Color_RGBA8 env = { 200, 120, 40, 0 };

        {
            s16 ang = (s16)(Rand_ZeroOne() * 65535.0f);
            f32 r = 34.0f + Rand_ZeroFloat(16.0f); /* a ring OUTSIDE her body (no overdraw flicker) */
            pos.x += Math_SinS(ang) * r;
            pos.z += Math_CosS(ang) * r;
        }
        pos.y = this->origY + Rand_ZeroFloat(40.0f);
        EffectSsKirakira_SpawnDispersed(play, &pos, &vel, &accel, &prim, &env, 2500, 26);
    }
}

void DsceMario_Update(Actor* thisx, PlayState* play) {
    DsceMarioActor* this = THIS;
    Player* player = GET_PLAYER(play);
    Input* input = &play->state.input[0];

    Camera* cam = GET_ACTIVE_CAM(play);
    s16 camYaw = (cam != NULL) ? Camera_GetInputDirYaw(cam) : 0;
    float mx;
    float my;
    float mz;
    short facingYaw;
    short visualYaw;
    unsigned action;
    float fwd;
    OSTime t0;
    OSTime t1;
    u32 us;
    size_t maxFree;
    size_t free;
    size_t alloc;

    if (thisx->params == 2) { /* statue: the SoH rite, INHERITED from the PC state machine */
        f32 sdx = player->actor.world.pos.x - thisx->world.pos.x;
        f32 sdz = player->actor.world.pos.z - thisx->world.pos.z;
        /* the hook latches the song event (the statue itself is frozen when it happens) */
        int song = (gDsceSongHealLatch > 0);

        if (gDsceDebugSong) {
            song = 1;
            gDsceDebugSong = 0;
        }
#if DSCE_DBG_GAMEPLAY
        { /* tag 1: state, timer, fade*1000, has-item-parent on every statue update */
            extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
            Dsce_Fh(7, 1, this->csState, this->healTimer, (s32)(this->fadeAlpha * 1000.0f),
                    Actor_HasParent(thisx, play) ? 1 : 0);
        }
#endif
        { /* [DSCE LOG] the WHOLE rite, every state: csState, scale, taken?, latch */
            extern void Dsce_Log(const char*, s32, s32, s32, s32);
            static u8 sDscePeachCsLog = 0;
            if ((++sDscePeachCsLog & 3) == 0) {
                Dsce_Log("peach.cs", this->csState, (s32)(thisx->scale.x * 100000.0f),
                         Actor_HasParent(thisx, play) ? 1 : 0, gDsceSongHealLatch);
            }
        }
        /* solid + talkable until she begins to dissolve */
        if (this->csState < DSCE_PEACH_CS_FADE) {
            Collider_UpdateCylinder(thisx, &this->atCylinder);
            CollisionCheck_SetOC(play, &play->colChkCtx, &this->atCylinder.base);
        }
        switch (this->csState) {
            case DSCE_PEACH_CS_IDLE:
                { /* [DSCE LOG] rite diagnostics: ocarina mode/song/distance; GAPS in the frame
                     column = the statue was frozen those frames (category/flag regressions) */
                    extern void Dsce_Log(const char*, s32, s32, s32, s32);
                    static u8 sDscePeachLogTick = 0;
                    if ((++sDscePeachLogTick & 7) == 0) {
                        Dsce_Log("peach.idle", play->msgCtx.ocarinaMode, play->msgCtx.lastPlayedSong,
                                 gDsceSongHealLatch * 100000 + (s32)(sdx * sdx + sdz * sdz) / 100,
                                 this->csState);
                    }
                }
                /* A near her -> "I will never finish that cake..." (Mario dialogue range) */
                if (!Actor_TalkOfferAccepted(thisx, &play->state)) {
                    thisx->textId = 0x4009;
                    Actor_OfferTalk(thisx, play, 90.0f);
                }
                if (song && ((sdx * sdx + sdz * sdz) < (280.0f * 280.0f))) {
                    gDsceSongHealLatch = 0; /* consume the latch */
                    if (play->msgCtx.ocarinaMode == OCARINA_MODE_EVENT) {
                        play->msgCtx.ocarinaMode = OCARINA_MODE_END; /* consume, En_Gb2 style */
                    }
                    this->csState = DSCE_PEACH_CS_RING;
                    this->healTimer = 0;
#if DSCE_DBG_GAMEPLAY
                    { /* tag 2: old state, new state, cause/mode, song */
                        extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
                        Dsce_Fh(7, 2, DSCE_PEACH_CS_IDLE, DSCE_PEACH_CS_RING,
                                play->msgCtx.ocarinaMode, play->msgCtx.lastPlayedSong);
                    }
#endif
                }
                break;
            case DSCE_PEACH_CS_RING:
                /* brief beat, then the puzzle-solved chime kicks off the dissolve (PC: 16 frames).
                 * The PC raised a warp-pillar actor; its object isn't loaded in this scene, so the
                 * N64 rite uses rising gold sparkles (gameplay_keep -- always available). */
                DscePeach_RiteSparkles(this, play);
                this->healTimer++;
                if (this->healTimer >= 16) {
                    Audio_PlaySfx(NA_SE_SY_CORRECT_CHIME);
                    this->csState = DSCE_PEACH_CS_FADE;
                    this->healTimer = 0;
#if DSCE_DBG_GAMEPLAY
                    { extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
                      Dsce_Fh(7, 2, DSCE_PEACH_CS_RING, DSCE_PEACH_CS_FADE, 16, 0); }
#endif
                }
                break;
            case DSCE_PEACH_CS_FADE: {
                /* she shrinks to a point at her feet over 24 frames. No floor-sink on N64: her
                 * geometry z-fought the walkway while intersecting it (read as flickering
                 * textures), and with no alpha dissolve the descent added nothing. The skeleton
                 * roots at the placed floor spot, so a pure scale-down reads as melting away. */
                DscePeach_RiteSparkles(this, play);
                this->healTimer++;
                this->fadeAlpha -= 255.0f / 24.0f;
                if (this->fadeAlpha < 0.0f) {
                    this->fadeAlpha = 0.0f;
                }
                Actor_SetScale(thisx, DSCE_PeachStatueScale * (this->fadeAlpha / 255.0f));
                if (this->fadeAlpha <= 0.0f) {
                    Audio_PlaySfx(NA_SE_SY_GET_ITEM);
                    this->csState = DSCE_PEACH_CS_GIVE;
#if DSCE_DBG_GAMEPLAY
                    { extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
                      Dsce_Fh(7, 2, DSCE_PEACH_CS_FADE, DSCE_PEACH_CS_GIVE,
                              this->healTimer, 0); }
#endif
                }
                break;
            }
            case DSCE_PEACH_CS_GIVE:
                if (Actor_HasParent(thisx, play)) {
                    this->csState = DSCE_PEACH_CS_GONE;
                    this->healTimer = 0;
#if DSCE_DBG_GAMEPLAY
                    { extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
                      Dsce_Fh(7, 2, DSCE_PEACH_CS_GIVE, DSCE_PEACH_CS_GONE, 0, 0); }
#endif
                } else {
                    Actor_OfferGetItem(thisx, play, GI_MASK_CIRCUS_LEADER, 400.0f, 200.0f);
                }
                break;
            case DSCE_PEACH_CS_GONE:
                /* The give textbox opens a few frames AFTER the catch and Item_Give runs when it
                 * closes -- dying on a short msg-free window raced all of that (the hook then saw
                 * an empty slot and respawned her). Hold until the mask has ACTUALLY LANDED in the
                 * slot and the textbox is done, then put it on C-LEFT and vanish. */
                if ((gSaveContext.save.saveInfo.inventory.items[SLOT_MASK_CIRCUS_LEADER] ==
                     ITEM_MASK_CIRCUS_LEADER) &&
                    (play->msgCtx.msgMode == MSGMODE_NONE)) {
                    this->healTimer++;
                    if (this->healTimer > 5) {
                        BUTTON_ITEM_EQUIP(0, EQUIP_SLOT_C_LEFT) = ITEM_MASK_CIRCUS_LEADER;
                        C_SLOT_EQUIP(0, EQUIP_SLOT_C_LEFT) = SLOT_MASK_CIRCUS_LEADER;
                        Interface_LoadItemIconImpl(play, EQUIP_SLOT_C_LEFT);
                        Actor_Kill(thisx);
                    }
                } else {
                    this->healTimer = 0;
                }
                break;
            default:
                break;
        }
        return;
    }
    if (thisx->params == 1) { /* pickup: spin, bob, grant on touch */
        f32 dx = player->actor.world.pos.x - thisx->world.pos.x;
        f32 dz = player->actor.world.pos.z - thisx->world.pos.z;

        thisx->shape.rot.y += 0x300;
        thisx->world.pos.y = 25.0f + 6.0f * Math_SinS((s16)(play->state.frames << 10));
        if ((dx * dx + dz * dz) < (85.0f * 85.0f)) { /* generous grab for a floating pickup */
            Item_Give(play, ITEM_MASK_CIRCUS_LEADER);
            /* assign to human C-LEFT (displacing its item -- reassignable in the pause
             * menu; MM would otherwise leave the earned mask unusable until paused) */
            BUTTON_ITEM_EQUIP(0, EQUIP_SLOT_C_LEFT) = ITEM_MASK_CIRCUS_LEADER;
            C_SLOT_EQUIP(0, EQUIP_SLOT_C_LEFT) = SLOT_MASK_CIRCUS_LEADER;
            Interface_LoadItemIconImpl(play, EQUIP_SLOT_C_LEFT);
            Audio_PlaySfx(NA_SE_SY_GET_ITEM);
            Actor_Kill(thisx);
        }
        return;
    }

    gDsceAuthorityPlay = play;
    gDsceWorldAuthority = 1;


    t0 = osGetTime();
    /* During cutscenes (entrance pans, exits) and the ocarina/song UI, Mario stays VISIBLE
     * (the takeover no longer dies -- that flashed Link back) but must not fight the script
     * or run around under the staff notation: tick the sandbox with a neutral pad so he idles. */
    if (Play_InCsMode(play) || (play->msgCtx.msgMode != MSGMODE_NONE)) {
        Dsce_MarioSandboxTick(0.0f, 0.0f, 0, 0, (s16)(camYaw + 0x8000));
    } else
    /* SM64 stick convention vs MM camera yaw: +180deg, matching the PC sandbox default. */
    Dsce_MarioSandboxTick(input->cur.stick_x, input->cur.stick_y, input->cur.button,
                          input->press.button, (s16)(camYaw + 0x8000));
    {
        extern u32 gDsceSingNoteCount;
        s32 singing = (player->stateFlags2 & PLAYER_STATE2_USING_OCARINA) != 0;

        if (singing) {
            if (!this->singActive || (DSCE_SingNotePulse && (this->singNoteSeen != gDsceSingNoteCount))) {
                this->singFrame = 0.0f;
            } else {
                this->singFrame += DSCE_SingAnimSpeed;
            }
            this->singNoteSeen = gDsceSingNoteCount;
            this->singActive = true;
        } else {
            this->singFrame = 0.0f;
            this->singActive = false;
        }
    }
    t1 = osGetTime();
    Dsce_MarioSandboxGetState(&mx, &my, &mz, &facingYaw, &visualYaw, &action, &fwd);
    player->actor.world.pos.x = mx;
    player->actor.world.pos.y = my;
    player->actor.world.pos.z = mz;
    /* MM camera/collision authority follows Mario's stable facing direction.  SM64's
     * twirlYaw is graphics-only and belongs on our separately rendered actor below. */
    player->actor.shape.rot.y = facingYaw;
    player->actor.world.rot.y = facingYaw;
    /* our own actor rides Mario's transform: Actor_Draw pre-loads world pos + shape rot
     * + scale as the current matrix before DsceMario_Draw runs */
    this->actor.world.pos.x = mx;
    this->actor.world.pos.y = my;
    this->actor.world.pos.z = mz;
    this->actor.shape.rot.y = visualYaw;

    /* Mario's attacks hurt MM enemies: while the SM64 action is ATTACKING (punch, kick,
     * dive, slide-kick, breakdance), an AT cylinder rides his fist arc -- centered a
     * body-length ahead at torso height. Registered fresh each frame; enemies react via
     * their own damage tables (DMG_GORON_PUNCH = MM's bare-hand class). */
    if (action & DSCE_SM64_ACT_FLAG_ATTACKING) {
        this->atCylinder.dim.pos.x = (s16)(mx + Math_SinS(facingYaw) * 30.0f);
        this->atCylinder.dim.pos.y = (s16)my;
        this->atCylinder.dim.pos.z = (s16)(mz + Math_CosS(facingYaw) * 30.0f);
        CollisionCheck_SetAT(play, &play->colChkCtx, &this->atCylinder.base);
    }

    us = OS_CYCLES_TO_USEC(t1 - t0);
    gDsceTelemetry.frame = ++this->ticks;
    gDsceTelemetry.tickUs = us;
    if (us > gDsceTelemetry.tickUsMax) {
        gDsceTelemetry.tickUsMax = us;
    }
    ZeldaArena_GetSizes(&maxFree, &free, &alloc);
    gDsceTelemetry.arenaFree = (u32)free;
    if ((u32)free < gDsceTelemetry.arenaFreeMin) {
        gDsceTelemetry.arenaFreeMin = (u32)free;
    }
    gDsceTelemetry.action = action;
    gDsceTelemetry.posX = mx;
    gDsceTelemetry.posY = my;
    gDsceTelemetry.posZ = mz;
    gDsceTelemetry.mmHealth = gSaveContext.save.saveInfo.playerData.health;
    {
        extern int Dsce_MarioSandboxAnimId(void);
        /* Report the pose the renderer will actually use. During MM's ocarina modal
         * the movement sandbox deliberately idles, but Draw overrides that idle pose
         * with the independent PC singing animation. */
        gDsceTelemetry.animId = this->singActive ? DSCE_SingAnimId : (u32)Dsce_MarioSandboxAnimId();
    }
    gDsceTelemetry.animFallbacks = gDsceAnimFallbacks;
    { /* scene-ambient blend: rescale the model's light groups by the live scene light so
       * Mario dims in interiors/night like everything else (SM64 never did this). */
        static u8 sBaseCols[6][12];
        static int sBaseInit = 0;
        s32 gi;
        s32 c;
        CurrentEnvLightSettings* ls = &play->envCtx.lightSettings;

        if (!sBaseInit) {
            for (gi = 0; gi < 6; gi++) {
                for (c = 0; c < 3; c++) {
                    sBaseCols[gi][c] = gDsceMarioLightGroups[gi]->a.l.col[c];
                    sBaseCols[gi][3 + c] = gDsceMarioLightGroups[gi]->a.l.colc[c];
                    sBaseCols[gi][6 + c] = gDsceMarioLightGroups[gi]->l[0].l.col[c];
                    sBaseCols[gi][9 + c] = gDsceMarioLightGroups[gi]->l[0].l.colc[c];
                }
            }
            sBaseInit = 1;
        }
        { /* [perf, goal 07] skip the 96-value rewrite when the scene light is unchanged */
            static u8 sLastLight[6] = { 0xFF, 0, 0, 0, 0, 0 };
            if (sBaseInit &&
                sLastLight[0] == ls->ambientColor[0] && sLastLight[1] == ls->ambientColor[1] &&
                sLastLight[2] == ls->ambientColor[2] && sLastLight[3] == ls->light1Color[0] &&
                sLastLight[4] == ls->light1Color[1] && sLastLight[5] == ls->light1Color[2]) {
                goto ambient_done;
            }
            sLastLight[0] = ls->ambientColor[0]; sLastLight[1] = ls->ambientColor[1];
            sLastLight[2] = ls->ambientColor[2]; sLastLight[3] = ls->light1Color[0];
            sLastLight[4] = ls->light1Color[1]; sLastLight[5] = ls->light1Color[2];
        }
        for (c = 0; c < 3; c++) {
            s32 f = ((s32)ls->ambientColor[c] + (s32)ls->light1Color[c]); /* 0..510 */
            if (f > 320) {
                f = 320; /* outdoor day saturates to 1.0 (320/320) */
            }
            f = f * DSCE_MarioBrightness / 100; /* user feedback: washed out at 1.0 */
            if (f < 80) {
                f = 80; /* readability floor in pitch dark */
            }
            for (gi = 0; gi < 6; gi++) {
                gDsceMarioLightGroups[gi]->a.l.col[c] = (u8)(sBaseCols[gi][c] * f / 320);
                gDsceMarioLightGroups[gi]->a.l.colc[c] = (u8)(sBaseCols[gi][3 + c] * f / 320);
                gDsceMarioLightGroups[gi]->l[0].l.col[c] = (u8)(sBaseCols[gi][6 + c] * f / 320);
                gDsceMarioLightGroups[gi]->l[0].l.colc[c] = (u8)(sBaseCols[gi][9 + c] * f / 320);
            }
        }
    ambient_done:;
    }
    {
        extern u32 gDsceVoiceReqs;
        extern u32 gDsceFoleyReqs;
        gDsceTelemetry.voiceReqs = gDsceVoiceReqs;
        gDsceTelemetry.foleyReqs = gDsceFoleyReqs;
    }
}

/* Hierarchical body render: hand-rolled geo_process_animated_part. Parts are in
 * anim-slot order with parent links, so one pass with per-part cached matrices replaces
 * SM64's GraphNode traversal. Rotation order matches SM64's mtxf_rotate_xyz_and_translate
 * (MM's Matrix_RotateZYX). Root anim translation is skipped in v1 (rotation-only pose;
 * Y-bounce polish comes with Phase 2b). */
/* generic SM64-anim pose evaluation at a fixed frame (statue = frozen pose) */
static void DsceStatue_Pose(s32 frame, s32 nparts) {
    const struct Animation* anim = (const struct Animation*)gDscePeachPoseAnim;
    const u16* attr = anim->index;
    s32 i;
    s32 j;

    attr += 6; /* skip root translation entry */
    for (i = 0; i < nparts && i < 32; i++) {
        for (j = 0; j < 3; j++) {
            u16 count = attr[0];
            u16 offset = attr[1];
            s32 fi = (count == 0) ? offset : ((frame < (s32)count) ? offset + frame : offset + count - 1);
            sDsceStatueRot[i][j] = anim->values[fi];
            attr += 2;
        }
    }
}

static void DsceStatue_Draw(Actor* thisx, PlayState* play) {
    static MtxF sMtx[32];
    s32 i;

    if (!sDsceStatuePosed) {
        /* The N64 pose is the HAND-VALIDATED frame-18 freeze. The PC's baked corrections
         * (FixBone/DressRot/PeachRot at frame 26) index its SkelAnime joint layout, which does
         * NOT match our geo-order part table -- applying them here skewed the dress orthogonal
         * to her body. Position/facing/tint/scale/sequence stay inherited; the pose is native. */
        DsceStatue_Pose(18, gDscePeachPartCount);
        sDsceStatuePosed = 1;
    }
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL25_Opa(play->state.gfxCtx);
    /* the SM64 RDP contract, same as the Mario body draw: her DLs are 1-cycle material with
     * paired gsSPLight loads -- under MM's 2-cycle fog pipeline + scene light count they render
     * combiner noise / washed shading (the "weird texture"). */
    gDPSetEnvColor(POLY_OPA_DISP++, 255, 255, 255, 255);
    gDPSetCycleType(POLY_OPA_DISP++, G_CYC_1CYCLE);
    gDPSetRenderMode(POLY_OPA_DISP++, G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2);
    gSPClearGeometryMode(POLY_OPA_DISP++, G_FOG);
    gSPSetGeometryMode(POLY_OPA_DISP++, G_LIGHTING | G_SHADING_SMOOTH);
    gSPNumLights(POLY_OPA_DISP++, NUMLIGHTS_1);
    for (i = 0; i < gDscePeachPartCount && i < 32; i++) {
        const DsceMarioPart* part = &gDscePeachParts[i];

        if (part->parent >= 0) {
            Matrix_Put(&sMtx[part->parent]);
        }
        Matrix_Translate(part->tx, part->ty, part->tz, MTXMODE_APPLY);
        Matrix_RotateZYX(sDsceStatueRot[i][0], sDsceStatueRot[i][1], sDsceStatueRot[i][2], MTXMODE_APPLY);
        Matrix_Get(&sMtx[i]);
        if (part->dl != NULL) {
            MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, play->state.gfxCtx);
            gSPDisplayList(POLY_OPA_DISP++, part->dl);
        }
    }
    /* restore MM's pipeline for whatever draws next (same as the body draw) */
    gDPPipeSync(POLY_OPA_DISP++);
    gDPSetCycleType(POLY_OPA_DISP++, G_CYC_2CYCLE);
    CLOSE_DISPS(play->state.gfxCtx);
}

static void DsceMario_DrawBody(Actor* thisx, PlayState* play) {
    static MtxF sPartMtx[DSCE_MARIO_NUM_PARTS];
    s16 trans[3];
    s16 rot[DSCE_MARIO_NUM_PARTS][3];
    s16 body[10];
    u32 sum = 0;
    s32 eyeCase = 0;
    s32 i;

    if (THIS->singActive) {
        if (!Dsce_MarioAnimPoseById(DSCE_SingAnimId, (s32)THIS->singFrame, trans, rot)) {
            return;
        }
    } else {
        if (!Dsce_MarioAnimPose(trans, rot)) {
            return;
        }
    }
    if (!Dsce_MarioBodyState(body)) {
        return;
    }
    if (body[0] == 0) { /* MARIO_EYES_BLINK: SM64's timer-driven blink cycle */
        s16 blinkFrame = (s16)((gDsceTelemetry.frame >> 1) & 0x1F);
        eyeCase = (blinkFrame < 7) ? sDsceBlinkPattern[blinkFrame] : 0;
    } else {
        eyeCase = (body[0] - 1 < 3) ? (body[0] - 1) : 0;
    }

    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL25_Opa(play->state.gfxCtx);
    /* SM64's body combiners (SHADEFADEA/BLENDRGBFADEA) read FADE alpha from the ENV
     * color, which MM animates for its own purposes -- pin it or the face strobes
     * black/white under accurate RDP (seen on simple64/parallel; glide64 hid it). */
    gDPSetEnvColor(POLY_OPA_DISP++, 255, 255, 255, 255);
    /* SM64's body DLs are authored for SM64's master-DL RDP contract, not MM's 2-cycle
     * fog pipeline. Under G_CYC_2CYCLE their combiners run twice and cycle 2 samples
     * garbage (TEXEL0 one pixel ahead) -- lighting-dependent NOISE on accurate renderers
     * (GLideN64/parallel; glide64 hides it, which is why the capture rig looked clean).
     * Pin the full SM64 contract: 1-cycle, plain opaque blender, no fog. The scene-
     * ambient light blend (below) still dims him correctly in interiors/night. */
    gDPSetCycleType(POLY_OPA_DISP++, G_CYC_1CYCLE);
    gDPSetRenderMode(POLY_OPA_DISP++, G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2);
    gSPClearGeometryMode(POLY_OPA_DISP++, G_FOG);
    /* SM64 enables G_LIGHTING once in its master init DL; the part DLs assume it. Without it,
     * the RSP reads the parts' packed vertex NORMALS as vertex COLORS -- every surface rendered
     * a direction-tinted pastel (top faces greenish, front faces purplish; measured S=0.17 on
     * what should be the deep tunic green). Set it here so the Lights1 groups actually light. */
    gSPSetGeometryMode(POLY_OPA_DISP++, G_LIGHTING | G_SHADING_SMOOTH);
    /* THE WASH ITSELF: the part DLs load their material via paired gsSPLight(&group.l, 1) +
     * gsSPLight(&group.a, 2) -- SM64's pattern, valid ONLY with numLights==1 (slot 1 directional,
     * slot 2 ambient; SM64's master init pins that once). MM's scene lighting leaves numLights at
     * whatever the scene bound (several), so slot 2 became a stray DIRECTIONAL light and MM's own
     * still-bound lights (incl. its bright ambient) kept shining on top -- Mario washed pastel
     * (S=0.17 vs the PC oracle's 0.71). Pin numLights to SM64's contract before the parts. */
    gSPNumLights(POLY_OPA_DISP++, NUMLIGHTS_1);
    for (i = 0; i < DSCE_MARIO_NUM_PARTS; i++) {
        const DsceMarioPart* part = &gDsceMarioParts[i];

        const Gfx* dl = part->dl;

        if (part->parent >= 0) {
            Matrix_Put(&sPartMtx[part->parent]);
            if (i == 2) { /* torso tilt (SM64 geo_mario_tilt_torso: reordered axes) */
                Matrix_RotateZYX(body[3], body[4], body[2], MTXMODE_APPLY);
            } else if (i == 3) { /* head turn (geo_mario_head_rotation) */
                Matrix_RotateZYX(body[6], body[7], body[5], MTXMODE_APPLY);
            }
            Matrix_Translate(part->tx, part->ty, part->tz, MTXMODE_APPLY);
        } else {
            /* root: PC ground lift + the anim's root Y-bounce (trans[1] * animYTrans mul) */
            f32 bounce = (f32)trans[1] * ((f32)body[8] / 256.0f);
            Matrix_Translate(part->tx, part->ty + DSCE_MarioYOff + bounce, part->tz, MTXMODE_APPLY);
        }
        Matrix_RotateZYX(rot[i][0], rot[i][1], rot[i][2], MTXMODE_APPLY);
        Matrix_Get(&sPartMtx[i]);
        if (i == 3) { /* head: blink-selected eyes DL */
            dl = gDsceMarioEyeDls[eyeCase];
        } else if (i == 7) { /* left hand */
            dl = gDsceMarioHandDls[0][body[1] < 3 ? body[1] : 0];
        } else if (i == 11) { /* right hand */
            dl = gDsceMarioHandDls[1][body[1] < 3 ? body[1] : 0];
        }
        if (dl != NULL) {
            MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, play->state.gfxCtx);
            gSPDisplayList(POLY_OPA_DISP++, dl);
        }
        sum += (u16)rot[i][0] + (u16)rot[i][1] + (u16)rot[i][2];
    }
    /* restore MM's pipeline contract for whatever draws next on POLY_OPA (the setup DLs
     * do NOT all reset cycle type -- a leaked 1-cycle would corrupt later actors' fog) */
    gDPPipeSync(POLY_OPA_DISP++);
    gDPSetCycleType(POLY_OPA_DISP++, G_CYC_2CYCLE);
    CLOSE_DISPS(play->state.gfxCtx);
    gDsceTelemetry.poseSum = sum;
    gDsceTelemetry.bodySum = (u32)eyeCase | ((u32)body[1] << 4) |
                             (((u32)(u16)(body[2] + body[3] + body[4] + body[6])) << 8);
}

void DsceMario_Draw(Actor* thisx, PlayState* play) {
#if DSCE_DBG_HUD
    GfxPrint printer;
    Gfx* gfx;
    Gfx* opaStart;
#endif

    if (thisx->params == 2) { /* statue */
        DsceStatue_Draw(thisx, play);
        return;
    }
    if (thisx->params == 1) { /* pickup: spinning textured quad */
        OPEN_DISPS(play->state.gfxCtx);
        Gfx_SetupDL25_Opa(play->state.gfxCtx);
        gDPSetCombineMode(POLY_OPA_DISP++, G_CC_DECALRGBA, G_CC_DECALRGBA);
        gSPClearGeometryMode(POLY_OPA_DISP++, G_CULL_BACK | G_LIGHTING);
        gSPTexture(POLY_OPA_DISP++, 0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON);
        gDPLoadTextureBlock(POLY_OPA_DISP++, gDsceMaskPickupTex, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0,
                            G_TX_NOMIRROR | G_TX_CLAMP, G_TX_NOMIRROR | G_TX_CLAMP, 5, 5,
                            G_TX_NOLOD, G_TX_NOLOD);
        MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, play->state.gfxCtx);
        gSPVertex(POLY_OPA_DISP++, sDsceMaskPickupVtx, 4, 0);
        gSP2Triangles(POLY_OPA_DISP++, 0, 1, 2, 0, 0, 2, 3, 0);
        CLOSE_DISPS(play->state.gfxCtx);
        return;
    }

    DsceMario_DrawBody(thisx, play);

#if DSCE_DBG_HUD
    OPEN_DISPS(play->state.gfxCtx);
    opaStart = POLY_OPA_DISP;
    gfx = Gfx_Open(opaStart);
    gSPDisplayList(OVERLAY_DISP++, gfx);
    GfxPrint_Init(&printer);
    GfxPrint_Open(&printer, gfx);
    GfxPrint_SetColor(&printer, 255, 255, 55, 255);
    GfxPrint_SetPos(&printer, 3, 5);
    GfxPrint_Printf(&printer, "TICK %4dus MAX %4dus", gDsceTelemetry.tickUs, gDsceTelemetry.tickUsMax);
    GfxPrint_SetPos(&printer, 3, 6);
    GfxPrint_Printf(&printer, "ARENA %6d MIN %6d", gDsceTelemetry.arenaFree, gDsceTelemetry.arenaFreeMin);
    GfxPrint_SetPos(&printer, 3, 7);
    GfxPrint_Printf(&printer, "ACT %08x", gDsceTelemetry.action);
    gfx = GfxPrint_Close(&printer);
    GfxPrint_Destroy(&printer);
    gSPEndDisplayList(gfx++);
    Gfx_Close(opaStart, gfx);
    POLY_OPA_DISP = gfx;
    CLOSE_DISPS(play->state.gfxCtx);
#endif
}

ActorProfile Dsce_Mario_Profile = {
    /**/ ACTOR_DSCE_MARIO,
    /**/ ACTORCAT_PROP, /* [DSCE] PC parity. MISC's freeze mask includes TALKING + in-cutscene, so
                         * the statue was frozen through the song textbox and missed the
                         * OCARINA_MODE_EVENT window even with the during-ocarina flag. PROP (the
                         * PC statue's category) is exempt from both. */
    /**/ ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED,
    /**/ GAMEPLAY_KEEP,
    /**/ sizeof(DsceMarioActor),
    /**/ DsceMario_Init,
    /**/ DsceMario_Destroy,
    /**/ DsceMario_Update,
    /**/ DsceMario_Draw,
};
