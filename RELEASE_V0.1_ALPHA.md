# v0.1.0-alpha.6 release gate

Version: `0.1.0-alpha.6`

Tag: `v0.1.0-alpha.6`

Status: standalone native GUI release candidate

This release builds a local Mario's Mask ROM from user-supplied NTSC-US Super Mario
64 and Majora's Mask ROMs. The public downloads provide the builder; users supply the
two game files locally.

The tag is ready only when:

- the source/history game-data audit passes;
- ROM normalization tests pass for `.z64`, `.v64`, `.n64`, compressed MM, and
  decompressed MM;
- Windows x86-64, Linux x86-64, Mac Apple Silicon, and Mac Intel packages all build;
- every assembled package passes the game-data audit; and
- each download stays below the lightweight package size limit and contains the
  native builder package; and
- an end-to-end build still produces the validated release-ROM SHA-256
  `6d60250f851598b56dc2345b6a453fbe918ffa44f200500eb4688578059b42ed`.

The platform packages distribute the builder. Generated ROMs stay local and are
ignored by Git.
