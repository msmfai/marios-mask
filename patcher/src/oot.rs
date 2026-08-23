use anyhow::{ensure, Context, Result};

// Retail N64 revisions move dmadata when the boot segment changes. Try the
// documented locations first, then retain a structural fallback for compatible
// layouts that we have not enumerated here.
const KNOWN_DMADATA_STARTS: &[usize] = &[
    0x7430, // NTSC 1.0 and NTSC 1.1
    0x7950, // PAL 1.0 and PAL 1.1
    0x7960, // NTSC 1.2
];
const DMADATA_FALLBACK_END: usize = 0x40000;
const MAX_DMA_ENTRIES: usize = 2048;
const MAX_OBJECT_SIZE: usize = 2 * 1024 * 1024;
const TALON_PREFIX_SIZE: usize = 0xB7D0;
const TALON_SKELETON_OFFSET: usize = 0xB7B8;
const TALON_LIMB_TABLE_OFFSET: usize = 0xB778;
const TALON_LIMB_FIRST_OFFSET: usize = 0xB6B8;
const TALON_LIMB_COUNT: usize = 16;

const RGBA16_RANGES: &[(usize, usize)] = &[
    (0x6AC0, 132 * 2),
    (0x6BC8, 63 * 4 * 2),
    (0xA638, 16 * 16 * 2),
    (0xA838, 8 * 8 * 2),
    (0xAFB8, 16 * 32 * 2),
    (0xB3B8, 8 * 16 * 2),
    (0xB4B8, 16 * 16 * 2),
];

pub fn stone_talon_source(rom: &[u8]) -> Result<Vec<u8>> {
    let mut match_source = None;
    let starts = dmadata_starts(rom);
    ensure!(
        !starts.is_empty(),
        "could not locate a structurally valid Ocarina of Time DMA table"
    );
    for dmadata_start in starts {
        for index in 0..MAX_DMA_ENTRIES {
            let entry = dmadata_start + index * 16;
            if entry + 16 > rom.len() {
                break;
            }
            if rom[entry..entry + 16].iter().all(|byte| *byte == 0) {
                break;
            }
            if let Some(source) = talon_source_from_dma_entry(rom, entry) {
                ensure!(
                    match_source.is_none(),
                    "OoT contains more than one Talon object"
                );
                match_source = Some(source);
            }
        }
    }
    match_source.context("could not find a compatible Talon object in this Ocarina of Time ROM")
}

fn dmadata_starts(rom: &[u8]) -> Vec<usize> {
    let mut starts = Vec::new();
    for &start in KNOWN_DMADATA_STARTS {
        if is_dmadata_start(rom, start) {
            starts.push(start);
        }
    }

    // A retail dmadata table describes the ROM header, boot segment, and
    // itself in its first three entries. In other words, a candidate table
    // carries its own address twice and joins exactly onto the standard N64
    // header/boot boundary. That signature is much stronger than treating
    // arbitrary non-zero boot data as a table. Scan only the small boot/file-
    // table region and only at the format's 16-byte alignment.
    let end = rom.len().min(DMADATA_FALLBACK_END);
    if end >= 48 {
        for start in (0..=end - 48).step_by(16) {
            if !starts.contains(&start) && is_dmadata_start(rom, start) {
                starts.push(start);
            }
        }
    }
    starts
}

fn is_dmadata_start(rom: &[u8], start: usize) -> bool {
    let Some(entries) = rom.get(start..start.saturating_add(48)) else {
        return false;
    };
    let words = |entry: usize| -> Option<[u32; 4]> {
        let offset = entry * 16;
        Some([
            be32(entries, offset).ok()?,
            be32(entries, offset + 4).ok()?,
            be32(entries, offset + 8).ok()?,
            be32(entries, offset + 12).ok()?,
        ])
    };
    words(0) == Some([0, 0x1060, 0, 0])
        && words(1) == Some([0x1060, start as u32, 0x1060, 0])
        && words(2).is_some_and(|entry| {
            entry[0] == start as u32
                && entry[1] > entry[0]
                && entry[2] == start as u32
                && entry[3] == 0
        })
}

fn talon_source_from_dma_entry(rom: &[u8], entry: usize) -> Option<Vec<u8>> {
    let vrom_start = be32(rom, entry).ok()? as usize;
    let vrom_end = be32(rom, entry + 4).ok()? as usize;
    let rom_start = be32(rom, entry + 8).ok()? as usize;
    let rom_end = be32(rom, entry + 12).ok()? as usize;
    if vrom_start == 0 && vrom_end == 0 && rom_start == 0 && rom_end == 0 {
        return None;
    }
    if vrom_end < vrom_start {
        return None;
    }
    let expected = vrom_end - vrom_start;
    if !(TALON_PREFIX_SIZE..=MAX_OBJECT_SIZE).contains(&expected) {
        return None;
    }
    let object = if rom_end == 0 {
        rom.get(rom_start..rom_start.checked_add(expected)?)?
            .to_vec()
    } else {
        if rom_end < rom_start {
            return None;
        }
        let compressed = rom.get(rom_start..rom_end)?;
        if compressed.get(..4) != Some(b"Yaz0") {
            return None;
        }
        decompress_yaz0(compressed, expected).ok()?
    };
    validate_talon(&object).ok()?;
    let mut output = object[..TALON_PREFIX_SIZE].to_vec();
    for &(offset, length) in RGBA16_RANGES {
        if offset + length > output.len() || length % 2 != 0 {
            return None;
        }
        for cursor in (offset..offset + length).step_by(2) {
            let value = u16::from_be_bytes([output[cursor], output[cursor + 1]]);
            let red = (value >> 11) & 0x1F;
            let green = (value >> 6) & 0x1F;
            let blue = (value >> 1) & 0x1F;
            let alpha = value & 1;
            let gray = (red * 30 + green * 59 + blue * 11) / 100;
            output[cursor..cursor + 2]
                .copy_from_slice(&((gray << 11) | (gray << 6) | (gray << 1) | alpha).to_be_bytes());
        }
    }
    Some(output)
}

fn validate_talon(data: &[u8]) -> Result<()> {
    ensure!(
        data.len() >= TALON_PREFIX_SIZE,
        "OoT object_ta is truncated"
    );
    ensure!(
        be32(data, TALON_SKELETON_OFFSET)? == 0x0600_0000 + TALON_LIMB_TABLE_OFFSET as u32,
        "unexpected Talon skeleton pointer"
    );
    ensure!(
        data[TALON_SKELETON_OFFSET + 4] as usize == TALON_LIMB_COUNT,
        "unexpected Talon limb count"
    );
    ensure!(
        data[TALON_SKELETON_OFFSET + 8] == 15,
        "unexpected Talon display-list count"
    );
    for index in 0..TALON_LIMB_COUNT {
        ensure!(
            be32(data, TALON_LIMB_TABLE_OFFSET + index * 4)?
                == 0x0600_0000 + (TALON_LIMB_FIRST_OFFSET + index * 12) as u32,
            "unexpected Talon limb pointer"
        );
    }
    Ok(())
}

fn decompress_yaz0(input: &[u8], expected: usize) -> Result<Vec<u8>> {
    ensure!(
        input.get(..4) == Some(b"Yaz0"),
        "compressed OoT object_ta is not Yaz0"
    );
    let declared = be32(input, 4)? as usize;
    ensure!(declared == expected, "OoT object_ta Yaz0 size mismatch");
    let mut output = Vec::with_capacity(declared);
    let mut cursor = 16usize;
    while output.len() < declared {
        let code = *input
            .get(cursor)
            .context("truncated OoT object_ta Yaz0 code")?;
        cursor += 1;
        for bit in 0..8 {
            if output.len() == declared {
                break;
            }
            if code & (0x80 >> bit) != 0 {
                output.push(
                    *input
                        .get(cursor)
                        .context("truncated OoT object_ta Yaz0 literal")?,
                );
                cursor += 1;
            } else {
                let first = *input
                    .get(cursor)
                    .context("truncated OoT object_ta Yaz0 copy")?;
                let second = *input
                    .get(cursor + 1)
                    .context("truncated OoT object_ta Yaz0 copy")?;
                cursor += 2;
                let distance = ((((first as usize) & 0xF) << 8) | second as usize) + 1;
                let mut length = (first as usize) >> 4;
                if length == 0 {
                    length = *input
                        .get(cursor)
                        .context("truncated OoT object_ta Yaz0 length")?
                        as usize
                        + 0x12;
                    cursor += 1;
                } else {
                    length += 2;
                }
                ensure!(
                    distance <= output.len(),
                    "invalid OoT object_ta Yaz0 distance"
                );
                for _ in 0..length {
                    ensure!(
                        output.len() < declared,
                        "OoT object_ta Yaz0 output overflow"
                    );
                    output.push(output[output.len() - distance]);
                }
            }
        }
    }
    Ok(output)
}

fn be32(data: &[u8], offset: usize) -> Result<u32> {
    let bytes = data
        .get(offset..offset + 4)
        .context("OoT ROM is truncated")?;
    Ok(u32::from_be_bytes(bytes.try_into().unwrap()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn synthetic_rom(dmadata_start: usize, object_entry: usize) -> Vec<u8> {
        let object_offset = 0x10000usize;
        let mut rom = vec![0u8; object_offset + TALON_PREFIX_SIZE];
        rom[dmadata_start..dmadata_start + 16]
            .copy_from_slice(&[0, 0, 0, 0, 0, 0, 0x10, 0x60, 0, 0, 0, 0, 0, 0, 0, 0]);
        let boot = dmadata_start + 16;
        rom[boot..boot + 4].copy_from_slice(&0x1060u32.to_be_bytes());
        rom[boot + 4..boot + 8].copy_from_slice(&(dmadata_start as u32).to_be_bytes());
        rom[boot + 8..boot + 12].copy_from_slice(&0x1060u32.to_be_bytes());
        let table = dmadata_start + 32;
        rom[table..table + 4].copy_from_slice(&(dmadata_start as u32).to_be_bytes());
        rom[table + 4..table + 8].copy_from_slice(&(dmadata_start as u32 + 0x1000).to_be_bytes());
        rom[table + 8..table + 12].copy_from_slice(&(dmadata_start as u32).to_be_bytes());

        // Real DMA tables are contiguous until their terminator. Populate
        // harmless short entries so the Talon object can exercise an arbitrary
        // table slot without making the synthetic table malformed.
        for index in 3..object_entry {
            let entry = dmadata_start + index * 16;
            let vrom_start = 0x0100_0000u32 + index as u32 * 0x1000;
            rom[entry..entry + 4].copy_from_slice(&vrom_start.to_be_bytes());
            rom[entry + 4..entry + 8].copy_from_slice(&(vrom_start + 0x1000).to_be_bytes());
            rom[entry + 8..entry + 12].copy_from_slice(&0x2000u32.to_be_bytes());
        }

        let entry = dmadata_start + object_entry * 16;
        rom[entry..entry + 4].copy_from_slice(&0x0200_0000u32.to_be_bytes());
        rom[entry + 4..entry + 8]
            .copy_from_slice(&(0x0200_0000u32 + TALON_PREFIX_SIZE as u32).to_be_bytes());
        rom[entry + 8..entry + 12].copy_from_slice(&(object_offset as u32).to_be_bytes());
        for index in 0..TALON_LIMB_COUNT {
            let pointer = 0x0600_0000 + (TALON_LIMB_FIRST_OFFSET + index * 12) as u32;
            let offset = object_offset + TALON_LIMB_TABLE_OFFSET + index * 4;
            rom[offset..offset + 4].copy_from_slice(&pointer.to_be_bytes());
        }
        let skeleton = object_offset + TALON_SKELETON_OFFSET;
        rom[skeleton..skeleton + 4]
            .copy_from_slice(&(0x0600_0000 + TALON_LIMB_TABLE_OFFSET as u32).to_be_bytes());
        rom[skeleton + 4] = TALON_LIMB_COUNT as u8;
        rom[skeleton + 8] = 15;
        let pixel = object_offset + RGBA16_RANGES[0].0;
        rom[pixel..pixel + 2].copy_from_slice(&0xF801u16.to_be_bytes());

        rom
    }

    fn assert_extracts_talon(rom: &[u8]) {
        let source = stone_talon_source(rom).unwrap();
        assert_eq!(source.len(), TALON_PREFIX_SIZE);
        assert_eq!(
            u16::from_be_bytes(
                source[RGBA16_RANGES[0].0..RGBA16_RANGES[0].0 + 2]
                    .try_into()
                    .unwrap()
            ),
            0x4A53
        );
    }

    #[test]
    fn derives_talon_from_each_known_ntsc_dmadata_location() {
        for start in [0x7430, 0x7960] {
            assert_extracts_talon(&synthetic_rom(start, 37));
        }
    }

    #[test]
    fn later_revision_boot_data_cannot_end_the_scan_before_dmadata() {
        let mut rom = synthetic_rom(0x7960, 37);
        rom[0x7430..0x7440].fill(0xA5);
        rom[0x7440..0x7450].fill(0);
        assert_extracts_talon(&rom);
    }

    #[test]
    fn structurally_finds_an_unlisted_dmadata_location() {
        assert_extracts_talon(&synthetic_rom(0x9AB0, 37));
    }

    #[test]
    fn rejects_an_unstructured_early_rom_region() {
        let mut rom = synthetic_rom(0x7960, 37);
        rom[0x7430..0x7440].fill(0xA5);
        assert!(!is_dmadata_start(&rom, 0x7430));
    }
}
