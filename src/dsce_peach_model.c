/* [DSCE N64] The Peach statue (Song of Healing acquisition) -- SM64's Peach model
 * compiled as an MM TU, same pattern as Mario's (see dsce_mario_compat.h for the
 * installation contract). Parts table + the statue-pose anim are staged/generated at
 * build time; the light groups are gray-tinted at staging (stone). */
#include "dsce_mario_compat.h"

#include "sm64_assets/actors/peach/model.inc.c"
#include "dsce_peach_anim.inc"
#include "dsce_peach_parts.inc"

const DsceMarioPart* const gDscePeachParts = sDscePeachParts;
const int gDscePeachPartCount = SDSCEPEACHPARTS_COUNT;
const struct Animation* const gDscePeachPoseAnim = &sDscePeachPoseAnim;
