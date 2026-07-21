/*
 * dsce_mario_sandbox.c -- MIM-FEEL movement reversal (2026-06-24, user-insisted).
 *
 * Drive the MM "Mario Mask" form from SM64's REAL movement code instead of a hand-port.
 * The original act handlers (mario_actions_*.c) and the dispatch are already linked into
 * the 2ship host (force_load libsm64_game.a). This file is the minimal SANDBOX HARNESS so
 * they run WITHOUT SM64's full runtime (no area/object manager, no init_mario):
 *
 *   - a hand-init gMarioState pointed at static scaffolding (marioObj/controller/body),
 *   - input glue mirroring update_mario_{geometry,button,joystick}_inputs (camera yaw is
 *     passed in directly instead of m->area->camera->yaw, so no Area/Camera needed),
 *   - the EXISTING M3.x collision adapter: with gDsceWorldAuthority=MM, the real find_floor/
 *     find_wall_collisions (ghostship/src/engine/surface_collision.c) redirect into MM's
 *     BgCheck (Dsce_AdapterFindFloor/Walls in z_play.c). So the authentic SM64 steppers
 *     collide on MM's real Termina collision.
 *
 * Coordinates: canonical (SM64) units = MM units * gDsceMmScale. The MM host feeds the
 * actor's MM position/input/camera-yaw each frame and reads gMarioState back (canonical /
 * scale) onto the actor. C-ABI (plain floats/ints) so the MM C tree calls it without the
 * SM64 headers.
 */
#include "../../dsce_config.h"
#include "sm64.h"
#include "types.h"
#include "game/mario.h"
#include "game/mario_step.h"
#include "engine/surface_collision.h"
#include "engine/math_util.h"
/* [DSCE N64] IDO requires COMPLETE types for the static scaffolding below (clang accepted the
 * PC include set); Area/Camera/PlayerCameraState live in these headers. */
#include "game/area.h"
#include "game/camera.h"

extern struct MarioState* gMarioState;
extern int gDsceWorldAuthority;
extern float gDsceMmScale;
#ifndef DSCE_AUTH_MM
#define DSCE_AUTH_MM 1
#endif

/* action-group dispatch (mario_actions_*.c) -- ALL 7 groups, like execute_mario_action; missing any
 * freezes Mario when the real code shifts him into that group (e.g. AUTOMATIC ledge/slide). */
extern s32 mario_execute_stationary_action(struct MarioState* m);
extern s32 mario_execute_moving_action(struct MarioState* m);
extern s32 mario_execute_airborne_action(struct MarioState* m);
extern s32 mario_execute_submerged_action(struct MarioState* m);
extern s32 mario_execute_cutscene_action(struct MarioState* m);
extern s32 mario_execute_automatic_action(struct MarioState* m);
extern s32 mario_execute_object_action(struct MarioState* m);
extern u32 set_mario_action(struct MarioState* m, u32 action, u32 actionArg);

/* Minimal scaffolding so the original action code has valid pointers to write through. The Object is
 * over-allocated (0x400) so far-offset writes like oMarioWalkingPitch (Object+0x200) are always mapped
 * even if this TU's sizeof(struct Object) somehow differs from the rest of the colink. */
static union {
    struct Object obj;
    char pad[0x400];
} sSandboxObjU;
#define sSandboxObj (sSandboxObjU.obj)
static struct Controller sSandboxCtrl;
static struct MarioBodyState sSandboxBody;
static struct PlayerCameraState sSandboxCamState;
static struct SpawnInfo sSandboxSpawn;
static struct Area sSandboxArea;
static struct Camera sSandboxCamera;
static int sSandboxReady = 0;

/* MM's follow camera consumes the player actor's facing yaw.  During ACT_TWIRLING,
 * SM64's faceAngle is a steering input and twirlYaw is a visual spin; neither is a
 * good camera heading.  Publish a separate, movement-led heading with the pieces a
 * player-facing camera inevitably needs: noise rejection, turn-rate limiting,
 * reversal confirmation, stationary hold, and a short landing handoff. */
#define DSCE_TWIRL_MOVE_EPSILON_SQ 0.5625f /* 0.75 canonical units/frame */
#define DSCE_TWIRL_TURN_DEADZONE 0x0200    /* ignore sub-3-degree direction noise */
#define DSCE_TWIRL_TURN_STEP 0x0800        /* at most 11.25 degrees per game tick */
#define DSCE_TWIRL_REVERSE_ANGLE 0x5000    /* confirm changes sharper than 112.5 degrees */
#define DSCE_TWIRL_REVERSE_SLOP 0x1000     /* samples must agree within 22.5 degrees */
#define DSCE_TWIRL_REVERSE_FRAMES 3
#define DSCE_TWIRL_EXIT_STEP 0x1000
#define DSCE_TWIRL_EXIT_FRAMES 8

static s16 sPublishedFacingYaw;
static s16 sTwirlReverseCandidateYaw;
static u8 sTwirlReverseFrames;
static u8 sTwirlFacingActive;
static u8 sTwirlExitFrames;

static s32 sandbox_yaw_distance(s16 a, s16 b) {
    s32 delta = (s16)(a - b);
    return (delta < 0) ? -delta : delta;
}

static s16 sandbox_approach_yaw(s16 current, s16 target, s32 step) {
    s32 delta = (s16)(target - current);

    if (delta > step) {
        return current + step;
    }
    if (delta < -step) {
        return current - step;
    }
    return target;
}

static void sandbox_reset_published_facing(s16 yaw) {
    sPublishedFacingYaw = yaw;
    sTwirlReverseCandidateYaw = yaw;
    sTwirlReverseFrames = 0;
    sTwirlFacingActive = 0;
    sTwirlExitFrames = 0;
}

static void sandbox_update_published_facing(struct MarioState* m, f32 prevX, f32 prevZ) {
    f32 dx;
    f32 dz;
    s16 motionYaw;
    s32 yawDistance;

    if (m->action == ACT_TWIRLING) {
        if (!sTwirlFacingActive) {
            /* Carry forward the heading published on the pre-bounce tick.  faceAngle
             * has already received this tick's air-steering by the time we get here;
             * copying it would create a small launch-frame camera kick.  A purely
             * vertical launch should not rotate the view before Mario establishes travel. */
            sTwirlReverseFrames = 0;
            sTwirlFacingActive = 1;
            sTwirlExitFrames = 0;
        }

        dx = m->pos[0] - prevX;
        dz = m->pos[2] - prevZ;
        if ((dx * dx + dz * dz) < DSCE_TWIRL_MOVE_EPSILON_SQ) {
            /* Standing, blocked by a wall, or receiving only collision depenetration:
             * retain the last useful heading and discard partial reversal evidence. */
            sTwirlReverseFrames = 0;
            return;
        }

        /* Use the accepted post-collision displacement.  Raw stick intent and velocity
         * can both point through a wall; actual travel is the least surprising camera cue. */
        motionYaw = atan2s(dz, dx);
        yawDistance = sandbox_yaw_distance(motionYaw, sPublishedFacingYaw);

        if (yawDistance > DSCE_TWIRL_REVERSE_ANGLE) {
            /* A bonk/collision correction can produce one backwards sample.  Require a
             * coherent run before beginning a genuine about-face, avoiding a camera whip. */
            if ((sTwirlReverseFrames == 0) ||
                (sandbox_yaw_distance(motionYaw, sTwirlReverseCandidateYaw) > DSCE_TWIRL_REVERSE_SLOP)) {
                sTwirlReverseCandidateYaw = motionYaw;
                sTwirlReverseFrames = 1;
                return;
            }
            if (sTwirlReverseFrames < DSCE_TWIRL_REVERSE_FRAMES) {
                sTwirlReverseFrames++;
            }
            if (sTwirlReverseFrames < DSCE_TWIRL_REVERSE_FRAMES) {
                return;
            }
        } else {
            sTwirlReverseFrames = 0;
        }

        if (yawDistance > DSCE_TWIRL_TURN_DEADZONE) {
            sPublishedFacingYaw = sandbox_approach_yaw(sPublishedFacingYaw, motionYaw,
                                                       DSCE_TWIRL_TURN_STEP);
        }
        return;
    }

    if (sTwirlFacingActive) {
        sTwirlFacingActive = 0;
        sTwirlReverseFrames = 0;
        sTwirlExitFrames = DSCE_TWIRL_EXIT_FRAMES;
    }

    if (sTwirlExitFrames != 0) {
        /* Do not snap on the landing frame if SM64's internal steering yaw differs
         * from the movement-led view.  Ordinary facing regains authority quickly. */
        sPublishedFacingYaw = sandbox_approach_yaw(sPublishedFacingYaw, m->faceAngle[1],
                                                   DSCE_TWIRL_EXIT_STEP);
        sTwirlExitFrames--;
        if (sandbox_yaw_distance(sPublishedFacingYaw, m->faceAngle[1]) <=
            DSCE_TWIRL_TURN_DEADZONE) {
            sPublishedFacingYaw = m->faceAngle[1];
            sTwirlExitFrames = 0;
        }
    } else {
        sPublishedFacingYaw = m->faceAngle[1];
    }
}

void Dsce_MarioSandboxInit(float mmx, float mmy, float mmz, short yaw) {
    struct MarioState* m = gMarioState;
    f32 k = gDsceMmScale;
    bzero(&sSandboxObj, sizeof(sSandboxObj));
    bzero(&sSandboxCtrl, sizeof(sSandboxCtrl));
    bzero(&sSandboxBody, sizeof(sSandboxBody));
    bzero(&sSandboxCamState, sizeof(sSandboxCamState));
    bzero(&sSandboxSpawn, sizeof(sSandboxSpawn));

    bzero(&sSandboxArea, sizeof(sSandboxArea));
    bzero(&sSandboxCamera, sizeof(sSandboxCamera));
    sSandboxArea.camera = &sSandboxCamera; /* act code reads m->area->camera / terrainType */

    m->controller = &sSandboxCtrl;
    m->marioObj = &sSandboxObj;
    m->marioBodyState = &sSandboxBody;
    m->statusForCamera = &sSandboxCamState;
    m->spawnInfo = &sSandboxSpawn;
    m->area = &sSandboxArea;
    { /* [DSCE N64] anim plumbing must be non-NULL (see dsce_sm64_support.c) */
        extern struct DmaHandlerList gDsceAnimList;
        m->animList = &gDsceAnimList;
    }

    m->marioObj->header.gfx.animInfo.animID = -1;
    m->flags = MARIO_NORMAL_CAP | MARIO_CAP_ON_HEAD;
    m->action = ACT_IDLE;
    m->prevAction = ACT_IDLE;
    m->actionState = 0;
    m->actionTimer = 0;
    m->forwardVel = 0.0f;
    m->faceAngle[0] = 0;
    m->faceAngle[1] = yaw;
    m->faceAngle[2] = 0;
    m->angleVel[0] = m->angleVel[1] = m->angleVel[2] = 0;
    m->pos[0] = mmx * k;
    m->pos[1] = mmy * k;
    m->pos[2] = mmz * k;
    /* Native SM64 uses the last published graphics position as its OOB recovery
     * point.  The sandbox has no SM64 render pass, so seed that checkpoint here. */
    vec3f_copy(m->marioObj->header.gfx.pos, m->pos);
    m->vel[0] = m->vel[1] = m->vel[2] = 0.0f;
    m->floor = NULL;
    m->wall = NULL;
    m->ceil = NULL;
    m->health = 0x0880;
    m->framesSinceA = 0xFF;
    m->framesSinceB = 0xFF;
    m->squishTimer = 0;
    sandbox_reset_published_facing(yaw);
    sSandboxReady = 1;
    /* [DSCE N64] host layout probe (__builtin_offsetof) removed -- IDO has no such builtin and
     * the PC-side layout verification is meaningless on-target. */
}

/* mirrors the essential update_mario_{geometry,button,joystick}_inputs (mario.c) without the
 * camera/object/water deps. find_floor/find_ceil hit MM collision via the adapter. */
static void sandbox_update_inputs(struct MarioState* m, short camYaw) {
    struct Controller* c = m->controller;
    f32 mag;

    /* Port update_mario_geometry_inputs' containment order.  In native SM64 the
     * graphics position is the last endpoint accepted by a movement step.  If a
     * later write leaves Mario where no floor exists, restore that checkpoint
     * before action dispatch instead of permanently skipping every action tick. */
    f32_find_wall_collision(&m->pos[0], &m->pos[1], &m->pos[2], 60.0f, 50.0f);
    f32_find_wall_collision(&m->pos[0], &m->pos[1], &m->pos[2], 30.0f, 24.0f);
    m->floorHeight = find_floor(m->pos[0], m->pos[1], m->pos[2], &m->floor);
    if (m->floor == NULL) {
        vec3f_copy(m->pos, m->marioObj->header.gfx.pos);
        m->floorHeight = find_floor(m->pos[0], m->pos[1], m->pos[2], &m->floor);
    }
    m->ceilHeight = find_ceil(m->pos[0], m->pos[1], m->pos[2], &m->ceil);
    /* DSCE MIM-COHERENCE #2: water is REAL now -- find_water_level is answered by MM's WaterBoxes
     * (Dsce_AdapterFindWater) and returns FLOOR_LOWER_LIMIT when dry (so he won't "drown" on land) or the
     * surface Y when in MM water (so SM64's swim actions run). This replaces the old -20000 no-water pin. */
    m->waterLevel = find_water_level(m->pos[0], m->pos[2]);
    if (m->floor != NULL) {
        m->floorAngle = atan2s(m->floor->normal.z, m->floor->normal.x);
    }

    m->input = 0;
    if (m->floor == NULL) {
        return; /* both current and last accepted positions are invalid */
    }
    if (m->pos[1] > (m->floorHeight + 100.0f)) {
        m->input |= INPUT_OFF_FLOOR;
    }
    if (c->buttonPressed & A_BUTTON) {
        m->input |= INPUT_A_PRESSED;
        m->framesSinceA = 0;
    } else if (m->framesSinceA < 0xFF) {
        m->framesSinceA++;
    }
    if (c->buttonDown & A_BUTTON) {
        m->input |= INPUT_A_DOWN;
    }
    if (c->buttonPressed & B_BUTTON) {
        m->input |= INPUT_B_PRESSED;
        m->framesSinceB = 0;
    } else if (m->framesSinceB < 0xFF) {
        m->framesSinceB++;
    }
    /* Z flags -- REQUIRED for crouch / long-jump / backflip / ground-pound (they gate on INPUT_Z_*).
     * Missing these is why every Z-move failed the headless tests. */
    if (c->buttonDown & Z_TRIG) {
        m->input |= INPUT_Z_DOWN;
    }
    if (c->buttonPressed & Z_TRIG) {
        m->input |= INPUT_Z_PRESSED;
    }

    mag = ((c->stickMag / 64.0f) * (c->stickMag / 64.0f)) * 64.0f;
    m->intendedMag = mag / 2.0f;
    if (m->intendedMag > 0.0f) {
        m->intendedYaw = atan2s(-c->stickY, c->stickX) + camYaw;
        m->input |= INPUT_NONZERO_ANALOG;
    } else {
        m->intendedYaw = m->faceAngle[1];
    }

    /* [DSCE XGAME F3] flags the original update_mario_inputs sets that this glue missed --
     * found by the cross-game rig: without INPUT_UNKNOWN_5 ("zero movement"), act_walking
     * NEVER exits at zero stick (forwardVel oscillates around 0 forever instead of
     * braking to idle, exactly as SM64's exit at mario_actions_moving.c:799 expects). */
    if ((m->pos[1] > m->waterLevel - 40) && mario_floor_is_slippery(m)) {
        m->input |= INPUT_ABOVE_SLIDE; /* decl comes from game/mario.h */
    }
    if (m->pos[1] < (m->waterLevel - 10)) {
        m->input |= INPUT_IN_WATER;
    }
    if (!(m->input & (INPUT_NONZERO_ANALOG | INPUT_A_PRESSED))) {
        m->input |= INPUT_UNKNOWN_5;
    }
}

/* DSCE MIM-COHERENCE #4: set by z_play on the Mario-mask-don edge; consumed in the tick below to play
 * Mario's scream from the SAME context the act code plays his voice (play_sound + live cameraToObject),
 * which is the only place it actually renders -- a z_play-side play_sound was silent. */
int gDsceMarioScreamReq = 0;
extern void play_sound(s32 soundBits, f32* pos);

/* DSCE MIM-COHERENCE #1 (hurt reaction): set by z_player when an MM enemy hits Mario's AC cylinder.
 * The tick applies SM64's real knockback to gMarioState (KB action + backward velocity), so he reacts +
 * gets knocked back like in SM64 instead of MM's reaction. Yaw = MM angle from Mario toward the attacker. */
int gDsceMarioKbReq = 0;
s16 gDsceMarioKbYaw = 0;
int gDsceMarioKbDmg = 0;
/* 1 while Mario is invulnerable in SM64 terms (an INVULNERABLE action like the KB, or the post-hit
 * invincTimer is running). z_player reads it to skip registering his AC, so enemies can't re-hit him
 * during the knockback/recovery (it was easy to soft-lock). */
int gDsceMarioInvuln = 0;
/* 1 while Mario's SM64 action is in the SUBMERGED (swimming) group. z_play reads it to switch the MM
 * camera to Zora's underwater swim setting (CAM_SET_WATER2) so the camera follows him while diving. */
int gDsceMarioUnderwater = 0;
/* MIM-COHERENCE: 1 while Mario is ground-pounding (z_play uses it to detect a pound onto a Deku flower).
 * z_play sets gDsceMarioBounceReq when that happens; the tick consumes it into a spinning bounce. */
int gDsceMarioGroundPounding = 0;
int gDsceMarioBounceReq = 0;
/* DSCE: speed Mario's MOVEMENT (physics) up toward native real-time. The sandbox ticks once per MM
 * frame (~20fps) but SM64 constants assume 30fps, so movement runs ~66% speed. We run the physics step
 * this many times per tick (averaged via an accumulator) to restore native pace -- collision/floor-snap
 * stay correct because each step does its own collision. The DISPLAYED animation still advances only
 * 1x per tick (below), so it keeps the intended 20fps look. The host sets this from gDsce.MarioSpeedMul. */
#include "../../dsce_tuning.h"
#if DSCE_XTEST && !DSCE_XTEST_SHIPPED
/* XTEST pure tier: the oracle comparison runs the kernel PURE -- the 1.5x wall-clock
 * feel compensation is the F2 DESIGN DECISION (kept; see test-xtest-shipped, which
 * verifies the shipped multiplier stays CONFINED to horizontal displacement). */
float gDsceMarioSpeedMul = 1.0f;
#else
float gDsceMarioSpeedMul = DSCE_MarioSpeedMul; /* tuning.yaml */
#endif
/* From interaction.c -- execute_mario_action runs this before the act loop; triggers the lava-boost on a
 * SURFACE_BURNING floor (our dangerous-water adapter). Declared here since the sandbox omits interaction.h. */
extern void mario_handle_special_floors(struct MarioState* m);

/* Apply the 20->30fps horizontal feel compensation without bypassing SM64's collision
 * contract.  The action step has already resolved its native endpoint; the extra fraction
 * is a NEW movement and therefore needs its own body collision pass before publication.
 * Keeping this here (rather than changing forwardVel) preserves native action thresholds,
 * jump height, vertical motion, and animation timing. */
static void sandbox_apply_horizontal_speed(struct MarioState* m, f32 prevX, f32 prevZ, f32 mul) {
    Vec3f pos;
    struct Surface* lowerWall = NULL;
    struct Surface* upperWall = NULL;
    struct Surface* floor = NULL;

    if ((mul <= 1.0f) || ((m->pos[0] == prevX) && (m->pos[2] == prevZ))) {
        return;
    }

    pos[0] = prevX + mul * (m->pos[0] - prevX);
    pos[1] = m->pos[1];
    pos[2] = prevZ + mul * (m->pos[2] - prevZ);

    if ((m->action & ACT_GROUP_MASK) == ACT_GROUP_SUBMERGED) {
        /* perform_water_quarter_step's body volume */
        lowerWall = resolve_and_return_wall_collisions(pos, 10.0f, 110.0f);
    } else if (m->action & ACT_FLAG_AIR) {
        /* perform_air_quarter_step: head first, then lower body */
        upperWall = resolve_and_return_wall_collisions(pos, 150.0f, 50.0f);
        lowerWall = resolve_and_return_wall_collisions(pos, 30.0f, 50.0f);
    } else {
        /* perform_ground_quarter_step: feet first, then upper body */
        lowerWall = resolve_and_return_wall_collisions(pos, 30.0f, 24.0f);
        upperWall = resolve_and_return_wall_collisions(pos, 60.0f, 50.0f);
    }

    /* A missing floor means MM supplied no collision below this X/Z: that is an
     * outside-the-scene void, not a walkable ledge.  SM64's ordinary quarter-step
     * rejects such X/Z endpoints; the 1.5x post-step must obey the same atomic
     * acceptance rule instead of publishing a position actions cannot escape. */
    (void)find_floor(pos[0], pos[1], pos[2], &floor);
    if (floor == NULL) {
        return;
    }

    m->pos[0] = pos[0];
    m->pos[2] = pos[2];
    if (upperWall != NULL) {
        m->wall = upperWall;
    } else if (lowerWall != NULL) {
        m->wall = lowerWall;
    }
}

void Dsce_MarioSandboxTick(float stickX, float stickY, unsigned short btnDown, unsigned short btnPressed,
                           short camYaw) {
    struct MarioState* m = gMarioState;
    s32 inLoop = 1;
    int prevAuth;
    f32 tickStartX;
    f32 tickStartZ;

    if (!sSandboxReady || (m->action == 0)) {
        return;
    }
    sSandboxCtrl.stickX = stickX;
    sSandboxCtrl.stickY = stickY;
    sSandboxCtrl.stickMag = (f32)sqrtf(stickX * stickX + stickY * stickY);
    if (sSandboxCtrl.stickMag > 64.0f) {
        sSandboxCtrl.stickMag = 64.0f;
    }
    sSandboxCtrl.buttonDown = btnDown;
    sSandboxCtrl.buttonPressed = btnPressed;

    /* Re-bind the scaffolding pointers EVERY tick: the host's event/object runtime (brought up for
     * the EventSystem the act code needs) can re-init gMarioState between frames, leaving marioObj
     * NULL -> the ACT_WALKING write m->marioObj->oMarioWalkingPitch faults. Cheap to re-assert. */
    m->controller = &sSandboxCtrl;
    m->marioObj = &sSandboxObj;
    m->marioBodyState = &sSandboxBody;
    m->statusForCamera = &sSandboxCamState;
    m->spawnInfo = &sSandboxSpawn;
    m->area = &sSandboxArea;
    { /* [DSCE N64] anim plumbing must be non-NULL (see dsce_sm64_support.c) */
        extern struct DmaHandlerList gDsceAnimList;
        m->animList = &gDsceAnimList;
    }

    prevAuth = gDsceWorldAuthority;
    gDsceWorldAuthority = DSCE_AUTH_MM; /* route find_floor/walls -> MM BgCheck for this tick */

    sandbox_update_inputs(m, camYaw);
    tickStartX = m->pos[0];
    tickStartZ = m->pos[2];

    /* DSCE MIM-COHERENCE #1 (hurt reaction): an MM enemy hit Mario -> do SM64's real knockback. Face the
     * attacker + backward velocity so he flies away, in the SM64 KB action (plays the KB animation). */
    if (gDsceMarioKbReq) {
        gDsceMarioKbReq = 0;
        m->faceAngle[1] = gDsceMarioKbYaw;
        m->forwardVel = -32.0f; /* knocked backward, away from the attacker */
        m->vel[1] = 20.0f;      /* pop up so he tumbles onto his butt rather than just sliding */
        m->hurtCounter += (gDsceMarioKbDmg > 0 ? gDsceMarioKbDmg : 1) * 4;
        /* No extra invincTimer: real SM64's take_damage_from_interact_object doesn't set one -- the
         * invulnerability is exactly the knockback action's ACT_FLAG_INVULNERABLE window (handled below). */
        /* HARD backward KB = the SM64 "knocked on his butt" reaction (soft is just a stumble). */
        set_mario_action(m, (m->action & ACT_FLAG_AIR) ? ACT_HARD_BACKWARD_AIR_KB : ACT_HARD_BACKWARD_GROUND_KB,
                         0);
    }
    /* MIM-COHERENCE: ground-pounded onto a Deku flower -> SM64 spinning bounce (like bouncing off a flying
     * enemy). High upward velocity + ACT_TWIRLING with actionArg=1 so it plays MARIO_ANIM_TWIRL (the spin). */
    if (gDsceMarioBounceReq) {
        gDsceMarioBounceReq = 0;
        m->vel[1] = 195.0f; /* 3x the base bounce */
        m->forwardVel = 0.0f;
        set_mario_action(m, ACT_TWIRLING, 1);
    }
    /* SM64-native invulnerability: count down invincTimer (the sandbox doesn't run mario_update, which
     * normally does it) and publish whether Mario is currently invulnerable (KB/invuln action or timer). */
    if (m->invincTimer > 0) {
        m->invincTimer--;
    }
    gDsceMarioInvuln = ((m->action & ACT_FLAG_INVULNERABLE) || (m->invincTimer > 0)) ? 1 : 0;
    gDsceMarioUnderwater = ((m->action & ACT_GROUP_MASK) == ACT_GROUP_SUBMERGED) ? 1 : 0;
    gDsceMarioGroundPounding = (m->action == ACT_GROUND_POUND) ? 1 : 0;
    /* DSCE: SM64-style swimming with NO loss of breath -- keep health topped so the swim never drains it
     * to ACT_DROWNING. The form's real health is MM's hearts; SM64 m->health is cosmetic here. */
    m->health = 0x0880;
    /* DSCE MIM-COHERENCE #2: water is now REAL -- find_water_level is answered by MM's WaterBoxes
     * (Dsce_AdapterFindWater), so the act code enters the SUBMERGED group only when actually in water.
     * The old unconditional SUBMERGED -> FREEFALL "no water" stopgap is removed so swimming works. */
    /* DSCE MIM-COHERENCE #3 (hazards): on a SURFACE_BURNING floor (set by the dangerous-floor adapter),
     * do SM64's lava-boost. INLINE, not via mario_handle_special_floors / check_lava_boost -- those also
     * run warp/death-plane/slide handling and update_mario_sound_and_camera, and the latter aborted in the
     * sandbox (libc++abi terminating). This is the boost minus the unsafe sound/camera call; the
     * ACT_LAVA_BOOST handler itself runs fine (it's an ordinary airborne act). Grounded-only (not air,
     * not swimming) -- the only underwater burning case is poison water, handled separately just below. */
    if ((m->floor != NULL) && (m->floor->type == SURFACE_BURNING) && (m->action != ACT_LAVA_BOOST) &&
        !(m->action & ACT_FLAG_AIR) && !(m->action & ACT_FLAG_SWIMMING)) {
        if (!(m->flags & MARIO_METAL_CAP)) {
            m->hurtCounter += (m->flags & MARIO_CAP_ON_HEAD) ? 12 : 18;
        }
        set_mario_action(m, ACT_LAVA_BOOST, 0);
    }
    /* Southern Swamp poison water: SM64 has no "swim in dangerous water" reaction, so bounce Mario off the
     * poison SURFACE whenever MM would be poisoning him (Dsce_MarioInPoisonWater = at/below the water line).
     * Surface-triggered, not floor-based: fires right at the water surface regardless of depth, so he never
     * sinks into the poison. No ACT_FLAG_AIR gate -- fire the instant he dips below the surface so he's
     * repelled at the surface; the ACT_LAVA_BOOST guard stops re-firing during the boost itself. */
    {
        extern int Dsce_MarioInPoisonWater(void);
        if ((m->action != ACT_LAVA_BOOST) && Dsce_MarioInPoisonWater()) {
            /* Force his pain sound NOW so it lands as he's repelled, instead of the water-entry act's
             * splash/swim sound (which the lava-boost's own ON_FIRE yell -- gated behind
             * MARIO_MARIO_SOUND_PLAYED -- often never interrupts). Set the flag so the boost act doesn't
             * also yell on top of this. */
            play_sound(SOUND_MARIO_ATTACKED, m->marioObj->header.gfx.cameraToObject);
            m->flags |= MARIO_MARIO_SOUND_PLAYED;
            set_mario_action(m, ACT_LAVA_BOOST, 0);
        }
    }
    /* Mario's SM64 trait: floating at a (non-poison) water surface recovers health. The heal lands on MM's
     * hearts (host side); when a heart wedge fills, play SM64's power-meter "ding" so it sounds like SM64. */
    {
        extern int Dsce_MarioWaterSurfaceHeal(void);
        if (Dsce_MarioWaterSurfaceHeal()) {
            play_sound(SOUND_MENU_POWER_METER, m->marioObj->header.gfx.cameraToObject);
        }
    }
    if (m->floor != NULL) {
        /* One physics step per tick (smooth, normal animation cadence). To make him cover ground at
         * native real-time pace without touching the animation, scale only the HORIZONTAL displacement
         * this step produced by gDsceMarioSpeedMul. Vertical (jump/gravity/floor-snap) is left native so
         * he never jitters on the ground or floats; the anim advances 1x below at its normal speed, so
         * his legs simply animate a touch slower than he glides -- which is fine. */
        f32 prevX = m->pos[0];
        f32 prevZ = m->pos[2];
        f32 mul = gDsceMarioSpeedMul;
        if (mul < 1.0f) {
            mul = 1.0f;
        }
        inLoop = 1;
        {
        int dsceGuard = 0;
        while (inLoop) {
            /* [DSCE N64] wedge guard: cap the dispatch loop so a ping-ponging action can't
             * hang the console (a NULL animList once wedged here). */
            if (++dsceGuard > 64) {
                break;
            }
            switch (m->action & ACT_GROUP_MASK) {
                case ACT_GROUP_STATIONARY:
                    inLoop = mario_execute_stationary_action(m);
                    break;
                case ACT_GROUP_MOVING:
                    inLoop = mario_execute_moving_action(m);
                    break;
                case ACT_GROUP_AIRBORNE:
                    inLoop = mario_execute_airborne_action(m);
                    break;
                case ACT_GROUP_SUBMERGED:
                    inLoop = mario_execute_submerged_action(m);
                    break;
                case ACT_GROUP_CUTSCENE:
                    inLoop = mario_execute_cutscene_action(m);
                    break;
                case ACT_GROUP_AUTOMATIC:
                    inLoop = mario_execute_automatic_action(m);
                    break;
                case ACT_GROUP_OBJECT:
                    inLoop = mario_execute_object_action(m);
                    break;
                default:
                    inLoop = 0;
                    break;
            }
        }
        }
        sandbox_apply_horizontal_speed(m, prevX, prevZ, mul);

    }

    sandbox_update_published_facing(m, tickStartX, tickStartZ);

#if DSCE_DBG_GAMEPLAY
    { /* kernel.action: transitions only */
        extern void Dsce_Fh(unsigned char, unsigned short, int, int, int, int);
        static unsigned int sFhPrevAct = 0;
        if (m->action != sFhPrevAct) {
            Dsce_Fh(5, 0, (int)m->action, (int)sFhPrevAct, (int)m->forwardVel, 0);
            sFhPrevAct = m->action;
        }
    }
#endif

    /* SM64 execute_mario_action runs squish_mario_model AFTER the act loop; the sandbox omitted it,
     * so a hard-fall squish (squishTimer=30, e.g. dropping into the Termina Field sand pit -- flat
     * non-slippery floor takes the fall-damage branch) NEVER counted down. While squishTimer != 0,
     * set_mario_action_airborne downgrades DOUBLE_JUMP/TWIRLING to plain ACT_JUMP -- the "stuck on
     * jump 1 with less height, forever" bug. Vendor the call: it decrements the timer and restores
     * the model scale, exactly like the original frame loop. */
    {
        extern void squish_mario_model(struct MarioState* m);
        squish_mario_model(m);
    }

    /* DSCE MIM-COHERENCE #4: play Mario's mask-don scream here -- the SAME context (and live
     * cameraToObject) the act code uses for his voice, so it actually renders. z_play requests it on
     * the form-don edge; a z_play-side play_sound was silent. */
    if (gDsceMarioScreamReq > 0) {
        extern char* getenv(const char*);
        extern unsigned long strtoul(const char*, char**, int);
        const char* e = getenv("DSCE_SCREAM_SND");
        /* Use the EXACT call the working jump voice uses (play_mario_jump_sound): the soundBits at the
         * marioObj's cameraToObject pointer. That pointer is {0,0,0} in the sandbox and the jump is still
         * audible, so {0,0,0} is fine. DSCE_SCREAM_SND (hex) overrides the sound live for picking the
         * exact one (e.g. 0x2431FF80 game-over wail, 0x24228080 ground-pound WAH, 0x242B8080 yahoo). */
        s32 snd = (e != NULL) ? (s32)strtoul(e, NULL, 0)
                              : 0x24008080 /* TEST: jump-cry (soundId 0, the jump uses it + is audible) */;
        play_sound(snd, m->marioObj->header.gfx.cameraToObject);
        gDsceMarioScreamReq = 0; /* SINGLE play -- re-triggering a discrete sound every frame keeps it in
                                    WAITING and it never transitions to PLAYING (the burst self-defeated). */
    }

    /* Advance Mario's animation frame. SM64 normally does this during rendering
     * (geo_update_animation_frame); the sandbox doesn't render through SM64, so anim-gated actions
     * (punch, crouch, land, turnaround) would never satisfy is_anim_at_end and would FREEZE. Advance
     * forward with loop/no-loop handling. */
    {
        struct AnimInfo* ai = &m->marioObj->header.gfx.animInfo;
        struct Animation* anim = ai->curAnim;
        if (anim != NULL && !(anim->flags & ANIM_FLAG_2)) {
            /* [DSCE XGAME F4] VERBATIM port of geo_update_animation_frame (engine/graph_node.c).
             * The old stand-in stepped the stale animFrameAccelAssist even at animAccel==0, but
             * set_mario_animation resets animFrame (to startFrame-1) WITHOUT resetting the assist,
             * so every fresh anim jumped frames ahead and anim-gated actions (punch, crouch-start,
             * pound-land, lava-land) ended ticks early vs the oracle. The original advances from
             * animFrame+1 when accel is zero -- cross-game action durations now match. */
            s32 result;
            if (anim->flags & ANIM_FLAG_BACKWARD) {
                if (ai->animAccel != 0) {
                    result = ai->animFrameAccelAssist - ai->animAccel;
                } else {
                    result = (ai->animFrame - 1) << 16;
                }
                if ((s16)(result >> 16) < anim->loopStart) {
                    if (anim->flags & ANIM_FLAG_NOLOOP) {
                        result = (result & 0xFFFF) | ((s32)anim->loopStart << 16);
                    } else {
                        result = (result & 0xFFFF) | ((s32)(anim->loopEnd - 1) << 16);
                    }
                }
            } else {
                if (ai->animAccel != 0) {
                    result = ai->animFrameAccelAssist + ai->animAccel;
                } else {
                    result = (ai->animFrame + 1) << 16;
                }
                if ((s16)(result >> 16) >= anim->loopEnd) {
                    if (anim->flags & ANIM_FLAG_NOLOOP) {
                        result = (result & 0xFFFF) | ((s32)(anim->loopEnd - 1) << 16);
                    } else {
                        result = (result & 0xFFFF) | ((s32)anim->loopStart << 16);
                    }
                }
            }
            ai->animFrameAccelAssist = result;
            ai->animFrame = (s16)(result >> 16);
        }
    }

    gDsceWorldAuthority = prevAuth;
}

/* Diagnostic: report this TU's struct layout so the MM host can log it (the harness's own Dsce_Log is
 * stubbed in the colink). If marioObjOff != the colink's expectation (0xA8=168), the harness compiled
 * MarioState with a different layout than mario.c -> the act code reads marioObj from the wrong offset. */
void Dsce_MarioSandboxLayout(int* marioObjOff, int* objSz, int* msSz) {
    /* [DSCE N64] standard offsetof idiom -- IDO lacks __builtin_offsetof. */
    if (marioObjOff) *marioObjOff = (int)(long)&(((struct MarioState*)0)->marioObj);
    if (objSz) *objSz = (int)sizeof(struct Object);
    if (msSz) *msSz = (int)sizeof(struct MarioState);
}

/* Read Mario's state back in MM units for the host to apply to the actor. */
void Dsce_MarioSandboxGetState(float* mmx, float* mmy, float* mmz, short* facingYaw, short* visualYaw,
                               unsigned* action, float* fwdVel) {
    struct MarioState* m = gMarioState;
    f32 invk = (gDsceMmScale != 0.0f) ? (1.0f / gDsceMmScale) : 0.0f;
    if (mmx) *mmx = m->pos[0] * invk;
    if (mmy) *mmy = m->pos[1] * invk;
    if (mmz) *mmz = m->pos[2] * invk;
    /* SM64 deliberately keeps facing and graphics yaw separate during a twirl.  MM's
     * follow camera and collision actor must receive facingYaw; only the rendered Mario
     * actor receives visualYaw.  Folding twirlYaw into the player actor made the camera
     * orbit once per animation revolution during a Deku-flower bounce. */
    if (facingYaw) *facingYaw = sPublishedFacingYaw;
    if (visualYaw) {
        *visualYaw = sPublishedFacingYaw + ((m->action == ACT_TWIRLING) ? m->twirlYaw : 0);
    }
    if (action) *action = m->action;
    if (fwdVel) *fwdVel = m->forwardVel * invk;
}

/* ?? Headless atomic-move tests ?????????????????????????????????????????????????????????????????
 * Spoof exact controller input per move, run the REAL act handlers on the deterministic flat test
 * floor (gDsceMarioTestFloor -> find_floor/find_ceil), and record the resulting gMarioState.action vs
 * the expected SM64 action. The MM host calls Dsce_MarioRunTests() then logs each result. */
int gDsceMarioTestFloor = 0;

#define DSCE_MAX_TESTS 24
static struct {
    const char* name;
    unsigned expect;
    unsigned got;
    unsigned input;
    int pass;
} sDsceTests[DSCE_MAX_TESTS];
static int sDsceNumTests = 0;

static void t_reset(void) {
    struct MarioState* m = gMarioState;
    bzero(&sSandboxCtrl, sizeof(sSandboxCtrl));
    m->controller = &sSandboxCtrl;
    m->marioObj = &sSandboxObj;
    m->marioBodyState = &sSandboxBody;
    m->statusForCamera = &sSandboxCamState;
    m->spawnInfo = &sSandboxSpawn;
    m->area = &sSandboxArea;
    { /* [DSCE N64] anim plumbing must be non-NULL (see dsce_sm64_support.c) */
        extern struct DmaHandlerList gDsceAnimList;
        m->animList = &gDsceAnimList;
    }
    m->pos[0] = 0.0f; m->pos[1] = 0.0f; m->pos[2] = 0.0f;
    m->vel[0] = m->vel[1] = m->vel[2] = 0.0f;
    m->faceAngle[0] = m->faceAngle[1] = m->faceAngle[2] = 0;
    m->forwardVel = 0.0f;
    m->action = ACT_IDLE;
    m->prevAction = ACT_IDLE;
    m->actionState = 0;
    m->actionTimer = 0;
    m->actionArg = 0;
    m->input = 0;
    m->flags = MARIO_NORMAL_CAP | MARIO_CAP_ON_HEAD;
    m->health = 0x0880;
    m->waterLevel = -20000;
    m->floor = NULL;
    m->wall = NULL;
    m->ceil = NULL;
    m->framesSinceA = 0xFF;
    m->framesSinceB = 0xFF;
    m->squishTimer = 0;
    sandbox_reset_published_facing(0);
    sSandboxReady = 1;
}
static void t_record(const char* name, unsigned expect) {
    if (sDsceNumTests < DSCE_MAX_TESTS) {
        sDsceTests[sDsceNumTests].name = name;
        sDsceTests[sDsceNumTests].expect = expect;
        sDsceTests[sDsceNumTests].got = gMarioState->action;
        sDsceTests[sDsceNumTests].input = gMarioState->input;
        sDsceTests[sDsceNumTests].pass = (gMarioState->action == expect);
        sDsceNumTests++;
    }
}

static void t_record_value(const char* name, unsigned expect, unsigned got) {
    if (sDsceNumTests < DSCE_MAX_TESTS) {
        sDsceTests[sDsceNumTests].name = name;
        sDsceTests[sDsceNumTests].expect = expect;
        sDsceTests[sDsceNumTests].got = got;
        sDsceTests[sDsceNumTests].input = 0;
        sDsceTests[sDsceNumTests].pass = (got == expect);
        sDsceNumTests++;
    }
}

void Dsce_MarioRunTests(void) {
    int i;
    gDsceMarioTestFloor = 1;
    sDsceNumTests = 0;

    // idle: no input stays idle
    t_reset();
    Dsce_MarioSandboxTick(0, 0, 0, 0, 0);
    Dsce_MarioSandboxTick(0, 0, 0, 0, 0);
    t_record("idle", ACT_IDLE);

    // walk: gentle stick forward
    t_reset();
    for (i = 0; i < 6; i++) Dsce_MarioSandboxTick(40, 40, 0, 0, 0);
    t_record("walk", ACT_WALKING);

    // single jump: A from idle
    t_reset();
    Dsce_MarioSandboxTick(0, 0, A_BUTTON, A_BUTTON, 0);
    t_record("jump", ACT_JUMP);

    // crouch: Z held, still, grounded
    t_reset();
    Dsce_MarioSandboxTick(0, 0, Z_TRIG, Z_TRIG, 0);
    t_record("crouch", ACT_START_CROUCHING);

    // backflip: Z held then A, still
    t_reset();
    Dsce_MarioSandboxTick(0, 0, Z_TRIG, Z_TRIG, 0);
    Dsce_MarioSandboxTick(0, 0, Z_TRIG | A_BUTTON, A_BUTTON, 0);
    t_record("backflip", ACT_BACKFLIP);

    // long jump: build run speed, then Z + A while moving
    t_reset();
    for (i = 0; i < 10; i++) Dsce_MarioSandboxTick(64, 64, 0, 0, 0);
    Dsce_MarioSandboxTick(64, 64, Z_TRIG, Z_TRIG, 0);
    Dsce_MarioSandboxTick(64, 64, Z_TRIG | A_BUTTON, A_BUTTON, 0);
    t_record("longjump", ACT_LONG_JUMP);

    // dive: at FULL run speed + B (at walk speed B punches instead -- that's correct SM64, so build speed)
    t_reset();
    for (i = 0; i < 40; i++) Dsce_MarioSandboxTick(64, 64, 0, 0, 0);
    Dsce_MarioSandboxTick(64, 64, B_BUTTON, B_BUTTON, 0);
    t_record("dive", ACT_DIVE);

    // ground pound: jump, then Z while airborne
    t_reset();
    Dsce_MarioSandboxTick(0, 0, A_BUTTON, A_BUTTON, 0);
    Dsce_MarioSandboxTick(0, 0, Z_TRIG, Z_TRIG, 0);
    t_record("groundpound", ACT_GROUND_POUND);

    // punch_exits: B from standing -> punch, then it must FINISH (anim advance) and return to idle,
    // not freeze. Regression for the "punching gets me stuck" bug.
    t_reset();
    Dsce_MarioSandboxTick(0, 0, B_BUTTON, B_BUTTON, 0);
    for (i = 0; i < 40; i++) Dsce_MarioSandboxTick(0, 0, 0, 0, 0);
    t_record("punch_exits", ACT_IDLE);

    /* Movement-led twirl camera: exercise the filter directly so the regression suite
     * covers UX behavior that is deliberately independent of the action result. */
    t_reset();
    gMarioState->action = ACT_TWIRLING;
    gMarioState->faceAngle[1] = 0x2000;
    sandbox_reset_published_facing(0x2000);
    sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    t_record_value("twirl_stationary_hold", 0x2000, (u16)sPublishedFacingYaw);

    /* Eight bounded steps rotate from north to accepted +X travel, never snapping. */
    gMarioState->faceAngle[1] = 0;
    sandbox_reset_published_facing(0);
    for (i = 0; i < 8; i++) {
        gMarioState->pos[0] = 4.0f;
        gMarioState->pos[2] = 0.0f;
        sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    }
    t_record_value("twirl_follows_motion", 0x4000, (u16)sPublishedFacingYaw);

    /* Sub-threshold depenetration and a single reverse collision sample cannot
     * perturb or whip the established view. */
    gMarioState->pos[0] = 0.25f;
    sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    t_record_value("twirl_rejects_noise", 0x4000, (u16)sPublishedFacingYaw);
    gMarioState->pos[0] = -4.0f;
    sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    t_record_value("twirl_rejects_reverse_spike", 0x4000, (u16)sPublishedFacingYaw);

    /* A sustained about-face is intentional: accept it after three coherent samples,
     * then slew toward it at the same bounded rate. */
    sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    t_record_value("twirl_accepts_reverse", 0x3800, (u16)sPublishedFacingYaw);

    /* Landing hands authority back to ordinary facing without a one-frame snap. */
    gMarioState->action = ACT_IDLE;
    gMarioState->faceAngle[1] = 0;
    sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    t_record_value("twirl_landing_blend", 0x2800, (u16)sPublishedFacingYaw);
    for (i = 0; i < 7; i++) {
        sandbox_update_published_facing(gMarioState, 0.0f, 0.0f);
    }
    t_record_value("twirl_landing_settles", 0, (u16)sPublishedFacingYaw);

    gDsceMarioTestFloor = 0;
}
int Dsce_MarioTestCount(void) {
    return sDsceNumTests;
}
const char* Dsce_MarioTestName(int i) {
    return (i >= 0 && i < sDsceNumTests) ? sDsceTests[i].name : "";
}
void Dsce_MarioTestGet(int i, int* pass, unsigned* expect, unsigned* got) {
    if (i >= 0 && i < sDsceNumTests) {
        if (pass) *pass = sDsceTests[i].pass;
        if (expect) *expect = sDsceTests[i].expect;
        if (got) *got = sDsceTests[i].got;
    }
}
unsigned Dsce_MarioTestInput(int i) {
    return (i >= 0 && i < sDsceNumTests) ? sDsceTests[i].input : 0;
}

/* The SM64 animation the CURRENT action selected (set_mario_animation) + its frame -- so the MM mesh
 * plays the authentic 1:1 animation the real code chose, not a guess. animID is the MARIO_ANIM_* value. */
/* [DSCE Phase 2] Evaluate the CURRENT animation at the CURRENT frame into per-part
 * rotations (+ root translation), for the MM-side hierarchical draw. Mirrors SM64's
 * geo_process_animated_part index math (u16 pairs: count, offset; clamp past the end;
 * 6 u16 per slot; slot 0 = root translation, slots 1..20 = part rotations). */
static s32 dsce_anim_index(s32 frame, const u16** attr) {
    u16 count = (*attr)[0];
    u16 offset = (*attr)[1];
    s32 result;
    if (count == 0) {
        result = (s32)offset; /* degenerate (fake anim) -- stay in bounds */
    } else if (frame < (s32)count) {
        result = (s32)offset + frame;
    } else {
        result = (s32)offset + (s32)count - 1;
    }
    *attr += 2;
    return result;
}

static int dsce_eval_anim_pose(const struct Animation* anim, s32 frame, short outTrans[3], short outRot[][3]) {
    const u16* attr;
    const s16* vals;
    s32 i;
    s32 j;

    if ((anim == NULL) || (anim->index == NULL) || (anim->values == NULL)) {
        return 0;
    }
    if (frame < 0) {
        frame = 0;
    }
    attr = anim->index;
    vals = anim->values;
    for (i = 0; i < 3; i++) {
        outTrans[i] = vals[dsce_anim_index(frame, &attr)];
    }
    for (i = 0; i < 20; i++) {
        for (j = 0; j < 3; j++) {
            outRot[i][j] = vals[dsce_anim_index(frame, &attr)];
        }
    }
    return 1;
}

int Dsce_MarioAnimPose(short outTrans[3], short outRot[][3]) {
    struct MarioState* m = gMarioState;
    struct AnimInfo* ai;

    if (!sSandboxReady || (m->marioObj == NULL)) {
        return 0;
    }
    ai = &m->marioObj->header.gfx.animInfo;
    return dsce_eval_anim_pose(ai->curAnim, ai->animFrame, outTrans, outRot);
}

/* PC singing override: evaluate a chosen SM64 animation on an independent clock.
 * The movement sandbox continues to idle under MM's ocarina modal, so borrowing its
 * action-selected anim would either freeze or be replaced by ACT_IDLE every frame. */
int Dsce_MarioAnimPoseById(s32 animId, s32 frame, short outTrans[3], short outRot[][3]) {
    extern const struct Animation* const gDsceMarioAnimTable[];
    extern const int gDsceMarioAnimTableLen;
    const struct Animation* anim;
    s32 span;

    if ((animId < 0) || (animId >= gDsceMarioAnimTableLen)) {
        return 0;
    }
    anim = gDsceMarioAnimTable[animId];
    if (anim == NULL) {
        return 0;
    }
    span = (s32)anim->loopEnd - (s32)anim->loopStart;
    if (span > 0) {
        frame = anim->loopStart + (frame % span);
    }
    return dsce_eval_anim_pose(anim, frame, outTrans, outRot);
}

/* [DSCE Phase 2b] Body state for the draw: eye state, resolved hand case (SM64's
 * geo_switch_mario_hand semantics incl. the swimming open-palms rule), torso tilt and
 * head turn angles (written per tick by the vendored walking/swimming act code), and
 * the anim root-translation multiplier (animYTrans/divisor -- 1.0 for standard anims). */
int Dsce_MarioBodyState(short out[10]) {
    struct MarioState* m = gMarioState;
    struct MarioBodyState* bs;
    struct Animation* anim;
    s32 hand;
    s32 mulQ8 = 0;

    if (!sSandboxReady || (m->marioBodyState == NULL)) {
        return 0;
    }
    bs = m->marioBodyState;
    if (bs->handState == 0) { /* MARIO_HAND_FISTS: open palms while swimming/flying */
        hand = ((m->action & ACT_FLAG_SWIMMING_OR_FLYING) != 0) ? 1 : 0;
    } else {
        hand = (bs->handState < 5) ? bs->handState : 1;
    }
    if ((m->marioObj != NULL) && (m->marioObj->header.gfx.animInfo.curAnim != NULL)) {
        anim = m->marioObj->header.gfx.animInfo.curAnim;
        if (anim->animYTransDivisor != 0) {
            mulQ8 = (s32)(((f32)m->marioObj->header.gfx.animInfo.animYTrans /
                           (f32)anim->animYTransDivisor) * 256.0f);
        }
    }
    out[0] = (short)bs->eyeState;
    out[1] = (short)hand;
    out[2] = bs->torsoAngle[0];
    out[3] = bs->torsoAngle[1];
    out[4] = bs->torsoAngle[2];
    out[5] = bs->headAngle[0];
    out[6] = bs->headAngle[1];
    out[7] = bs->headAngle[2];
    out[8] = (short)mulQ8;
    out[9] = 0;
    return 1;
}

int Dsce_MarioSandboxAnimId(void) {
    return (int)gMarioState->marioObj->header.gfx.animInfo.animID;
}
int Dsce_MarioSandboxAnimFrame(void) {
    return (int)gMarioState->marioObj->header.gfx.animInfo.animFrame;
}

/* Diagnostic readout to pin why an action freezes (full action, water level, floor-null, canonical Y). */
void Dsce_MarioSandboxDebug(unsigned* action, int* waterLvl, int* floorNull, int* posYcanon) {
    struct MarioState* m = gMarioState;
    if (action) *action = m->action;
    if (waterLvl) *waterLvl = (int)m->waterLevel;
    if (floorNull) *floorNull = (m->floor == NULL) ? 1 : 0;
    if (posYcanon) *posYcanon = (int)m->pos[1];
}
