#ifndef DSCE_N64_ABI_H
#define DSCE_N64_ABI_H

/* Compile-time contracts for data shared by MM, SM64, the R4300, RSP, and RDP.
 * ELF class/ISA/endianness are checked again after linking because IDO exposes no
 * portable endian macro. */
#include "libc/assert.h"

static_assert(sizeof(void*) == 4, "DSCE requires the N64 o32 ABI (32-bit pointers)");
static_assert(sizeof(uintptr_t) == 4, "DSCE requires 32-bit uintptr_t");
static_assert(sizeof(long) == 4, "DSCE requires the N64 o32 ABI (32-bit long)");
static_assert(sizeof(float) == 4, "DSCE requires 32-bit float");
static_assert(sizeof(double) == 8, "DSCE requires 64-bit double");
static_assert(sizeof(Gfx) == 8, "RSP display-list commands must be exactly 8 bytes");
static_assert(sizeof(Vtx) == 16, "RSP vertices must be exactly 16 bytes");
static_assert(sizeof(Mtx) == 64, "RSP matrices must be exactly 64 bytes");

#endif
