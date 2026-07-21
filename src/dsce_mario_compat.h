/* [DSCE N64] Compatibility shims for compiling SM64's EXTRACTED asset sources (Mario's
 * model.inc.c and anim_*.inc.c) as Majora's Mask translation units.
 *
 * Installation contract: the user supplies both baseroms; Mario's data is extracted from
 * THEIR SM64 ROM by the sm64 decomp's asset pipeline and staged into the build at `make
 * mod` time (see Makefile "stage-sm64-assets"). No game data is committed to this repo.
 *
 * The SM64 sources are gbi MACRO source, so compiling them under MM's F3DEX_GBI_2 gbi.h
 * re-emits every display list in MM's native microcode dialect automatically (SM64's
 * <=16-vertex gsSPVertex loads are legal under F3DEX2's 32-slot buffer).
 */
#ifndef DSCE_MARIO_COMPAT_H
#define DSCE_MARIO_COMPAT_H

#include "global.h"
#include "dsce_n64_abi.h"

/* SM64 include/macros.h: alignment attribute is a no-op under IDO there too */
#define ALIGNED8

/* SM64 include/types.h */
typedef u8 Texture;

/* SM64's struct Animation, bit-identical layout to the vendored kernel's (both o32 BE);
 * the extracted anim_*.inc.c files initialize it positionally. */
struct Animation {
    s16 flags;
    s16 animYTransDivisor;
    s16 startFrame;
    s16 loopStart;
    s16 loopEnd;
    s16 unusedBoneCount;
    const s16* values;
    const u16* index;
    u32 length;
};
static_assert(sizeof(struct Animation) == 24,
              "SM64 animation layout must remain o32-compatible");

#define ANIMINDEX_NUMPARTS(animindex) (s16)(sizeof(animindex) / sizeof(u16) / 6 - 1)

/* Combiner modes SM64's model data uses that MM's gbi.h doesn't define (copied verbatim
 * from sm64/include/PR/gbi.h -- plain combiner tuples, microcode-agnostic). */
#ifndef G_CC_DECALFADE
#define G_CC_DECALFADE 0, 0, 0, TEXEL0, 0, 0, 0, ENVIRONMENT
#endif
#ifndef G_CC_DECALFADEA
#define G_CC_DECALFADEA 0, 0, 0, TEXEL0, TEXEL0, 0, ENVIRONMENT, 0
#endif
#ifndef G_CC_SHADEFADEA
#define G_CC_SHADEFADEA 0, 0, 0, SHADE, 0, 0, 0, ENVIRONMENT
#endif
#ifndef G_CC_BLENDRGBFADEA
#define G_CC_BLENDRGBFADEA TEXEL0, SHADE, TEXEL0_ALPHA, SHADE, 0, 0, 0, ENVIRONMENT
#endif
#ifndef G_CC_MODULATERGBFADEA
#define G_CC_MODULATERGBFADEA TEXEL0, 0, SHADE, 0, 0, 0, 0, ENVIRONMENT
#endif
#ifndef G_CC_MODULATERGBFADE
#define G_CC_MODULATERGBFADE TEXEL0, 0, SHADE, 0, 0, 0, 0, ENVIRONMENT
#endif

/* SM64's custom render mode (peach hair transparency) -- standard RM macro composition */
#ifndef G_RM_CUSTOM_AA_ZB_XLU_SURF
/* verbatim from sm64 gbi.h: XLU surf with Z_UPD */
#define RM_CUSTOM_AA_ZB_XLU_SURF(clk) RM_AA_ZB_XLU_SURF(clk) | Z_UPD
#define G_RM_CUSTOM_AA_ZB_XLU_SURF RM_CUSTOM_AA_ZB_XLU_SURF(1)
#endif

/* Mario's 20-bone body-part table (traversal order = anim rotation slot order; slot 0 of
 * the anim index table is the root translation, slots 1..20 are these parts' rotations).
 * Derived by hand from sm64/actors/mario/geo.inc.c mario_geo_body (the GEO_ROTATION_NODE
 * torso-tilt hook and the hand/eye GEO_SWITCH states are fixed: open hands, cap on,
 * eyes front -- Phase 2b re-introduces switch states). */
typedef struct {
    s16 tx, ty, tz;   /* static translation, model units */
    s8 parent;        /* index into gDsceMarioParts, -1 = actor root */
    s8 pad;
    const Gfx* dl;    /* NULL for invisible articulation bones */
} DsceMarioPart;

#define DSCE_MARIO_NUM_PARTS 20
static_assert(sizeof(DsceMarioPart) == 12,
              "Mario part table layout must remain o32-compatible");
static_assert(DSCE_MARIO_NUM_PARTS <= 32,
              "renderer matrix/pose caches hold at most 32 parts");

#endif
