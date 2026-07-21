# DSCE Brother's Mask — N64 ROM edition: build machinery.
# Drives the pinned private dependency clones under .work/, applies the
# mod (patches/ + src/) at build time, and drops ROMs in out/. See README.md.

MM      ?= .work/mm
SM64    ?= .work/sm64
VERSION := n64-us
OUT     ?= out
TOOLCHAIN ?= $(CURDIR)/.work/toolchain

# Keep every helper on the same dependency trees when callers override MM/SM64 (the
# standalone two-ROM wrapper does this with private, pinned clones under .work/).
export DSCE_MM_TREE := $(abspath $(MM))
export DSCE_SM64_TREE := $(abspath $(SM64))
export DSCE_TOOLCHAIN := $(abspath $(TOOLCHAIN))

# Host overrides (Apple Silicon, discovered 2026-07-02 — see README):
#  - RUN_CC_CHECK=0: host gcc lacks -m32 here (the check pass is advisory anyway)
#  - ICONV: must be GNU iconv (BSD iconv rejects some source bytes, e.g. PreRender.c);
#    pinned from the nix store into toolchain/bin/gnu-iconv
#  - MIPS_BINUTILS_PREFIX: our o32-capable binutils (make toolchain)
MM_ARGS := RUN_CC_CHECK=0 ICONV=$(TOOLCHAIN)/bin/gnu-iconv \
           MIPS_BINUTILS_PREFIX=$(TOOLCHAIN)/bin/mips-linux-gnu-
JOBS ?= 10
TESTBOOT ?= 0
TB_SCENE ?= TERMINA_FIELD
TB_SPAWN ?= 0
TB_GRANT_MASK ?= 1
XTEST ?= 0
XTEST_VARIANT ?= A
XTEST_SHIPPED ?= 0
DEBUG ?= 0
# Debug instrumentation is compile-time composable.  All groups are forcibly
# disabled when DEBUG=0.  Full debug keeps the causal audio recorder and the
# lower-rate gameplay stream, while the redundant legacy ring and HUD default
# off.  Override any DBG_* value with 0/1 for a focused performance build.
DBG_LEGACY ?= 0
DBG_AUDIO ?= $(DEBUG)
DBG_GAMEPLAY ?= $(DEBUG)
DBG_HUD ?= 0
DBG_LEGACY_EFFECTIVE := $(if $(and $(filter 1,$(DEBUG)),$(filter 1,$(DBG_LEGACY))),1,0)
DBG_AUDIO_EFFECTIVE := $(if $(and $(filter 1,$(DEBUG)),$(filter 1,$(DBG_AUDIO))),1,0)
DBG_GAMEPLAY_EFFECTIVE := $(if $(and $(filter 1,$(DEBUG)),$(filter 1,$(DBG_GAMEPLAY))),1,0)
DBG_HUD_EFFECTIVE := $(if $(and $(filter 1,$(DEBUG)),$(filter 1,$(DBG_HUD))),1,0)
DBG_FIREHOSE_EFFECTIVE := $(if $(filter 1,$(DBG_LEGACY_EFFECTIVE) $(DBG_AUDIO_EFFECTIVE) $(DBG_GAMEPLAY_EFFECTIVE)),1,0)
DBG_CONFIG_ID := $(DBG_LEGACY_EFFECTIVE)$(DBG_AUDIO_EFFECTIVE)$(DBG_GAMEPLAY_EFFECTIVE)$(DBG_HUD_EFFECTIVE)
ifneq ($(strip $(filter-out 0 1,$(DEBUG) $(DBG_LEGACY) $(DBG_AUDIO) $(DBG_GAMEPLAY) $(DBG_HUD))),)
$(error DEBUG and every DBG_* setting must be exactly 0 or 1)
endif
# SM64 anims staged into the mod (hex ids): the set observed across the capability suite
# plus their action families. gDsceAnimFallbacks counts anything we missed (suite: ==0).
DSCE_ANIM_IDS := 00 01 02 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 11 12 13 14 15 16 17 18 19 1A 1B 1C 1D 28 29 2A 2B 2C 2D 30 33 34 35 3A 3B 3C 3D 3F 40 41 42 43 44 45 46 47 48 4A 4B 4C 4D 4E 4F 50 52 53 56 57 58 59 5A 5B 5C 5D 65 66 67 68 69 6A 6B 6C 6D 6E 6F 70 71 72 74 75 76 77 78 7A 7B 7C 7D 7E 7F 80 81 82 83 84 85 86 87 88 89 8A 8B 8C 8D 8F 90 91 92 93 94 95 96 97 98 99 9A 9B 9E 9F A0 A1 A2 A3 A4 A5 A6 A7 A8 A9 AA AB AC AD AE AF B0 B1 B2 B5 B6 B7 B8 B9 BA BB BC BD BE BF C0 C1 C2 C3 C4 C5 C6 C7 C8 C9 CA CB CC CF D0
TB_TAG = $(if $(filter TERMINA_FIELD,$(TB_SCENE)),,-$(shell echo $(TB_SCENE) | tr 'A-Z_' 'a-z-'))$(if $(filter 0,$(TB_SPAWN)),,-s$(TB_SPAWN))$(if $(filter 1,$(TB_GRANT_MASK)),,-nomask)$(if $(filter 0,$(XTEST)),,-xtest$(if $(filter A,$(XTEST_VARIANT)),,-$(shell echo $(XTEST_VARIANT) | tr 'A-Z' 'a-z'))$(if $(filter 0,$(XTEST_SHIPPED)),,-shipped))$(if $(filter 0,$(DEBUG)),,-debug$(if $(filter 0110,$(DBG_CONFIG_ID)),,-dbg$(DBG_CONFIG_ID)))
MOD_OUT = $(if $(filter 1,$(TESTBOOT)),mm-dsce-test$(TB_TAG).z64,mm-dsce.z64)
RESTORE_MM = tools/stage-voice.sh restore; tools/stage-mario-sfx.sh restore; \
             tools/stage-mask-item.sh restore; rm -rf $(MM)/src/dsce; \
             git -C $(MM) checkout -- .

.PHONY: all rom mod restore-mm toolchain check-toolchain test acquisition-smoke clean distclean

all: rom

toolchain:
	tools/build-binutils.sh

check-toolchain:
	@$(TOOLCHAIN)/bin/mips-linux-gnu-ld -V 2>/dev/null | grep -q elf32btsmip || \
	    { echo "toolchain missing — run 'make toolchain' first"; exit 1; }
	@$(TOOLCHAIN)/bin/gnu-iconv --version >/dev/null 2>&1 || \
	    { echo "GNU iconv missing — run 'make toolchain' first"; exit 1; }

# Idempotent recovery for wrappers when any of the early staging recipes fail.
# Keep this callable independently of check-toolchain: recovery must still work after
# a partially completed first-run bootstrap.
restore-mm:
	@$(RESTORE_MM)

# Vanilla ROM — proves the substrate builds + links end-to-end. COMPARE=0 because our
# binutils 2.42 + GNU libiconv produce a byte-DIFFERENT (not byte-matching) ROM; the mod
# builds NON_MATCHING anyway, so functional (boot) verification is the bar, not the MD5.
# Use `make rom-match` to insist on the retail MD5 (expected to fail on this toolchain).
rom: check-toolchain
	$(MAKE) -C $(MM) -j$(JOBS) rom $(MM_ARGS) COMPARE=0
	@mkdir -p $(OUT)
	cp $(MM)/build/$(VERSION)/mm-$(VERSION).z64 $(OUT)/mm-vanilla.z64
	@md5 -q $(OUT)/mm-vanilla.z64 2>/dev/null || md5sum $(OUT)/mm-vanilla.z64
	@echo "==> $(OUT)/mm-vanilla.z64 (boot-test this; not byte-matching)"

rom-match: check-toolchain
	$(MAKE) -C $(MM) -j$(JOBS) rom $(MM_ARGS) COMPARE=1

# DSCE mod ROM — applies patches to the clean private MM checkout, builds,
# copies the local output, and restores the checkout on every normal exit.
mod: check-toolchain
	tools/gen_tuning.py tuning.yaml src/dsce_tuning.h
	@test -z "$$(git -C $(MM) status --porcelain -- src include assets spec Makefile)" || \
	    { echo "ERROR: $(MM) has local changes — commit/stash them first"; exit 1; }
	@for p in patches/*.patch; do \
	    [ -e "$$p" ] || continue; \
	    echo "applying $$p"; git -C $(MM) apply "$(CURDIR)/$$p" || exit 1; \
	done
	printf '#define DSCE_TESTBOOT %s\n#define DSCE_TB_ENTRANCE ENTRANCE(%s, %s)\n#define DSCE_TB_GRANT_MASK %s\n#define DSCE_XTEST %s\n#define DSCE_XTEST_SHIPPED %s\n#define DSCE_DEBUG %s\n#define DSCE_DBG_LEGACY %s\n#define DSCE_DBG_AUDIO %s\n#define DSCE_DBG_GAMEPLAY %s\n#define DSCE_DBG_HUD %s\n#define DSCE_DBG_FIREHOSE %s\n' "$(TESTBOOT)" "$(TB_SCENE)" "$(TB_SPAWN)" "$(TB_GRANT_MASK)" "$(XTEST)" "$(XTEST_SHIPPED)" "$(DEBUG)" "$(DBG_LEGACY_EFFECTIVE)" "$(DBG_AUDIO_EFFECTIVE)" "$(DBG_GAMEPLAY_EFFECTIVE)" "$(DBG_HUD_EFFECTIVE)" "$(DBG_FIREHOSE_EFFECTIVE)" > src/dsce_config.h
	tools/gen_xtest_arena.py /tmp/dsce-xtest-collision.inc.c src/dsce_xtest_arena.h $(XTEST_VARIANT)
	rsync -a --delete src/ $(MM)/src/dsce/
# Stage Mario's data from the user's SM64 ROM extraction (installation contract: both
# baseroms in -> one modded MM ROM out; no game data lives in this repo).
	@test -f $(SM64)/actors/mario/model.inc.c \
	       -a -f $(SM64)/build/us/actors/mario/mario_logo.rgba16.inc.c \
	       -a -f $(SM64)/build/us/actors/peach/peach_dress.rgba16.inc.c || \
	    { echo "ERROR: SM64 checkout is not extracted -- use tools/build_from_roms.sh"; exit 1; }
	mkdir -p $(MM)/src/dsce/sm64_assets/actors/mario $(MM)/src/dsce/sm64_assets/anims
	cp $(SM64)/actors/mario/model.inc.c $(MM)/src/dsce/sm64_assets/actors/mario/
	cp $(SM64)/build/us/actors/mario/*.inc.c $(MM)/src/dsce/sm64_assets/actors/mario/
	cp $(SM64)/assets/anims/anim_*.inc.c $(MM)/src/dsce/sm64_assets/anims/
	tools/gen_mario_anims.py $(MM)/src/dsce/sm64_assets/anims $(MM)/src/dsce/dsce_mario_anims.c $(DSCE_ANIM_IDS)
# Mario's VOICE: swap Fierce Deity's donor voice samples (adult_link_*, endgame-only
# content) for Mario clips from the user's SM64 extraction. extracted/ is not
# git-tracked, so originals are backed up and restored by the cleanup/failure paths.
	tools/stage-cosmetics.sh $(MM)/src/dsce/sm64_assets $(SM64)/actors/mario/mario_logo.rgba16.png
	tools/stage-statue.sh $(MM)/src/dsce
	tools/stage-mask-item.sh stage $(MM)/src/dsce
	python3 tools/check_content_contracts.py --project $(CURDIR) --mm $(MM) \
	    --original-logo $(SM64)/actors/mario/mario_logo.rgba16.png \
	    --staged-logo $(MM)/src/dsce/sm64_assets/actors/mario/mario_logo.rgba16.inc.c
	tools/stage-voice.sh stage
	tools/stage-mario-sfx.sh stage
	rm -rf $(MM)/build/$(VERSION)/assets/audio
# The mm Makefile does NOT track C-header dependencies (its own comment at :390), so objects
# built before our patches keep the UNPATCHED tables (cost us hours: z_actor_dlftbls.o kept the
# UNSET actor row -> Actor_Spawn returned NULL). Force-rebuild every object a patch can affect.
	rm -f $(MM)/build/$(VERSION)/src/code/z_actor_dlftbls.o \
	      $(MM)/build/$(VERSION)/src/code/z_sram_NES.o \
	      $(MM)/build/$(VERSION)/src/code/z_play.o \
	      $(MM)/build/$(VERSION)/src/code/z_play_hireso.o \
	      $(MM)/build/$(VERSION)/src/code/z_message.o \
	      $(MM)/build/$(VERSION)/src/code/object_table.o \
	      $(MM)/build/$(VERSION)/src/overlays/gamestates/ovl_title/z_title.o \
	      $(MM)/build/$(VERSION)/src/overlays/actors/ovl_En_Toto/z_en_toto.o \
	      $(MM)/build/$(VERSION)/spec
# our own generated dsce_config.h suffers the same no-header-deps trap: always rebuild dsce objs
	rm -rf $(MM)/build/$(VERSION)/src/dsce
# the staged mask-item art mutates the icon/name archives: force their rebuild
	rm -rf $(MM)/build/$(VERSION)/assets/archives/icon_item_static $(MM)/build/$(VERSION)/assets/archives/item_name_static $(MM)/build/$(VERSION)/extracted 2>/dev/null || true
	$(MAKE) -C $(MM) -j$(JOBS) rom $(MM_ARGS) NON_MATCHING=1 COMPARE=0 || \
	    { $(RESTORE_MM); exit 1; }
	tools/check_sequence_span.py $(TOOLCHAIN)/bin/mips-linux-gnu-nm \
	    $(TOOLCHAIN)/bin/mips-linux-gnu-objdump \
	    $(MM)/build/$(VERSION)/assets/audio/sequences/*.o || \
	    { $(RESTORE_MM); exit 1; }
	tools/check_sfx_font_selectors.py $(TOOLCHAIN)/bin/mips-linux-gnu-nm \
	    $(TOOLCHAIN)/bin/mips-linux-gnu-objdump \
	    $(MM)/build/$(VERSION)/assets/audio/sequences/seq_0.prg.o || \
	    { $(RESTORE_MM); exit 1; }
	tools/check_n64_invariants.py \
	    --rom $(MM)/build/$(VERSION)/mm-$(VERSION).z64 \
	    --map $(MM)/build/$(VERSION)/mm-$(VERSION).map \
	    --elf $(MM)/build/$(VERSION)/mm-$(VERSION).elf \
	    --debug $(DEBUG) \
	    --debug-legacy $(DBG_LEGACY_EFFECTIVE) \
	    --debug-firehose $(DBG_FIREHOSE_EFFECTIVE) \
	    --debug-audio $(DBG_AUDIO_EFFECTIVE) || { $(RESTORE_MM); exit 1; }
	$(MM)/.venv/bin/python -m ipl3checksum check --cic 6105 \
	    $(MM)/build/$(VERSION)/mm-$(VERSION).z64 || \
	    { $(RESTORE_MM); exit 1; }
	@mkdir -p $(OUT)
	tools/stage-voice.sh restore
	tools/stage-mario-sfx.sh restore
	tools/stage-mask-item.sh restore
	cp $(MM)/build/$(VERSION)/mm-$(VERSION).z64 $(OUT)/$(MOD_OUT)
	cp $(MM)/build/$(VERSION)/mm-$(VERSION).map $(OUT)/$(MOD_OUT).map
# sidecar .va: per-ROM telemetry addresses (the shared linker map only reflects the LAST build,
# so runs against any earlier ROM would read garbage otherwise -- the stale-VA trap, root-fixed)
	@grep -E '\s(gDsceTelemetry|gDsceProbe|gDsceLifecycleProbe|gDsceLogHead|gDsceLogRing|gDsceMarioState|gDscePlayFrame)$$' $(MM)/build/$(VERSION)/mm-$(VERSION).map | \
	    awk '{gsub(/^0x0*/,"",$$1); print $$2"="$$1}' > $(OUT)/$(MOD_OUT).va
	@grep -E '\s(gDsceFhRing|gDsceFhHead|gDsceSeqFlightRing|gDsceSeqFlightHead|gDsceSeqFlightFrozen)$$' $(MM)/build/$(VERSION)/mm-$(VERSION).map | \
	    awk '{gsub(/^0x0*/,"",$$1); print $$2"="$$1}' >> $(OUT)/$(MOD_OUT).va || true
	rm -rf $(MM)/src/dsce
	git -C $(MM) checkout -- .
	@echo "==> $(OUT)/$(MOD_OUT)"

# Headless behavioural/metamorphic test suite. NEEDS BOTH test ROMs built from the SAME
# sources (the runner reads gDsceTelemetry's address from the latest linker map; a stale
# ROM has a different address and reads zeros): make testroms first after any src change.
testroms:
	$(MAKE) mod TESTBOOT=1
	$(MAKE) mod TESTBOOT=1 TB_SCENE=LAUNDRY_POOL
	$(MAKE) mod TESTBOOT=1 TB_SCENE=SOUTHERN_SWAMP_POISONED TB_SPAWN=8
	$(MAKE) mod TESTBOOT=1 TB_SCENE=LAUNDRY_POOL TB_GRANT_MASK=0

test:
	tools/check_acquisition_boot.py
	tools/run_tests.py

acquisition-smoke:
	tools/check_acquisition_boot.py

# Termina smoke matrix: boot many scenes, walk around, assert base invariants in each.
# Sweeps the collision adapters across real geometry. Build the ROMs first (slow, ~2min each).
MATRIX_SCENES := EAST_CLOCK_TOWN WEST_CLOCK_TOWN NORTH_CLOCK_TOWN SOUTH_CLOCK_TOWN MILK_ROAD
matrixroms: testroms
	@for sc in $(MATRIX_SCENES); do $(MAKE) mod TESTBOOT=1 TB_SCENE=$$sc || exit 1; done

test-matrix:
	tools/run_tests.py --matrix

# XTEST oracle ROM: the SM64+Clock Town tree with area 1 collision replaced by the
# generated cross-game arena (tools/gen_xtest_arena.py); tree restored after.
sm64-xtest:
	tools/stage-xtest-sm64.sh A
sm64-xtest-b:
	tools/stage-xtest-sm64.sh B
sm64-xtest-c:
	tools/stage-xtest-sm64.sh C
sm64-xtest-d:
	tools/stage-xtest-sm64.sh D

# XTEST: totalistic cross-game moveset parity over the matched arena.
# Needs: make sm64-xtest && make mod TESTBOOT=1 XTEST=1
test-xtest:
	tools/xtest.py

# Shipped-config parity tier: the mod runs the SHIPPED MarioSpeedMul (1.5 feel
# compensation) on the same arenas; comparison under the declared transform.
# Needs: make mod TESTBOOT=1 XTEST=1 XTEST_SHIPPED=1 XTEST_VARIANT={A,B,C,D}
test-xtest-shipped:
	tools/xtest.py --shipped

# R3 sound-event relation, report tier (families; informational, always exit 0)
test-xtest-sounds:
	tools/xtest.py --sounds

# Cross-game metamorphic tests: the real SM64 ROM as Mario's oracle (goal 10).
# Needs out/mm-dsce-test.z64 (make mod TESTBOOT=1) + the sm64 decomp built once.
test-xgame:
	tools/xgame_test.py

# Cosmetic pixel assertion (windowed GL run; not part of the fast suite)
test-visual:
	tools/visual_check.py

clean:
	$(MAKE) -C $(MM) clean
	rm -rf $(OUT)

distclean: clean
	rm -rf $(TOOLCHAIN)
