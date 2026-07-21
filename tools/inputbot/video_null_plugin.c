/* mupen64plus NULL VIDEO plugin: a real gfx plugin whose every operation is a no-op.
 * Purpose: true headless emulation for the DSCE N64 test pipeline. The core's built-in
 * "dummy" (no plugin attached) stalls Majora's Mask boot -- the RSP-HLE graphics task
 * handoff needs an attached plugin's ProcessDList/UpdateScreen cycle to complete so the
 * game's DP/SP message loop advances. This plugin completes the contract without rendering.
 *
 * Build:
 *   clang -dynamiclib -O2 -I/opt/homebrew/include/mupen64plus \
 *         -o mupen64plus-video-null.dylib video_null_plugin.c
 */
#include <stdio.h>

#define M64P_PLUGIN_PROTOTYPES 1
#include "m64p_types.h"
#include "m64p_plugin.h"
#include "m64p_common.h"

static void (*sCheckInterrupts)(void) = NULL;
static unsigned int *sMiIntrReg = NULL;
#define MI_INTR_DP 0x20

EXPORT m64p_error CALL PluginStartup(m64p_dynlib_handle CoreLibHandle, void *Context,
                                     void (*DebugCallback)(void *, int, const char *)) {
    (void) CoreLibHandle; (void) Context; (void) DebugCallback;
    return M64ERR_SUCCESS;
}

EXPORT m64p_error CALL PluginShutdown(void) {
    return M64ERR_SUCCESS;
}

EXPORT m64p_error CALL PluginGetVersion(m64p_plugin_type *PluginType, int *PluginVersion,
                                        int *APIVersion, const char **PluginNamePtr,
                                        int *Capabilities) {
    if (PluginType)    *PluginType = M64PLUGIN_GFX;
    if (PluginVersion) *PluginVersion = 0x010000;
    if (APIVersion)    *APIVersion = 0x020200;
    if (PluginNamePtr) *PluginNamePtr = "DSCE null video (headless)";
    if (Capabilities)  *Capabilities = 0;
    return M64ERR_SUCCESS;
}

EXPORT int CALL InitiateGFX(GFX_INFO Gfx_Info) {
    sCheckInterrupts = Gfx_Info.CheckInterrupts;
    sMiIntrReg = Gfx_Info.MI_INTR_REG;
    fprintf(stderr, "[video-null] initiated (headless)\n");
    return 1;
}

EXPORT int CALL RomOpen(void) {
    return 1;
}

EXPORT void CALL RomClosed(void) {
}

EXPORT void CALL ProcessDList(void) {
    /* Complete the task contract: raise the DP interrupt (the game blocks on RDPFULLSYNC
     * otherwise -- MM boot stalls with a polite no-op plugin). rsp-hle raises SP itself. */
    if (sMiIntrReg != NULL) {
        *sMiIntrReg |= MI_INTR_DP;
    }
    if (sCheckInterrupts != NULL) {
        sCheckInterrupts();
    }
}

EXPORT void CALL ProcessRDPList(void) {
    if (sMiIntrReg != NULL) {
        *sMiIntrReg |= MI_INTR_DP;
    }
    if (sCheckInterrupts != NULL) {
        sCheckInterrupts();
    }
}

EXPORT void CALL ShowCFB(void) {
}

EXPORT void CALL UpdateScreen(void) {
}

EXPORT void CALL ViStatusChanged(void) {
}

EXPORT void CALL ViWidthChanged(void) {
}

EXPORT void CALL ChangeWindow(void) {
}

EXPORT void CALL MoveScreen(int xpos, int ypos) {
    (void) xpos; (void) ypos;
}

EXPORT void CALL ResizeVideoOutput(int width, int height) {
    (void) width; (void) height;
}

EXPORT void CALL ReadScreen2(void *dest, int *width, int *height, int front) {
    (void) dest; (void) front;
    if (width) *width = 0;
    if (height) *height = 0;
}

EXPORT void CALL SetRenderingCallback(void (*callback)(int)) {
    (void) callback;
}

EXPORT void CALL FBRead(unsigned int addr) {
    (void) addr;
}

EXPORT void CALL FBWrite(unsigned int addr, unsigned int size) {
    (void) addr; (void) size;
}

EXPORT void CALL FBGetFrameBufferInfo(void *p) {
    (void) p;
}
