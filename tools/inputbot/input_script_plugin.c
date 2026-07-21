/* mupen64plus input plugin: scripted input playback + goal-seeking bot.
 *
 * Env vars:
 *   CT_INPUT_SCRIPT  path to rule file (required for any input)
 *   CT_MARIO_ADDR    hex VA of gMarioStates (e.g. 801d75b0) — enables
 *                    state readback (GOTO rules + telemetry)
 *   CT_TELEMETRY     csv path; per-frame "frame,x,y,z,yaw,action" appended
 *
 * Rule file format, one rule per line ('#' comments):
 *   <start> <end> <BUTTONS> <stick_x> <stick_y>     timed input
 *   G <start> <end> <tx> <tz> <radius>              steer Mario to (tx,tz)
 *   H <start> <end> <BUTTONS> <tx> <tz> <radius>    GOTO while holding buttons
 * BUTTONS: comma list of A,B,Z,START,L,R,DU,DD,DL,DR,CU,CD,CL,CR or NONE.
 * Later rules override earlier on overlap. GOTO holds forward and applies
 * proportional stick-x steering from faceAngle error; presses A when stuck.
 *
 * Build:
 *   clang -dynamiclib -O2 -I/opt/homebrew/include/mupen64plus \
 *         -o mupen64plus-input-script.dylib input_script_plugin.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dlfcn.h>
#include <time.h>

#define M64P_PLUGIN_PROTOTYPES 1
#include "m64p_types.h"
#include "m64p_plugin.h"
#include "m64p_common.h"

#define MAX_RULES 4096

typedef struct {
    int is_goto;
    unsigned start, end;
    unsigned buttons;
    signed char x, y;
    float tx, tz, radius;
    int area;        /* queue rules: required gCurrAreaIndex (0 = any) */
    int reached;
} Rule;

/* Sequential exploration queue: 'Q x z radius area' lines. The active entry
 * advances when reached (or skipped after QUEUE_ENTRY_TIMEOUT frames), and
 * gives no input while the area gate doesn't match (e.g. mid-warp). */
#define MAX_QUEUE 512
#define QUEUE_ENTRY_TIMEOUT 700
static Rule sQueue[MAX_QUEUE];
static int sQueueCount = 0;
static int sQueueIdx = 0;
static unsigned sQueueEntryStart = 0;

static Rule sRules[MAX_RULES];
static int sRuleCount = 0;
static unsigned sFrame = 0;
static CONTROL *sControls = NULL;

static unsigned char *sRdram = NULL;
static unsigned sMarioAddr = 0;   /* VA of gMarioStates */
static unsigned sAreaAddr = 0;    /* VA of gCurrAreaIndex (s16) */
static unsigned sDsceAddr = 0;    /* CT_DSCE_ADDR: VA of gDsceTelemetry (DSCE N64 mod) */
static unsigned sPeekAddr = 0;    /* CT_PEEK_ADDR: 4 u32s dumped per sample as PEEK rows */
static unsigned sPeek2Addr = 0;   /* CT_PEEK2_ADDR: independent 8-u32 lifecycle probe */
static int sDsceSeen = 0;
static unsigned sShotEvery = 0;   /* CT_SCREENSHOT_EVERY: frames between auto-screenshots */
static unsigned sStateSaveAt = 0; /* CT_STATE_SAVE_AT: frame to save a savestate (CT_STATE_PATH) */
static const char *sStateLoadPath = NULL; /* CT_STATE_LOAD: load this savestate at frame 30
                                           * (mupen SIGBUSes on --savestate given at startup) */
static int sStateLoadDone = 0;
static unsigned sStateSaveOnTicks = 0; /* CT_STATE_SAVE_ON_TICKS: save when DSCE tick counter >= N */
static int sStateSaved = 0;
static const char *sStatePath = NULL;
static void *(*sGetMemPtr)(m64p_dbg_memptr_type) = NULL;
static m64p_error (*sCoreDoCommand)(m64p_command, int, void *) = NULL;
static unsigned sMaxFrames = 0;       /* CT_MAX_FRAMES: hard stop */
static unsigned sQueueDoneFrame = 0;  /* stop shortly after queue completes */
static FILE *sTelemetry = NULL;
static float sLastX, sLastZ;
static int sStuckFrames = 0;
static int sGotoUnstick = 1;     /* CT_GOTO_UNSTICK=0 disables GOTO's automatic hop */

/* ---- DSCE structured JSONL log drain ---- */
static unsigned sTickAddr = 0;      /* CT_TICK_ADDR: VA of the GAME's sim-tick counter (u32).
                                     * When set, telemetry emits ONE row per tick INCREMENT (with the
                                     * tick value as the first column) instead of every-5-polls --
                                     * the cross-game metamorphic rig compares tick-indexed streams
                                     * (SM64 gGlobalTimer vs the mod's gDscePlayFrame). */
static unsigned sLastTick = 0;
static unsigned sLogHeadAddr = 0;   /* CT_LOG_ADDR: VA of gDsceLogHead (u32 monotonic write count) */
static unsigned sLogRingAddr = 0;   /* CT_LOGRING_ADDR: VA of gDsceLogRing[] (48-byte records) */
static FILE *sLogFile = NULL;
static unsigned sLogDrained = 0;    /* last seq we emitted */
#define DSCE_LOG_RING 256
#define DSCE_LOG_RECSZ 48           /* sizeof(DsceLogRec): u32 seq,frame + char[24] + s32 a,b,c,d */

/* ---- DSCE firehose drain (debug ROMs): 32-byte DsceFhRec ring -> JSONL spool ---- */
static unsigned sFhHeadAddr = 0;   /* CT_FH_ADDR: VA of gDsceFhHead */
static unsigned sFhRingAddr = 0;   /* CT_FH_RING: VA of gDsceFhRing */
static FILE *sFhFile = NULL;       /* CT_FH_DIR/<ts>.fh.jsonl */
static unsigned sFhDrained = 0;
static unsigned long long sFhDrops = 0;
#define DSCE_FH_RING 1024
#define DSCE_FH_RECSZ 32

/* ---- RDRAM access (mupen64plus stores RDRAM as host-endian u32 words) ---- */

static unsigned rd_u32(unsigned va) {
    return *(unsigned *) (sRdram + (va & 0x00FFFFFC));
}

static float rd_f32(unsigned va) {
    unsigned u = rd_u32(va);
    float f;
    memcpy(&f, &u, 4);
    return f;
}

static short rd_s16(unsigned va) {
    unsigned w = rd_u32(va);
    return (short) ((va & 2) ? (w & 0xFFFF) : (w >> 16));
}

/* single byte from N64 big-endian RDRAM stored host-endian-word: XOR-3 within the word */
static unsigned char rd_u8(unsigned va) {
    return sRdram[((va & 0x00FFFFFF) ^ 3)];
}

static void dsce_drain_firehose(void) {
    unsigned head, seq;
    if (!sFhFile || !sRdram || !sFhHeadAddr || !sFhRingAddr) {
        return;
    }
    head = rd_u32(sFhHeadAddr);
    if (head - sFhDrained > DSCE_FH_RING) { /* overwritten: count, never hide */
        unsigned long long lost = (head - sFhDrained) - DSCE_FH_RING;
        sFhDrops += lost;
        fprintf(sFhFile, "{\"drop\":%llu}\n", lost);
        sFhDrained = head - DSCE_FH_RING;
    }
    for (seq = sFhDrained; seq != head; seq++) {
        unsigned base = sFhRingAddr + (seq & (DSCE_FH_RING - 1)) * DSCE_FH_RECSZ;
        unsigned rseq = rd_u32(base + 0);
        unsigned dft = rd_u32(base + 4);
        if (rseq != seq) { /* lapped mid-read */
            continue;
        }
        fprintf(sFhFile,
                "{\"seq\":%u,\"domain\":%u,\"tag\":%u,\"tick\":%u,\"frame\":%u,"
                "\"a\":%d,\"b\":%d,\"c\":%d,\"d\":%d}\n",
                rseq, (dft >> 24) & 0xFF, dft & 0xFFFF,
                rd_u32(base + 8), rd_u32(base + 12),
                (int) rd_u32(base + 16), (int) rd_u32(base + 20),
                (int) rd_u32(base + 24), (int) rd_u32(base + 28));
    }
    sFhDrained = head;
}

/* Drain new gDsceLogRing records (seq > sLogDrained) to the JSONL file, one object per line.
 * Record layout (48B): u32 seq, u32 frame, char tag[24], s32 a,b,c,d. */
static void dsce_drain_log(void) {
    unsigned head, seq;
    if (!sLogFile || !sRdram || !sLogHeadAddr || !sLogRingAddr) {
        return;
    }
    head = rd_u32(sLogHeadAddr);
    /* if the ring wrapped past what we've drained, skip ahead to avoid re-reading overwritten slots */
    if (head - sLogDrained > DSCE_LOG_RING) {
        sLogDrained = head - DSCE_LOG_RING;
    }
    for (seq = sLogDrained; seq != head; seq++) {
        unsigned base = sLogRingAddr + (seq & (DSCE_LOG_RING - 1)) * DSCE_LOG_RECSZ;
        unsigned rseq = rd_u32(base + 0);
        unsigned rframe = rd_u32(base + 4);
        char tag[25];
        int i;
        for (i = 0; i < 24; i++) {
            unsigned char ch = rd_u8(base + 8 + i);
            tag[i] = (ch >= 0x20 && ch < 0x7F) ? (char) ch : '\0';
            if (tag[i] == '\0') break;
        }
        tag[i] = '\0';
        fprintf(sLogFile, "{\"seq\":%u,\"frame\":%u,\"tag\":\"%s\",\"a\":%d,\"b\":%d,\"c\":%d,\"d\":%d}\n",
                rseq, rframe, tag, (int) rd_u32(base + 32), (int) rd_u32(base + 36),
                (int) rd_u32(base + 40), (int) rd_u32(base + 44));
    }
    if (head != sLogDrained) {
        fflush(sLogFile);
    }
    sLogDrained = head;
}

/* MarioState field offsets (sm64 decomp include/types.h) */
#define MARIO_ACTION   0x0C
#define MARIO_INTYAW   0x24   /* intendedYaw = stick angle + camera yaw */
#define MARIO_FACEYAW  0x2E   /* faceAngle[1] */
#define MARIO_POS      0x3C
#define MARIO_FLOORH   0x70   /* floorHeight under Mario */

static unsigned parse_buttons(const char *spec) {
    unsigned v = 0;
    char buf[256];
    char *tok;
    strncpy(buf, spec, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = 0;
    for (tok = strtok(buf, ","); tok; tok = strtok(NULL, ",")) {
        BUTTONS b;
        b.Value = 0;
        if      (!strcmp(tok, "A"))     b.A_BUTTON = 1;
        else if (!strcmp(tok, "B"))     b.B_BUTTON = 1;
        else if (!strcmp(tok, "Z"))     b.Z_TRIG = 1;
        else if (!strcmp(tok, "START")) b.START_BUTTON = 1;
        else if (!strcmp(tok, "L"))     b.L_TRIG = 1;
        else if (!strcmp(tok, "R"))     b.R_TRIG = 1;
        else if (!strcmp(tok, "DU"))    b.U_DPAD = 1;
        else if (!strcmp(tok, "DD"))    b.D_DPAD = 1;
        else if (!strcmp(tok, "DL"))    b.L_DPAD = 1;
        else if (!strcmp(tok, "DR"))    b.R_DPAD = 1;
        else if (!strcmp(tok, "CU"))    b.U_CBUTTON = 1;
        else if (!strcmp(tok, "CD"))    b.D_CBUTTON = 1;
        else if (!strcmp(tok, "CL"))    b.L_CBUTTON = 1;
        else if (!strcmp(tok, "CR"))    b.R_CBUTTON = 1;
        v |= b.Value;
    }
    return v;
}

static void load_script(void) {
    const char *path = getenv("CT_INPUT_SCRIPT");
    FILE *f;
    char line[512];

    sRuleCount = 0;
    sQueueCount = 0;
    sQueueIdx = 0;
    sQueueEntryStart = 0;
    if (path == NULL) {
        fprintf(stderr, "[input-script] CT_INPUT_SCRIPT not set; inputs neutral\n");
        return;
    }
    f = fopen(path, "r");
    if (f == NULL) {
        fprintf(stderr, "[input-script] cannot open %s\n", path);
        return;
    }
    while (fgets(line, sizeof(line), f) && sRuleCount < MAX_RULES) {
        char btns[256];
        unsigned s, e;
        int x, y;
        float tx, tz, rad;
        char *hash = strchr(line, '#');
        if (hash) *hash = 0;
        int qarea;
        if (sscanf(line, "Q %f %f %f %d", &tx, &tz, &rad, &qarea) == 4) {
            if (sQueueCount < MAX_QUEUE) {
                Rule *r = &sQueue[sQueueCount++];
                memset(r, 0, sizeof(*r));
                r->is_goto = 1;
                r->tx = tx; r->tz = tz; r->radius = rad;
                r->area = qarea;
            }
        } else if (sscanf(line, "H %u %u %255s %f %f %f", &s, &e, btns, &tx, &tz, &rad) == 6) {
            Rule *r = &sRules[sRuleCount++];
            memset(r, 0, sizeof(*r));
            r->is_goto = 1;
            r->start = s; r->end = e;
            r->buttons = parse_buttons(btns);
            r->tx = tx; r->tz = tz; r->radius = rad;
        } else if (sscanf(line, "G %u %u %f %f %f", &s, &e, &tx, &tz, &rad) == 5) {
            Rule *r = &sRules[sRuleCount++];
            memset(r, 0, sizeof(*r));
            r->is_goto = 1;
            r->start = s; r->end = e;
            r->tx = tx; r->tz = tz; r->radius = rad;
        } else if (sscanf(line, "%u %u %255s %d %d", &s, &e, btns, &x, &y) == 5) {
            Rule *r = &sRules[sRuleCount++];
            memset(r, 0, sizeof(*r));
            r->start = s; r->end = e;
            r->buttons = parse_buttons(btns);
            r->x = (signed char) x;
            r->y = (signed char) y;
        }
    }
    fclose(f);
    fprintf(stderr, "[input-script] loaded %d rules, %d queue entries from %s\n",
            sRuleCount, sQueueCount, path);
}

static void init_state_channel(m64p_dynlib_handle core) {
    const char *addr = getenv("CT_MARIO_ADDR");
    const char *tele = getenv("CT_TELEMETRY");

    if (addr) sMarioAddr = (unsigned) strtoul(addr, NULL, 16);
    if (getenv("CT_AREA_ADDR")) sAreaAddr = (unsigned) strtoul(getenv("CT_AREA_ADDR"), NULL, 16);
    if (getenv("CT_DSCE_ADDR")) sDsceAddr = (unsigned) strtoul(getenv("CT_DSCE_ADDR"), NULL, 16);
    if (getenv("CT_PEEK_ADDR")) sPeekAddr = (unsigned) strtoul(getenv("CT_PEEK_ADDR"), NULL, 16);
    if (getenv("CT_TICK_ADDR")) sTickAddr = (unsigned) strtoul(getenv("CT_TICK_ADDR"), NULL, 16);
    if (getenv("CT_PEEK2_ADDR")) sPeek2Addr = (unsigned) strtoul(getenv("CT_PEEK2_ADDR"), NULL, 16);
    if (getenv("CT_LOG_ADDR")) sLogHeadAddr = (unsigned) strtoul(getenv("CT_LOG_ADDR"), NULL, 16);
    if (getenv("CT_LOGRING_ADDR")) sLogRingAddr = (unsigned) strtoul(getenv("CT_LOGRING_ADDR"), NULL, 16);
    if (sLogHeadAddr && sLogRingAddr) {
        /* one file per session: logs/<unix_ts>.jsonl (dir from CT_LOG_DIR, default ./logs) */
        const char *dir = getenv("CT_LOG_DIR");
        char path[512];
        unsigned long ts = (unsigned long) time(NULL);
        if (!dir) dir = "logs";
        snprintf(path, sizeof(path), "%s/%lu.jsonl", dir, ts);
        sLogFile = fopen(path, "w");
        if (sLogFile) fprintf(stderr, "[input-script] DSCE log -> %s\n", path);
        else fprintf(stderr, "[input-script] DSCE log: could not open %s (mkdir %s?)\n", path, dir);
    }
    if (getenv("CT_FH_ADDR")) sFhHeadAddr = (unsigned) strtoul(getenv("CT_FH_ADDR"), NULL, 16);
    if (getenv("CT_FH_RING")) sFhRingAddr = (unsigned) strtoul(getenv("CT_FH_RING"), NULL, 16);
    if (sFhHeadAddr && sFhRingAddr) {
        const char *fdir = getenv("CT_FH_DIR");
        char fpath[512];
        unsigned long fts = (unsigned long) time(NULL);
        if (!fdir) fdir = "logs";
        snprintf(fpath, sizeof(fpath), "%s/%lu.fh.jsonl", fdir, fts);
        sFhFile = fopen(fpath, "w");
        if (sFhFile) fprintf(stderr, "[input-script] DSCE firehose -> %s\n", fpath);
    }
    if (getenv("CT_SCREENSHOT_EVERY")) sShotEvery = (unsigned) strtoul(getenv("CT_SCREENSHOT_EVERY"), NULL, 10);
    if (getenv("CT_GOTO_UNSTICK")) sGotoUnstick = atoi(getenv("CT_GOTO_UNSTICK")) != 0;
    if (getenv("CT_STATE_SAVE_AT")) sStateSaveAt = (unsigned) strtoul(getenv("CT_STATE_SAVE_AT"), NULL, 10);
    if (getenv("CT_STATE_SAVE_ON_TICKS")) sStateSaveOnTicks = (unsigned) strtoul(getenv("CT_STATE_SAVE_ON_TICKS"), NULL, 10);
    sStatePath = getenv("CT_STATE_PATH");
    sStateLoadPath = getenv("CT_STATE_LOAD");

    /* RDRAM isn't allocated until the ROM opens — resolve the accessor now,
     * fetch the pointer lazily in GetKeys. */
    sGetMemPtr = (void *(*)(m64p_dbg_memptr_type)) dlsym(core, "DebugMemGetPointer");
    sCoreDoCommand = (m64p_error (*)(m64p_command, int, void *)) dlsym(core, "CoreDoCommand");
    if (getenv("CT_MAX_FRAMES"))
        sMaxFrames = (unsigned) strtoul(getenv("CT_MAX_FRAMES"), NULL, 10);
    fprintf(stderr, "[input-script] DebugMemGetPointer=%p marioAddr=%08x\n",
            (void *) sGetMemPtr, sMarioAddr);

    if (tele) {
        sTelemetry = fopen(tele, "w");
        if (sTelemetry) fprintf(sTelemetry, "frame,x,y,z,yaw,action,area,floorh\n");
    }
}

EXPORT m64p_error CALL PluginStartup(m64p_dynlib_handle CoreLibHandle, void *Context,
                                     void (*DebugCallback)(void *, int, const char *)) {
    (void) Context; (void) DebugCallback;
    load_script();
    init_state_channel(CoreLibHandle);
    return M64ERR_SUCCESS;
}

EXPORT m64p_error CALL PluginShutdown(void) {
    if (sTelemetry) { fclose(sTelemetry); sTelemetry = NULL; }
    return M64ERR_SUCCESS;
}

EXPORT m64p_error CALL PluginGetVersion(m64p_plugin_type *PluginType, int *PluginVersion,
                                        int *APIVersion, const char **PluginNamePtr,
                                        int *Capabilities) {
    if (PluginType)    *PluginType = M64PLUGIN_INPUT;
    if (PluginVersion) *PluginVersion = 0x010100;
    if (APIVersion)    *APIVersion = 0x020100;
    if (PluginNamePtr) *PluginNamePtr = "CT scripted input + goto bot";
    if (Capabilities)  *Capabilities = 0;
    return M64ERR_SUCCESS;
}

EXPORT void CALL InitiateControllers(CONTROL_INFO ControlInfo) {
    sControls = ControlInfo.Controls;
    sControls[0].Present = 1;
    sControls[0].Plugin = PLUGIN_NONE;
    sControls[1].Present = 0;
    sControls[2].Present = 0;
    sControls[3].Present = 0;
    sFrame = 0;
}

/* Self-calibrating steering: intendedYaw (game-computed) = C + s*a where a
 * is our stick angle, s = handedness, C = camera-dependent offset. Probe two
 * angles to solve s and C, then drive a = s*(bearing - C). C is re-estimated
 * every frame so camera rotation is tracked. */
static short sCalA0, sCalA1;          /* intendedYaw at probe angles */
static int sCalPhase = 0;             /* 0,1: probing; 2: calibrated */
static int sCalSign = 1;
static short sLastA = 0;              /* last commanded stick angle (s16) */

static void stick_at(BUTTONS *Keys, short a16) {
    float a = (float) a16 * (float) M_PI / 32768.0f;
    Keys->X_AXIS = (signed char) (sinf(a) * 70.0f);
    Keys->Y_AXIS = (signed char) (cosf(a) * 70.0f);
    sLastA = a16;
}

static void apply_goto(Rule *r, BUTTONS *Keys) {
    float x = rd_f32(sMarioAddr + MARIO_POS);
    float z = rd_f32(sMarioAddr + MARIO_POS + 8);
    short intYaw = rd_s16(sMarioAddr + MARIO_INTYAW);
    float dx = r->tx - x, dz = r->tz - z;
    float dist = sqrtf(dx * dx + dz * dz);
    short bearing, C, want;

    if (dist < r->radius) {
        if (!r->reached) {
            r->reached = 1;
            if (r->start != r->end) /* timed rule; queue logs its own */
                fprintf(stderr, "[input-script] GOTO (%.0f,%.0f) REACHED at frame %u\n",
                        r->tx, r->tz, sFrame);
        }
        return;
    }

    bearing = (short) (atan2f(dx, dz) * 32768.0f / (float) M_PI);

    /* calibration probe: 20 frames at angle 0, 20 at +90 degrees */
    if (sCalPhase < 2) {
        unsigned ph = sFrame % 40;
        if (ph < 20) {
            stick_at(Keys, 0);
            sCalA0 = intYaw;
        } else {
            stick_at(Keys, 0x4000);
            sCalA1 = intYaw;
            if (ph == 39) {
                short d = (short) (sCalA1 - sCalA0);
                sCalSign = (d > 0) ? 1 : -1;
                sCalPhase = 2;
                fprintf(stderr, "[input-script] steering calibrated: sign=%d (d=%d)\n",
                        sCalSign, d);
            }
        }
        return;
    }

    /* per-frame offset estimate from last commanded angle */
    C = (short) (intYaw - sCalSign * sLastA);
    want = (short) (sCalSign * (short) (bearing - C));
    stick_at(Keys, want);

    /* unstick: if barely moving for ~1s, hop */
    if (fabsf(x - sLastX) + fabsf(z - sLastZ) < 1.0f) {
        sStuckFrames++;
        if (sGotoUnstick && sStuckFrames > 30 && (sStuckFrames % 30) < 5) {
            Keys->A_BUTTON = 1;
        }
    } else {
        sStuckFrames = 0;
    }
    sLastX = x;
    sLastZ = z;
    Keys->Value |= r->buttons;
}

EXPORT void CALL GetKeys(int Control, BUTTONS *Keys) {
    int i;
    Keys->Value = 0;
    if (Control != 0) return;

    if (sRdram == NULL && sGetMemPtr != NULL) {
        sRdram = (unsigned char *) sGetMemPtr(M64P_DBG_PTR_RDRAM);
        if (sRdram != NULL)
            fprintf(stderr, "[input-script] rdram=%p (frame %u)\n", (void *) sRdram, sFrame);
    }

    for (i = 0; i < sRuleCount; i++) {
        Rule *r = &sRules[i];
        if (sFrame < r->start || sFrame >= r->end) continue;
        if (r->is_goto) {
            if (sRdram && sMarioAddr) apply_goto(r, Keys);
        } else {
            Keys->Value = r->buttons;
            Keys->X_AXIS = r->x;
            Keys->Y_AXIS = r->y;
        }
    }

    if (sQueueIdx < sQueueCount && sRdram && sMarioAddr) {
        Rule *r = &sQueue[sQueueIdx];
        int areaNow = sAreaAddr ? rd_s16(sAreaAddr) : 0;
        if (sQueueEntryStart == 0) sQueueEntryStart = sFrame;
        if (sFrame - sQueueEntryStart > QUEUE_ENTRY_TIMEOUT) {
            fprintf(stderr, "[input-script] QUEUE %d/%d SKIPPED (%.0f,%.0f) area %d\n",
                    sQueueIdx + 1, sQueueCount, r->tx, r->tz, r->area);
            sQueueIdx++;
            sQueueEntryStart = sFrame;
        } else if (r->area == 0 || areaNow == r->area) {
            apply_goto(r, Keys);
            if (r->reached) {
                fprintf(stderr, "[input-script] QUEUE %d/%d REACHED (%.0f,%.0f) area %d frame %u\n",
                        sQueueIdx + 1, sQueueCount, r->tx, r->tz, r->area, sFrame);
                sQueueIdx++;
                sQueueEntryStart = sFrame;
            }
        }
        /* area mismatch: hold still and wait for the warp to finish */
    }

    /* Self-termination: batch runs stop the core when done (or at the cap),
     * so the harness never needs wall-clock timeouts. */
    if (sCoreDoCommand != NULL && sShotEvery && sFrame > 0 && (sFrame % sShotEvery) == 0) {
        sCoreDoCommand(M64CMD_TAKE_NEXT_SCREENSHOT, 0, NULL);
    }
    if (sCoreDoCommand != NULL && !sStateLoadDone && sStateLoadPath != NULL && sFrame == 30) {
        sStateLoadDone = 1;
        fprintf(stderr, "[input-script] loading state %s at frame %u\n", sStateLoadPath, sFrame);
        sCoreDoCommand(M64CMD_STATE_LOAD, 0, (void *) sStateLoadPath);
    }
    if (sCoreDoCommand != NULL && sStateSaveAt && sFrame == sStateSaveAt && sStatePath != NULL) {
        fprintf(stderr, "[input-script] saving state to %s at frame %u\n", sStatePath, sFrame);
        sCoreDoCommand(M64CMD_STATE_SAVE, 1, (void *) sStatePath);
    }
    /* tick-anchored state save: robust to boot-timing drift across ROM rebuilds -- fires when
     * the DSCE spike has actually ticked N frames (in gameplay, unfrozen, physics live). */
    if (sCoreDoCommand != NULL && !sStateSaved && sStateSaveOnTicks && sDsceAddr && sRdram &&
        rd_u32(sDsceAddr) == 0x44534345u && rd_u32(sDsceAddr + 4) >= sStateSaveOnTicks &&
        rd_u32(sDsceAddr + 4) < 0xBB00u && sStatePath != NULL) {
        sStateSaved = 1;
        fprintf(stderr, "[input-script] DSCE ticks>=%u: saving state to %s (frame %u)\n",
                sStateSaveOnTicks, sStatePath, sFrame);
        sCoreDoCommand(M64CMD_STATE_SAVE, 1, (void *) sStatePath);
    }
    if (sCoreDoCommand != NULL) {
        if (sQueueCount > 0 && sQueueIdx >= sQueueCount && sQueueDoneFrame == 0) {
            sQueueDoneFrame = sFrame;
            fprintf(stderr, "[input-script] QUEUE COMPLETE at frame %u\n", sFrame);
        }
        if ((sQueueDoneFrame && sFrame > sQueueDoneFrame + 120)
                || (sMaxFrames && sFrame > sMaxFrames)) {
            fprintf(stderr, "[input-script] stopping core at frame %u\n", sFrame);
            sCoreDoCommand(M64CMD_STOP, 0, NULL);
        }
    }

    dsce_drain_log(); /* [DSCE] every frame, so the crash/freeze sequence is captured to JSONL */
    dsce_drain_firehose();

    if (sTelemetry && sRdram && sMarioAddr && sTickAddr) {
        /* tick-indexed mode: one row per sim-tick increment, exact floats (bit-comparable) */
        unsigned tick = rd_u32(sTickAddr);
        if (tick != sLastTick) {
            sLastTick = tick;
            /* poll number second: the xtest runner calibrates tick->poll from it to
             * compile tick-authored input specs into poll-indexed rule files */
            fprintf(sTelemetry, "%u,%u,%.9g,%.9g,%.9g,%d,%08x,%.9g\n", tick, sFrame,
                    rd_f32(sMarioAddr + MARIO_POS),
                    rd_f32(sMarioAddr + MARIO_POS + 4),
                    rd_f32(sMarioAddr + MARIO_POS + 8),
                    rd_s16(sMarioAddr + MARIO_FACEYAW),
                    rd_u32(sMarioAddr + MARIO_ACTION),
                    rd_f32(sMarioAddr + MARIO_FLOORH));
        }
    } else if (sTelemetry && sRdram && sMarioAddr && (sFrame % 5) == 0) {
        fprintf(sTelemetry, "%u,%.1f,%.1f,%.1f,%d,%08x,%d,%.1f\n", sFrame,
                rd_f32(sMarioAddr + MARIO_POS),
                rd_f32(sMarioAddr + MARIO_POS + 4),
                rd_f32(sMarioAddr + MARIO_POS + 8),
                rd_s16(sMarioAddr + MARIO_FACEYAW),
                rd_u32(sMarioAddr + MARIO_ACTION),
                sAreaAddr ? rd_s16(sAreaAddr) : -1,
                rd_f32(sMarioAddr + MARIO_FLOORH));
        fflush(sTelemetry);
    }

    if (sPeekAddr && sRdram && sTelemetry && (sFrame % 5) == 0) {
        fprintf(sTelemetry, "PEEK,%u,%u,%u,%u,%u\n", sFrame, rd_u32(sPeekAddr),
                rd_u32(sPeekAddr + 4), rd_u32(sPeekAddr + 8), rd_u32(sPeekAddr + 12));
    }
    if (sPeek2Addr && sRdram && sTelemetry && (sFrame % 5) == 0) {
        fprintf(sTelemetry, "PEEK2,%u,%u,%u,%u,%u,%u,%u,%u,%u\n", sFrame,
                rd_u32(sPeek2Addr), rd_u32(sPeek2Addr + 4), rd_u32(sPeek2Addr + 8),
                rd_u32(sPeek2Addr + 12), rd_u32(sPeek2Addr + 16), rd_u32(sPeek2Addr + 20),
                rd_u32(sPeek2Addr + 24), rd_u32(sPeek2Addr + 28));
    }

    /* CT_DSCE_ADDR: peek the DSCE N64 telemetry block (7 BE u32s: magic 'DSCE', frame, tickUs,
     * tickUsMax, arenaFree, arenaFreeMin, action) and append CSV to CT_TELEMETRY. Logs once to
     * stderr when the magic first appears (= the spike actor is alive). */
    if (sDsceAddr && sRdram && (sFrame % 5) == 0) {
        unsigned magic = rd_u32(sDsceAddr);
        if (magic == 0x44534345u) {
            if (!sDsceSeen) {
                sDsceSeen = 1;
                fprintf(stderr, "[input-script] DSCE telemetry LIVE at %08x (frame %u)\n", sDsceAddr, sFrame);
            }
            if (sTelemetry) {
                fprintf(sTelemetry, "DSCE,%u,%u,%u,%u,%u,%u,%08x,%.2f,%.2f,%.2f,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n", sFrame,
                        rd_u32(sDsceAddr + 4), rd_u32(sDsceAddr + 8), rd_u32(sDsceAddr + 12),
                        rd_u32(sDsceAddr + 16), rd_u32(sDsceAddr + 20), rd_u32(sDsceAddr + 24),
                        rd_f32(sDsceAddr + 28), rd_f32(sDsceAddr + 32), rd_f32(sDsceAddr + 36),
                        rd_u32(sDsceAddr + 40), rd_u32(sDsceAddr + 44),
                        rd_u32(sDsceAddr + 48), rd_u32(sDsceAddr + 52),
                        rd_u32(sDsceAddr + 56), rd_u32(sDsceAddr + 60), rd_u32(sDsceAddr + 64),
                        rd_u32(sDsceAddr + 68), rd_u32(sDsceAddr + 72), rd_u32(sDsceAddr + 76));
                fflush(sTelemetry);
            }
        }
    }

    sFrame++;
}

EXPORT void CALL ControllerCommand(int Control, unsigned char *Command) {
    (void) Control; (void) Command;
}

EXPORT void CALL ReadController(int Control, unsigned char *Command) {
    (void) Control; (void) Command;
}

EXPORT int CALL RomOpen(void) {
    sFrame = 0;
    load_script();
    return 1;
}

EXPORT void CALL RomClosed(void) {
}

EXPORT void CALL SDL_KeyDown(int keymod, int keysym) {
    (void) keymod; (void) keysym;
}

EXPORT void CALL SDL_KeyUp(int keymod, int keysym) {
    (void) keymod; (void) keysym;
}
