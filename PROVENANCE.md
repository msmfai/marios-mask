# Public-source boundary

This repository contains only the project-authored standalone builder, release
packaging, documentation, and a transparent two-input recipe.

It does not contain ROMs, extracted game assets, decompilation source trees,
Majora's Mask source context, or the private mod-development repository. The
builder accepts exact user-supplied inputs and constructs the output locally.

The recipe format records every operation as one of:

- copy bytes from the user's Majora's Mask input;
- copy bytes from the user's Super Mario 64 input;
- emit an explicit literal payload stored in the recipe; or
- copy bytes already emitted, preserving their original classification.

Input and output SHA-256 digests are part of the recipe header. The verifier
reports byte totals for each origin class and a digest of the complete stored
literal payload. See [`patcher/recipe/FORMAT.md`](patcher/recipe/FORMAT.md).

This mechanical classification makes the recipe inspectable. It does not, by
itself, decide copyright ownership or grant rights in user-supplied games.

The Rust builder and project documentation are released under GPL-3.0-only.
Third-party Rust dependencies retain the licenses recorded by their projects
and locked versions.
