# Unified diffs against the pristine MM decomp, applied by `make mod` in filename order.

- `0001`: game integration and debug telemetry hooks.
- `0003`: debug-only audio-sequencer flight recorder and fault boundaries.
- `0004`: assembler errors for sequence sections outside `.startseq/.endseq`.

The subsequent object-span audit in `Makefile` covers raw data directives that cannot
be intercepted by the sequence macros.
