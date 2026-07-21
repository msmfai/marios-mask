# v0.1.0-alpha.2 release gate

Version: `0.1.0-alpha.2`

Tag: `v0.1.0-alpha.2`

Status: native GUI release candidate

This release builds a local Mario's Mask ROM from user-supplied NTSC-US Super Mario
64 and Majora's Mask ROMs. The public repository and downloads contain no ROMs or
extracted game assets.

The tag is ready only when:

- the source/history game-data audit passes;
- ROM normalization tests pass for `.z64`, `.v64`, `.n64`, compressed MM, and
  decompressed MM;
- Windows x86-64, Linux x86-64, Mac Apple Silicon, and Mac Intel packages all build;
- every assembled package passes the game-data audit; and
- an end-to-end build still produces the validated release-ROM SHA-256
  `6a3c66b66ee31f0bf271c1c17001b46c0e18bcf9e697f1d605acba91c96349db`.

The platform packages are builder tools, not game releases. Generated ROMs remain
local and are ignored by Git.
