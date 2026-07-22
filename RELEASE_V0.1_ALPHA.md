# v0.1.0-alpha.3 release gate

Version: `0.1.0-alpha.3`

Tag: `v0.1.0-alpha.3`

Status: standalone native GUI release candidate

This release builds a local Mario's Mask ROM from user-supplied NTSC-US Super Mario
64 and Majora's Mask ROMs. The public repository and downloads contain no ROMs or
extracted game assets.

The tag is ready only when:

- the source/history game-data audit passes;
- ROM normalization tests pass for `.z64`, `.v64`, `.n64`, compressed MM, and
  decompressed MM;
- Windows x86-64, Linux x86-64, Mac Apple Silicon, and Mac Intel packages all build;
- every assembled package passes the game-data audit; and
- each download stays below the lightweight package size limit and contains no
  Python runtime, compiler, decomp tree, or WSL environment; and
- an end-to-end build still produces the validated release-ROM SHA-256
  `f580f8a12e45bc7123487d7214e1a5d5678b6769c7242c19c0cb6f0bcd2c8090`.

The platform packages are builder tools, not game releases. Generated ROMs remain
local and are ignored by Git.
