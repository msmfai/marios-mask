#ifndef DSCE_TELEMETRY_H
#define DSCE_TELEMETRY_H

/* One definition shared by the producer, renderer, host symbol reader, and tests. */
typedef struct DsceTelemetry {
    u32 magic;
    u32 frame;
    u32 tickUs;
    u32 tickUsMax;
    u32 arenaFree;
    u32 arenaFreeMin;
    u32 action;
    f32 posX;
    f32 posY;
    f32 posZ;
    u32 mmHealth;
    u32 animId;
    u32 poseSum;
    u32 animFallbacks;
    u32 voiceReqs;
    u32 maskItem;
    u32 foleyReqs;
    u32 bodySum;
    u32 camDist;
    u32 questState;
} DsceTelemetry;

static_assert(sizeof(DsceTelemetry) == 0x50,
              "DsceTelemetry changed; update every host-side decoder explicitly");

extern DsceTelemetry gDsceTelemetry;

#endif
