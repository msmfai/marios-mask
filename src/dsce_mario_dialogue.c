/* [DSCE] Mario's dialogue identity (goal 06). The takeover puppets HUMAN Link, so every
 * MM system treats him as Link -- correct almost everywhere. Where dialogue hinges on being
 * RECOGNIZED, Mario has HIS OWN textId range:
 *
 *   0x4000-0x40FF -- DSCE MARIO RANGE (vanilla tops out at 0x354C; zero overlap)
 *
 * THE PATTERN (user mandate: "Mario has his own stuff, it never overlaps with anyone"):
 *   1. The NPC actor gets a PLAYER_FORM_MARIO case that selects an id from this range
 *      (never another form's id, never a rewritten vanilla id).
 *   2. Message_OpenText (patched) resolves DSCE-range ids via a plain-box template
 *      (0x51E) for the header/DMA window, then Dsce_MarioDialogue fills in the text below.
 *   3. A DSCE id absent from this table shows the template text -- add the row.
 *
 * Text is plain ASCII; "\x11" = newline, "\x10" = box break. Keep lines ~18 chars.
 *
 * ASSIGNED IDS:
 *   0x4000-0x4007  Clock Town gate guards (En_Stop_heishi): gate*2 + night
 *                  gates: 0 south/swamp, 1 north/mountain, 2 west/ocean, 3 east/canyon
 *   0x4008         Deku Palace guard (En_Guard_Nuts)
 *   0x4009         Peach statue "cake" line (z_dsce_mario.c; shows for ANY form)
 *
 * GLOBAL ITEM-TEXT OVERRIDES (the Circus Leader slot is fully replaced):
 *   0x0083         Brother's Mask get-item text
 *   0x173D         Brother's Mask pause-menu description
 *   0x1FF4         Happy Mask Salesman reaction
 *   0x210A         pause-menu provenance hint
 *   0x21B4         Toto quest's replacement reward notebook label
 *   0x2341         ranch face-reaction dialogue
 */
#include "global.h"

typedef struct {
    u16 textId;
    const char* mario; /* ASCII + 0x11 newline / 0x10 box-break; no header, no end code */
} DsceMarioLine;

/* THE TABLE -- add rows to Mario-ize more "recognized as Link" dialogue. */
static const DsceMarioLine sDsceMarioLines[] = {
    { 0x0083,
      "You got the\x11"
      "Brother's Mask!\x11"
      "Contains the spirit of a\x11"
      "hero from another world." },
    { 0x173D,
      "Brother's Mask\x11"
      "Contains the spirit of\x11"
      "a hero from another\x11"
      "world." },
    { 0x1FF4,
      "That's the Brother's\x11"
      "Mask, isn't it?" },
    { 0x210A,
      "It seems this mask holds\x11"
      "the spirit of a hero from\x11"
      "another world..." },
    { 0x21B4,
      "Toto's Reward     Milk Bar\x11"
      "Thanks for moving Gorman with song" },
    { 0x2341,
      "Oh, the Brother's Mask!\x11"
      "It reminds me of Gorman.\x10"
      "He always says how his\x11"
      "brothers are at the ranch..." },
    /* 0x4000-0x4007: Clock Town gate guards -- destination callout, no homecoming assumptions */
    { 0x4000,
      "The swamp at Woodfall\x11"
      "lies this way.\x10"
      "Safe travels, sir!\x11"
      "...Nice moustache." },
    { 0x4001,
      "The swamp road is\x11"
      "dark at night, sir.\x10"
      "Watch your step...\x11"
      "and the moustache." },
    { 0x4002,
      "Snowhead's mountains\x11"
      "lie this way.\x10"
      "Safe travels, sir!\x11"
      "...Nice moustache." },
    { 0x4003,
      "The mountain road is\x11"
      "cold at night, sir.\x10"
      "That moustache should\x11"
      "keep you warm." },
    { 0x4004,
      "Great Bay and its\x11"
      "ocean lie this way.\x10"
      "Safe travels, sir!\x11"
      "...Nice moustache." },
    { 0x4005,
      "The bay is rough\x11"
      "after dark, sir.\x10"
      "Swim carefully...\x11"
      "and the moustache." },
    { 0x4006,
      "The canyon at Stone\x11"
      "Tower lies this way.\x10"
      "Safe travels, sir!\x11"
      "...Nice moustache." },
    { 0x4007,
      "The canyon is eerie\x11"
      "at night, sir.\x10"
      "Even that moustache\x11"
      "won't scare ghosts." },
    /* 0x4008: Deku Palace guard sizes up the outsider */
    { 0x4008,
      "Halt! ...A grown man\x11"
      "with a magnificent\x11"
      "moustache?\x10"
      "Heh. No mere outsider.\x11"
      "Go on through, sir." },
    /* 0x4009: the Peach statue (Laundry Pool) -- her one line, inherited from the PC rite */
    { 0x4009,
      "I will never finish\x11"
      "that cake..." },
};
#define DSCE_MARIO_LINES_COUNT (s32)(sizeof(sDsceMarioLines) / sizeof(sDsceMarioLines[0]))

/* the reserved Mario range -- Message_OpenText remaps these onto a plain-box template */
int Dsce_MarioDialogueIsDsce(u16 textId) {
    return (textId >= 0x4000) && (textId < 0x4100);
}

static int Dsce_MarioDialogueIsGlobal(u16 textId) {
    switch (textId) {
        case 0x0083:
        case 0x173D:
        case 0x1FF4:
        case 0x210A:
        case 0x21B4:
        case 0x2341:
            return 1;
        default:
            return 0;
    }
}

extern int gDsceSpikeAlive;

/* Called from the patched Message_OpenText AFTER the normal message load. If the mask is
 * on and this textId has a Mario override, rewrite the loaded message text in place. */
void Dsce_MarioDialogue(PlayState* play, u16 textId) {
    Font* font;
    const char* src;
    s32 i;
    s32 w;

    /* DSCE-range ids and the globally replaced item/notebook text must resolve for any
     * form.  In particular the get-item message appears before the first transformation. */
    if (!gDsceSpikeAlive && !Dsce_MarioDialogueIsDsce(textId) && !Dsce_MarioDialogueIsGlobal(textId)) {
        return; /* not Mario -> inherit the human/Link message */
    }
    for (i = 0; i < DSCE_MARIO_LINES_COUNT; i++) {
        if (sDsceMarioLines[i].textId != textId) {
            continue;
        }
        /* keep MM's 11-byte header (schar[0..10]); overwrite the text from schar[11] */
        font = &play->msgCtx.font;
        if (textId == 0x21B4) {
            /* Notebook detail header byte 2 selects the item icon.  The original entry
             * used the Circus Leader mask; show the actual 200-rupee replacement. */
            font->msgBuf.schar[2] = ITEM_RUPEE_HUGE;
        }
        src = sDsceMarioLines[i].mario;
        w = 11;
        while (*src != '\0' && w < 1279) {
            font->msgBuf.schar[w++] = *src++;
        }
        font->msgBuf.schar[w++] = (char)0xBF; /* MESSAGE_END */
        return;
    }
}
