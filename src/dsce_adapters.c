/* [DSCE N64] BgCheck adapters -- MM-side half of the collision bridge. Ported from the PC mod
 * (2s2h/mm/src/code/z_play.c:1153?1241) with CVars baked via dsce_tuning.h. The SM64 kernel's
 * find_floor/find_walls/find_water (dsce_sm64_support.c) call these; the spike actor publishes
 * gDsceAuthorityPlay each Update. Phase P: poison/heal report "no" (hazards are Phase 1). */
#include "global.h"
#include "dsce_tuning.h"
#include "dsce_config.h" /* DSCE_DEBUG flag */

#ifndef DSCE_MmScale
#define DSCE_MmScale 4.29f
#endif

PlayState* gDsceAuthorityPlay = NULL;
int gDsceWorldAuthority = 0;   /* 1 (DSCE_AUTH_MM) while the sandbox ticks */
float gDsceMmScale = DSCE_MmScale;


int Dsce_AdapterFindFloor(float sx, float sy, float sz, float* outHeight, float* outNx, float* outNy,
                          float* outNz, int* outDanger) {
    PlayState* play = gDsceAuthorityPlay;
    f32 k = gDsceMmScale;
    f32 invk = (k != 0.0f) ? (1.0f / k) : 0.0f;
    CollisionPoly* poly = NULL;
    s32 bgId = 0;
    Vec3f pos;
    f32 fy;

    if ((play == NULL) || (invk == 0.0f)) {
        return 0;
    }
    /* SM64 -> MM, raycasting from a hair above the query point so a floor exactly at the
     * object's feet is still caught (BgCheck raycasts downward from pos.y). */
    pos.x = sx * invk;
    pos.y = sy * invk + 50.0f;
    pos.z = sz * invk;
    fy = BgCheck_EntityRaycastFloor3(&play->colCtx, &poly, &bgId, &pos);
    if ((fy <= BGCHECK_Y_MIN) || (poly == NULL)) {
        return 0; /* no MM floor under the object -> SM64 sees empty, it falls */
    }
    *outHeight = fy * k; /* MM -> SM64 */
    CollisionPoly_GetNormalF(poly, outNx, outNy, outNz);
    if (outDanger != NULL) {
        /* same-poly hazard read (lava FloorType 2/3/9 or damage type) -- NO second raycast:
         * the separate Dsce_AdapterFloorIsDangerous doubled per-query cost and blew the
         * suite's tick budget (13-18ms vs 12ms); the tests caught it. */
        s32 floorType = SurfaceType_GetFloorType(&play->colCtx, poly, bgId);
        *outDanger = (floorType == FLOOR_TYPE_2) || (floorType == FLOOR_TYPE_3) ||
                     (floorType == FLOOR_TYPE_9) || SurfaceType_IsWallDamage(&play->colCtx, poly, bgId);
    }
    return 1;
}

int Dsce_AdapterFindWalls(float sx, float sy, float sz, float prevSx, float prevSy, float prevSz,
                          float radius, float* outDispX, float* outDispZ, float* outNx, float* outNy,
                          float* outNz, int* outDanger) {
    PlayState* play = gDsceAuthorityPlay;
    f32 k = gDsceMmScale;
    f32 invk = (k != 0.0f) ? (1.0f / k) : 0.0f;
    CollisionPoly* poly = NULL;
    s32 bgId = BGCHECK_SCENE;
    Vec3f next;
    Vec3f result;
    Vec3f prev;
#if DSCE_DBG_GAMEPLAY
    extern u32 gDsceProbe[4];
    gDsceProbe[0]++; /* cumulative MM wall-adapter queries */
#endif

    if (outDanger != NULL) {
        *outDanger = 0;
    }
    if ((play == NULL) || (invk == 0.0f)) {
        return 0;
    }
    next.x = sx * invk;
    next.y = sy * invk;
    next.z = sz * invk;
    prev.x = prevSx * invk;
    prev.y = prevSy * invk;
    prev.z = prevSz * invk;
    result = next;
    if (BgCheck_EntitySphVsWall3(&play->colCtx, &result, &next, &prev, radius * invk, &poly, &bgId, NULL,
                                 20.0f)) {
        *outDispX = result.x * k;
        *outDispZ = result.z * k;
        CollisionPoly_GetNormalF(poly, outNx, outNy, outNz);
        if (outDanger != NULL) {
            *outDanger = SurfaceType_IsWallDamage(&play->colCtx, poly, bgId);
        }
#if DSCE_DBG_GAMEPLAY
        gDsceProbe[1]++; /* cumulative detected wall contacts */
        /* Last MM-space push-out, signed fixed-point (1/100 world unit). The input
         * plugin exposes these four words as PEEK rows in debug headless runs. */
        gDsceProbe[2] = (u32)(s32)((result.x - next.x) * 100.0f);
        gDsceProbe[3] = (u32)(s32)((result.z - next.z) * 100.0f);
#endif
        return 1;
    }
    return 0;
}

int Dsce_AdapterFindWater(float sx, float sz, float* outSurf) {
    PlayState* play = gDsceAuthorityPlay;
    f32 k = gDsceMmScale;
    f32 invk = (k != 0.0f) ? (1.0f / k) : 0.0f;
    f32 ySurface;
    WaterBox* wb = NULL;

    if ((play == NULL) || (invk == 0.0f)) {
        return 0;
    }
    if (WaterBox_GetSurface1(play, &play->colCtx, sx * invk, sz * invk, &ySurface, &wb)) {
        *outSurf = ySurface * k;
        return 1;
    }
    return 0;
}

int Dsce_AdapterFindCeil(float sx, float sy, float sz, float* outHeight) {
    PlayState* play = gDsceAuthorityPlay;
    f32 k = gDsceMmScale;
    f32 invk = (k != 0.0f) ? (1.0f / k) : 0.0f;
    CollisionPoly* poly = NULL;
    s32 bgId = 0;
    Vec3f pos;
    f32 cy;

    if ((play == NULL) || (invk == 0.0f)) {
        return 0;
    }
    pos.x = sx * invk;
    pos.y = sy * invk;
    pos.z = sz * invk;
    /* checkHeight ~ Mario's height in MM units so ceilings just above his head register */
    if (BgCheck_EntityCheckCeiling(&play->colCtx, &cy, &pos, 50.0f, &poly, &bgId, NULL)) {
        *outHeight = cy * k; /* MM -> SM64 */
        return 1;
    }
    return 0;
}

u32 gDsceVoiceReqs = 0; /* voice sfx requests (telemetry: proves Mario isn't silent) */
u32 gDsceFoleyReqs = 0; /* non-voice movement/terrain sfx requests */

/* [DSCE MSFX] the SM64-sound mint (PC parity). key = (sm64Bank << 8) | soundID; every
 * kernel-reachable id resolves to a minted NA_SE playing the REAL SM64 sample, rendered
 * exactly as SM64's sound player performs that id. Map generated by gen_mario_sfx.py;
 * table headers + samples staged into the mm tree by stage-mario-sfx.sh. */
#include "dsce_msfx_map.h"
void Dsce_AdapterPlayMsfx(int key) {
    PlayState* play = gDsceAuthorityPlay;
    Player* player;
    s32 lo = 0;
    s32 hi = DSCE_MSFX_MAP_LEN - 1;
    s32 mid;
    u16 id = 0;

    while (lo <= hi) {
        mid = (lo + hi) / 2;
        if (sDsceMsfxKeys[mid] == (u16)key) {
            id = sDsceMsfxIds[mid];
            break;
        }
        if (sDsceMsfxKeys[mid] < (u16)key) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    if (id == 0 || play == NULL) {
#if DSCE_DBG_GAMEPLAY
        if (id == 0) {
            extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
            Dsce_Fh(6, 1, key, 0, 0, 0); /* tag 1 = unmapped miss */
        }
#endif
        return;
    }
    player = GET_PLAYER(play);
    if (player == NULL) {
        return;
    }
#if DSCE_DBG_GAMEPLAY
    { /* kernel.sound: every SM64 soundBits resolution, hit or miss */
        extern void Dsce_Fh(u8, u16, s32, s32, s32, s32);
        Dsce_Fh(6, 0, key, id, 0, 0);
    }
#endif
    Audio_PlaySfx_AtPos(&player->actor.projectedPos, id);
    /* Bank 2 is SM64's voice bank.  Before the sound mint, the dedicated voice
     * adapter maintained this split; counting every minted request as foley made
     * the voice telemetry claim Mario was silent while his real samples played. */
    if ((((u32)key >> 8) & 0xF) == 2) {
        gDsceVoiceReqs++;
    } else {
        gDsceFoleyReqs++;
    }
}

/* Terrain foley through MM's own surface system: the material variant comes from the
 * floor poly the player is standing on (same source z_player uses for Link's feet). */
void Dsce_AdapterPlayFoley(int kind) {
    PlayState* play = gDsceAuthorityPlay;
    Player* player;
    u16 surf = 0;
    u16 id = 0;

    if (play == NULL) {
        return;
    }
    player = GET_PLAYER(play);
    if (player == NULL) {
        return;
    }
    if (player->actor.floorPoly != NULL) {
        surf = SurfaceType_GetSfxOffset(&play->colCtx, player->actor.floorPoly, player->actor.floorBgId);
    }
    switch (kind) {
        case 0: id = NA_SE_PL_JUMP_GROUND + surf; break;
        case 1: id = NA_SE_PL_LAND_GROUND + surf; break;
        case 2: id = NA_SE_PL_WALK_GROUND + surf; break;
        case 3: id = NA_SE_PL_BODY_HIT; break;
        case 4: id = NA_SE_PL_SWIM; break;
        case 5: id = NA_SE_PL_BOUND; break;
        case 6: /* ground pound: a WEIGHTY thud layered with the surface-material landing.
                 * BLOCK_BOUND (stone push-block drop), NOT BODY_HIT -- the body-slam family
                 * is what Goron link uses, and the pound read as "a Goron drop". */
            Audio_PlaySfx_AtPos(&player->actor.projectedPos, NA_SE_EV_BLOCK_BOUND);
            id = NA_SE_PL_LAND_GROUND + surf;
            break;
        case 7: id = NA_SE_EV_DIVE_INTO_WATER; break;
        case 8: id = NA_SE_IT_SWORD_SWING_HARD; break; /* pound/twirl windup whoosh */
        default: return;
    }
    Audio_PlaySfx_AtPos(&player->actor.projectedPos, id);
    gDsceFoleyReqs++;
}


/* Mario's voice: play a swapped-sample VO id (Fierce Deity bank, form offset 0) at the
 * player. Ids are the literal 0x68xx VO indices (see voicebank_table.h). */
void Dsce_AdapterPlayVoice(int kind) {
    static const u16 sVoiceIds[5] = {
        0x6800, /* JUMP   -> NA_SE_VO_LI_SWORD_N  (adult_link_attack1..3 = yah/wah/hoo) */
        0x6801, /* SHOUT  -> NA_SE_VO_LI_SWORD_L  (strong_attack = yahoo/waha) */
        0x6814, /* HOOHOO -> NA_SE_VO_LI_AUTO_JUMP (hup = hoohoo) */
        0x6805, /* HURT   -> NA_SE_VO_LI_DAMAGE_S (gasp1 = attacked) */
        0x6808, /* FALL   -> NA_SE_VO_LI_FALL_L   (falling1 = waaaooow) */
    };
    PlayState* play = gDsceAuthorityPlay;
    Player* player;

    if ((play == NULL) || (kind < 0) || (kind >= 5)) {
        return;
    }
    player = GET_PLAYER(play);
    if (player == NULL) {
        return;
    }
    Audio_PlaySfx_AtPos(&player->actor.projectedPos, sVoiceIds[kind]);
    gDsceVoiceReqs++;
}

/* [perf, goal 07] Both water queries below (poison + heal) hit WaterBox_GetSurface1 at the
 * SAME player position each tick. Share one query, cached on the tick counter -> halves the
 * water cost with zero behavior change (bit-identical, deterministic). */
extern unsigned int gDsceTelemetry[]; /* [0]=magic [1]=frame */
static struct {
    u32 frame;
    s32 found;
    f32 ySurface;
    s32 lightIndex;
} sDsceWaterCache = { 0xFFFFFFFF, 0, 0.0f, 0 };

static s32 Dsce_CachedWater(PlayState* play, f32 px, f32 pz, f32* ySurface, s32* lightIndex) {
    u32 frame = gDsceTelemetry[1];
    if (sDsceWaterCache.frame != frame) {
        WaterBox* wb = NULL;
        sDsceWaterCache.frame = frame;
        sDsceWaterCache.found = WaterBox_GetSurface1(play, &play->colCtx, px, pz,
                                                     &sDsceWaterCache.ySurface, &wb);
        sDsceWaterCache.lightIndex = (wb != NULL) ? ((((s32)wb->properties) >> 8) & 0x1F) : 0;
    }
    *ySurface = sDsceWaterCache.ySurface;
    *lightIndex = sDsceWaterCache.lightIndex;
    return sDsceWaterCache.found;
}

/* Southern Swamp poison water (PC: z_play.c:1297): MM's only damaging water; discriminated by
 * WaterBox lightIndex 4 (the murky poison tint) vs 1 (normal). Fires at/below the surface. */
#define DSCE_POISON_WATER_LIGHT_INDEX 4
int Dsce_MarioInPoisonWater(void) {
    PlayState* play = gDsceAuthorityPlay;
    Player* player;
    f32 ySurface;

    if ((play == NULL) || (play->sceneId != SCENE_20SICHITAI)) {
        return 0;
    }
    player = GET_PLAYER(play);
    if (player == NULL) {
        return 0;
    }
    {
        s32 lightIndex;
        if (Dsce_CachedWater(play, player->actor.world.pos.x, player->actor.world.pos.z, &ySurface,
                             &lightIndex)) {
            return ((player->actor.world.pos.y < ySurface) &&
                    (lightIndex == DSCE_POISON_WATER_LIGHT_INDEX)) ? 1 : 0;
        }
    }
    return 0;
}

/* Water-surface heal (PC: z_play.c:1333): floating near the top of non-poison water recovers MM
 * hearts; returns 1 per filled wedge so the driver can ding SM64's power meter. */
#define DSCE_HEAL_WEDGE 0x10
#ifndef DSCE_WaterHealBand
#define DSCE_WaterHealBand 80.0f
#endif
#ifndef DSCE_WaterHealRate
#define DSCE_WaterHealRate 1.0f
#endif
int Dsce_MarioWaterSurfaceHeal(void) {
    PlayState* play = gDsceAuthorityPlay;
    Player* player;
    f32 ySurface;
    f32 py;
    s32 lightIndex;
    s32 before;
    s32 after;
    s32 add;
    static f32 sAccum = 0.0f;

    if (play == NULL) {
        return 0;
    }
    player = GET_PLAYER(play);
    if (player == NULL) {
        return 0;
    }
    if (!Dsce_CachedWater(play, player->actor.world.pos.x, player->actor.world.pos.z, &ySurface,
                          &lightIndex)) {
        return 0;
    }
    if (lightIndex == DSCE_POISON_WATER_LIGHT_INDEX) {
        return 0;
    }
    py = player->actor.world.pos.y;
    if (!((py < ySurface) && (py >= ySurface - DSCE_WaterHealBand))) {
        return 0;
    }
    if (gSaveContext.save.saveInfo.playerData.health >= gSaveContext.save.saveInfo.playerData.healthCapacity) {
        return 0;
    }
    before = gSaveContext.save.saveInfo.playerData.health / DSCE_HEAL_WEDGE;
    sAccum += DSCE_WaterHealRate;
    add = (s32)sAccum;
    if (add > 0) {
        sAccum -= add;
        gSaveContext.save.saveInfo.playerData.health += add;
        if (gSaveContext.save.saveInfo.playerData.health > gSaveContext.save.saveInfo.playerData.healthCapacity) {
            gSaveContext.save.saveInfo.playerData.health = gSaveContext.save.saveInfo.playerData.healthCapacity;
        }
    }
    after = gSaveContext.save.saveInfo.playerData.health / DSCE_HEAL_WEDGE;
    return (after > before) ? 1 : 0;
}


/* --- Mario sings the ocarina (PC parity, monophonic) -------------------------------------
 * Inherited config: SingBaseSemitone (A4=9 -- the central real note plays the clip UNPITCHED,
 * keeping the five-note range within -7..+5 semitones) and SingVolume. The PC pitches by resampling in
 * its mixer; on N64 the sfx system's live freqScale pointer does the same job. Polyphony,
 * reverb and vibrato are PC-mixer features and stay PC-only. */
static const f32 sDsceSemiRatio[49] = { /* 2^(n/12), n = -24..+24 */
    0.250000f, 0.264866f, 0.280616f, 0.297302f, 0.314980f, 0.333710f,
    0.353553f, 0.374577f, 0.396850f, 0.420448f, 0.445449f, 0.471937f,
    0.500000f, 0.529732f, 0.561231f, 0.594604f, 0.629961f, 0.667420f,
    0.707107f, 0.749154f, 0.793701f, 0.840896f, 0.890899f, 0.943874f,
    1.000000f, 1.059463f, 1.122462f, 1.189207f, 1.259921f, 1.334840f,
    1.414214f, 1.498307f, 1.587401f, 1.681793f, 1.781797f, 1.887749f,
    2.000000f, 2.118926f, 2.244924f, 2.378414f, 2.519842f, 2.669680f,
    2.828427f, 2.996614f, 3.174802f, 3.363586f, 3.563595f, 3.775497f,
    4.000000f
};
f32 gDsceSingFreq = 1.0f;                 /* live freqScale the audio thread reads */
f32 gDsceSingVolume = DSCE_SingVolume;    /* inherited PC volume */
u32 gDsceSingNoteCount = 0;               /* draw-side performance pulse, as on PC */
/* Punch Hoo is the longest upbeat punch donor (502 ms versus 285/252 ms for Yah/Wah).
 * Its generated 32 kHz channel is fixed-pitch, unlike the swapped vanilla hup channel. */
u16 gDsceSingSfxId = NA_SE_VO_DSCE_VO_PUNCH_HOO;

f32 Dsce_SingRatio(s32 semitone) {
    s32 d = semitone - (s32)DSCE_SingBaseSemitone;
    if (d < -24) {
        d = -24;
    } else if (d > 24) {
        d = 24;
    }
    return sDsceSemiRatio[d + 24];
}


/* mask-on scream lead-in from tuning: MarioScreamDelay is in MILLISECONDS (the PC's mixer
 * buffers silence); MM gameplay runs at 20fps, so ms/50 = frames. Minimum 1 so the cue
 * always defers to the hook (same code path regardless of tuning). */
s32 Dsce_ScreamDelayFromTuning(void) {
    s32 frames = (s32)(DSCE_MarioScreamDelay / 50.0f + 0.5f);

    return (frames < 1) ? 1 : frames;
}
