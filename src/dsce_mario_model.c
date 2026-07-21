/* [DSCE N64] Mario's model, compiled from the user's SM64 ROM extraction -- staged into
 * src/dsce/sm64_assets/ at `make mod` time; see dsce_mario_compat.h for the contract.
 * All display lists are re-emitted in MM's F3DEX_GBI_2 dialect by this compile. */
#include "dsce_mario_compat.h"

#include "sm64_assets/actors/mario/model.inc.c"

/* Body-part table in anim-slot order (see compat header). Translations and hierarchy are
 * from mario_geo_body in sm64/actors/mario/geo.inc.c. Fixed switch states: cap on, eyes
 * front, both hands open. */
/* scene-ambient blend: the 6 light groups, rescaled per frame by the draw */
Lights1* const gDsceMarioLightGroups[6] = {
    &mario_blue_lights_group,  &mario_red_lights_group,    &mario_white_lights_group,
    &mario_brown1_lights_group, &mario_beige_lights_group, &mario_brown2_lights_group,
};

/* switch-state DLs (Phase 2b): eyes by blink case, hands by geo_switch_mario_hand case */
const Gfx* const gDsceMarioEyeDls[3] = {
    mario_cap_on_eyes_front, mario_cap_on_eyes_half_closed, mario_cap_on_eyes_closed,
};
const Gfx* const gDsceMarioHandDls[2][3] = {
    { mario_left_hand_closed, mario_left_hand_open, mario_left_hand_closed },
    { mario_right_hand_closed, mario_right_hand_open, mario_right_hand_peace },
};

const DsceMarioPart gDsceMarioParts[DSCE_MARIO_NUM_PARTS] = {
    /*  0 root    */ { 0, 0, 0, -1, 0, NULL },
    /*  1 butt    */ { 0, 0, 0, 0, 0, mario_butt },
    /*  2 torso   */ { 68, 0, 0, 1, 0, mario_torso },
    /*  3 head    */ { 87, 0, 0, 2, 0, mario_cap_on_eyes_front },
    /*  4 L shldr */ { 67, -10, 79, 2, 0, NULL },
    /*  5 L arm   */ { 0, 0, 0, 4, 0, mario_left_arm },
    /*  6 L fore  */ { 65, 0, 0, 5, 0, mario_left_forearm_shared_dl },
    /*  7 L hand  */ { 60, 0, 0, 6, 0, mario_left_hand_open },
    /*  8 R shldr */ { 68, -10, -79, 2, 0, NULL },
    /*  9 R arm   */ { 0, 0, 0, 8, 0, mario_right_arm },
    /* 10 R fore  */ { 65, 0, 0, 9, 0, mario_right_forearm_shared_dl },
    /* 11 R hand  */ { 60, 0, 0, 10, 0, mario_right_hand_open },
    /* 12 L hip   */ { 13, -8, 42, 1, 0, NULL },
    /* 13 L thigh */ { 0, 0, 0, 12, 0, mario_left_thigh },
    /* 14 L leg   */ { 89, 0, 0, 13, 0, mario_left_leg_shared_dl },
    /* 15 L foot  */ { 67, 0, 0, 14, 0, mario_left_foot },
    /* 16 R hip   */ { 13, -8, -42, 1, 0, NULL },
    /* 17 R thigh */ { 0, 0, 0, 16, 0, mario_right_thigh },
    /* 18 R leg   */ { 89, 0, 0, 17, 0, mario_right_leg_shared_dl },
    /* 19 R foot  */ { 67, 0, 0, 18, 0, mario_right_foot },
};
