# N64 invariants dossier

This dossier records the contracts that matter when SM64 assets and movement code are
linked into the Majora's Mask N64 runtime. It distinguishes facts the build can prove
from behavior that only a real console can prove. An emulator pass is evidence, not a
hardware certificate.

## Evidence base

The primary sources used for the rules below are:

- Nintendo's [CPU/cache and I/O model](https://ultra64.ca/files/documentation/online-manuals/man/pro-man/pro04/04-02.html),
  [`osWritebackDCache`](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/n64man/os/osWritebackDCache.htm),
  and [`osEPiStartDma`](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/n64man/os/osEPiStartDma.htm).
- Nintendo's [CPU/RSP/RDP address spaces](https://ultra64.ca/files/documentation/online-manuals/man/kantan/step1/1-4.html),
  [task-buffer alignment rules](https://ultra64.ca/files/documentation/online-manuals/functions_reference_manual_2.0i/os/OSTask.html),
  and [RDP completion/synchronization guidance](https://ultra64.ca/files/documentation/online-manuals/man/pro-man/pro25/25-08.html).
- The upstream [SM64 decompilation](https://github.com/n64decomp/sm64), including its
  exact US ROM hash and its statement that `NON_MATCHING` selects functionally
  equivalent implementations while avoiding known undefined behavior.
- The upstream [Majora's Mask decompilation](https://github.com/zeldaret/mm), including
  its N64-US-only revision, baserom hashes, shiftability warning, linker spec,
  `dmadata` implementation, Expansion Pak buffer layout, and CIC-6105 checksum step.
- The Mupen64Plus-Next [documented core options](https://docs.libretro.com/library/mupen64plus/)
  and [option definitions](https://github.com/libretro/mupen64plus-libretro-nx/blob/master/libretro/libretro_core_options.h).
- The real-hardware-oriented [libdragon guidance](https://github.com/DragonMinded/libdragon),
  which recommends Ares homebrew mode for advanced development but still treats real
  N64 hardware as the target. This is why the canonical Mupen profile below is a
  high-sensitivity test, not the final authority.

## Enforced contracts

| Boundary | Invariant | Enforcement | What remains unproved |
|---|---|---|---|
| Inputs | SM64 US SHA-1 and compressed MM US MD5 are exact; both decomp commits are pinned | `tools/build_from_roms.sh` fails before extraction/build | Ownership and local cartridge provenance |
| CPU ABI | ELF32, big-endian, MIPS III/o32; pointers and `long` are 32-bit | `dsce_n64_abi.h` compile-time assertions plus post-link ELF audit | CPU timing and every possible C undefined behavior |
| RSP data | `Gfx=8`, `Vtx=16`, `Mtx=64`; imported animation and part layouts are exact | compile-time assertions; imported Mario/Peach display-list symbols are audited for 8-byte alignment | Semantics of every generated display-list opcode |
| ROM header | Big-endian magic, MM US identity/revision, KSEG0 entrypoint, populated CRC words, <=64 MiB | `check_n64_invariants.py`; upstream `ipl3checksum check --cic 6105` independently verifies CRC1/CRC2 | Flashcart firmware quirks |
| Segment layout | Every ROM segment is ordered, aligned, bounded by `_RomEnd`; linker assertions succeeded | map audit after every mod build | Runtime corruption after boot |
| Resident RDRAM | code/data/buffers do not overlap; framebuffer remains `0x80780000..0x80800000`; at least 2 MiB static Zelda-arena headroom remains | compile/link assertions and map audit | fragmentation and scene-dependent allocation peaks |
| Virtual ROM | `dmadata` has bounded, ordered VROM and physical spans, legal PI alignment, an owner entry, a zero sentinel, and zero tail padding | binary table audit after every build | correctness of a caller's requested RAM destination |
| Audio sequence | no aseq section may appear outside `.startseq/.endseq`; advertised sequence length equals object payload | assembler errors plus `check_sequence_span.py` over all 123 sequences | runtime sequencer state and AI scheduling |
| SFX dispatch ABI | every generated game-side SFX enum ordinal equals its `_LANGUAGE_ASEQ` channel-table ordinal | `check_sfx_dispatch_alignment.py` before compilation | vanilla table edits outside the generated rows |
| SFX font selectors | each generated channel's compiled `fontinstr` local selector resolves through sequence 0's reverse-indexed font list to global font 41 (foley) or 42 (voice) | `check_sfx_font_selectors.py` over the assembled sequence object | later runtime mutation of a valid channel's font state |
| Debug boundary | firehose/audio-flight/legacy/HUD groups are independently selectable; all are forbidden in release; enabled groups must link and disabled groups must not | conditional compilation plus map-symbol audit | host capture availability on a physical N64 |
| Telemetry ABI | producer and renderer use one 0x50-byte definition; firehose and flight records remain 32 bytes | shared header and compile-time assertions | host tools written for some future schema until deliberately updated |

The `dmadata` checks mirror MM's own loader: `romEnd == 0` means an uncompressed
entry, both physical words `0xFFFFFFFF` mean a SYMS entry, and `(0,0,0,0)` terminates
the table. Physical ROM addresses are required to be at least two-byte aligned;
Nintendo requires eight-byte RDRAM addresses and recommends 16-byte alignment for PI
reads. MM's DMA manager owns and invalidates its destination cache ranges. Any new
direct DMA introduced by this mod must use that manager or explicitly pair correct
cache maintenance with 16-byte-aligned/padded buffers.

## Cross-game boundaries

SM64's model source is recompiled under MM's F3DEX2 GBI rather than copying encoded
SM64 display-list bytes. The shared compatibility header is therefore a hard ABI:
animation fields, pointers, part records, `Gfx`, vertices, and matrices cannot drift
silently between translation units. The renderer establishes SM64's one-cycle,
one-light, no-fog material state before imported lists and restores MM's two-cycle
state afterward. MM remains responsible for task submission, cache management,
framebuffers, audio DMA, save data, and scene/overlay lifetime.

`NON_MATCHING=1`/`AVOID_UB` is deliberate. This project needs functionally safe code,
not reproduction of compiler-dependent undefined behavior. It does not make arbitrary
C safe: new shared structs and pointer/integer conversions still need explicit
contracts and are subject to the ABI audit.

## Canonical RetroArch accuracy profile

`tools/run_debug_release.py` creates a fresh core-options file inside every timestamped
run and points RetroArch at it with `global_core_options=true`. Automatic overrides
and per-game option files are disabled for that invocation, so the installed per-core
options and global user settings cannot silently change the test. The launcher also
rejects the run unless the live core log confirms Pure Interpreter and contains none
of the known cached-interpreter/ParaLLEl/8x markers.
The emulator and core binaries, profile, options, ROM, and symbols are hashed into the
run metadata. No emulator or core binary is modified.

The pinned profile is:

- pure R4300 interpreter (the core describes interpreter mode as best compatibility);
- CXD4 LLE RSP, not HLE;
- Angrylion software RDP, `Filtered` VI output, `High` synchronization, one worker
  (the core says one behaves like original Angrylion and may avoid threaded bugs);
- original frame rate and automatic database timing; no Count-per-Op/VI overclock;
- Expansion Pak enabled; TLB exceptions are not ignored;
- no frame duplication, rewind, run-ahead, preemptive frames, threaded video, or shader;
- frontend audio sync and vsync enabled.

This profile maximizes compatibility/error visibility within Mupen64Plus-Next. It can
be slower than the former ParaLLEl/upscaled profile. A failure caused solely by the
host being unable to run it in real time is an emulator-performance failure, not a ROM
failure; record that separately and use real hardware for the decision.

## Mandatory real-N64 residual gate

Before calling a release hardware-safe, boot the ordinary release ROM on an NTSC N64
with Expansion Pak and a known-good development/flash cartridge, then run the Laundry
Pool acquisition, transformation, scene transition, heavy swamp swim, repeated jumps,
voice/foley, pause/save, and unmask/remask paths. Confirm stable native pacing, no
audio crackle/dropout, no visual RDP corruption, no freeze, and persistent save data.

An all-groups or focused debug ROM may be run on hardware as a conservative stress
build (enabled HUD/rings add overhead), but host ClickHouse capture is unavailable unless a separate
hardware transport is deliberately implemented. The ROM never attempts filesystem or
network access, in an emulator or on a console.
