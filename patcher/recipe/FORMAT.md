# MMRECP03 transparent recipe format

All integers are unsigned little-endian. Commands are applied in order and
concatenated to form the output.

## Header

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 8 | ASCII `MMRECP03` |
| 8 | 8 | Output size |
| 16 | 32 | SHA-256 of decompressed Majora's Mask input |
| 48 | 32 | SHA-256 of Super Mario 64 input |
| 80 | 32 | SHA-256 of the validated Talon source derived from the Ocarina of Time input |
| 112 | 32 | SHA-256 of output |
| 144 | 4 | Command count |

## Commands

| Opcode | Payload | Meaning |
|---:|---|---|
| 0 | `u32 input_offset, u32 length` | Copy from Majora's Mask |
| 1 | `u32 input_offset, u32 length` | Copy from Super Mario 64 |
| 2 | `u32 length, byte[length]` | Emit the stored literal bytes |
| 3 | `u32 output_offset, u32 length` | Copy previously emitted output |
| 4 | `u32 input_offset, u32 length` | Copy from the locally derived stone-Talon source |

An output copy may overlap its destination, like an LZ back-reference. Each byte
inherits the classification of the byte it copies, so it cannot hide a new byte
class.

The decoder rejects incorrect input digests, zero-length commands, out-of-range
copies, references to unwritten output, output-size mismatches, trailing data,
and an incorrect output digest.

## Inspecting a recipe

From `patcher/`, run:

```sh
cargo run --release --features recipe-tool --bin marios-mask-recipe -- \
  verify <sm64.z64> <oot.z64> <decompressed-mm.z64> recipe/marios-mask.mmrecipe
```

The report gives the transitive MM, SM64, OoT, and literal byte totals, the number of
bytes physically stored as literals, output-copy totals, and the SHA-256 of all
literal payloads in command order.

## Build options record

The recipe always reconstructs the default build. Player choices are applied
afterwards to two small records in the output, each located by a unique
marker:

| Record | Layout | Builder writes |
|---|---|---|
| `DSCECOLR` | marker, 6 x RGB, version `2`, guard `A5 1D 5A E1` | Mario's palette |
| `DSCEOPTS` | marker, version `1`, slot count `16`, 16 value bytes, guard `A5 1D 5A E1` | value bytes |

`DSCEOPTS` value slots:

| Slot | Meaning | Values |
|---|---|---|
| 0 | Game mode | `0` Standard, `1` Classic (default) |
| 1-15 | Reserved | `0` |

The builder writes choices, not rules: the ROM decides what each mode means,
and treats unknown values as the default. The builder rejects a missing,
duplicated, newer-version, or unguarded record. When a changed byte lies in the
N64 boot-checksummed region, the header checksum is recomputed.
