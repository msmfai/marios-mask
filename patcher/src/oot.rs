use anyhow::{ensure, Context, Result};

const DMADATA_START: usize = 0x7430;
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
    let mut table_started = false;
    for index in 0..MAX_DMA_ENTRIES {
        let entry = DMADATA_START + index * 16;
        if entry + 16 > rom.len() {
            break;
        }
        let empty = rom[entry..entry + 16].iter().all(|byte| *byte == 0);
        if empty {
            if table_started {
                break;
            }
            continue;
        }
        table_started = true;
        if let Some(source) = talon_source_from_dma_entry(rom, entry) {
            ensure!(
                match_source.is_none(),
                "OoT contains more than one Talon object"
            );
            match_source = Some(source);
        }
    }
    match_source.context("could not find a compatible Talon object in this Ocarina of Time ROM")
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

    #[test]
    fn derives_and_grayscales_talon_from_the_oot_dma_entry() {
        let object_offset = 0x10000usize;
        let mut rom = vec![0u8; object_offset + TALON_PREFIX_SIZE];
        // Deliberately use an arbitrary slot: retail revisions do not need to
        // keep object_ta at one hard-coded DMA index.
        let entry = DMADATA_START + 37 * 16;
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

        let source = stone_talon_source(&rom).unwrap();
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
}
