use anyhow::{bail, ensure, Context, Result};
use flate2::read::GzDecoder;
use sha1::{Digest, Sha1};
use std::fs;
use std::io::{Cursor, Read, Write};
use std::path::{Path, PathBuf};

const MAX_INPUT_SIZE: usize = 128 * 1024 * 1024;
const DMADATA_START: usize = 0x1A500;
const SM64_SHA1: &str = "9bef1128717f958171a4afac3ed78ee2bb4e86ce";
const MM_COMPRESSED_SHA1: &str = "d6133ace5afaa0882cf214cf88daba39e266c078";
const MM_DECOMPRESSED_SHA1: &str = "7f5630dbc4d5d61d6276213210c4d5cdd83a47d6";
const OUTPUT_SHA1: &str = "682829e76147ac90f105c38ab137b4a4eb65d1e4";
const PATCH: &[u8] = include_bytes!("../recipe/marios-mask-alpha3.mm2p");

#[derive(Clone, Copy, Debug)]
struct DmaEntry {
    vrom_start: u32,
    vrom_end: u32,
    rom_start: u32,
    rom_end: u32,
}

impl DmaEntry {
    fn from_bytes(bytes: &[u8]) -> Result<Self> {
        ensure!(bytes.len() >= 16, "truncated Majora's Mask DMA table");
        Ok(Self {
            vrom_start: be32(bytes, 0)?,
            vrom_end: be32(bytes, 4)?,
            rom_start: be32(bytes, 8)?,
            rom_end: be32(bytes, 12)?,
        })
    }

    fn is_end(self) -> bool {
        self.vrom_start == 0 && self.vrom_end == 0 && self.rom_start == 0 && self.rom_end == 0
    }

    fn is_syms(self) -> bool {
        self.rom_start == u32::MAX && self.rom_end == u32::MAX
    }

    fn write(self, output: &mut [u8], offset: usize) -> Result<()> {
        ensure!(
            offset + 16 <= output.len(),
            "Majora's Mask DMA table exceeds the ROM"
        );
        for (index, value) in [self.vrom_start, self.vrom_end, self.rom_start, self.rom_end]
            .iter()
            .enumerate()
        {
            output[offset + index * 4..offset + index * 4 + 4]
                .copy_from_slice(&value.to_be_bytes());
        }
        Ok(())
    }
}

pub fn build_from_paths<F>(
    sm64_path: &Path,
    mm_path: &Path,
    output_path: &Path,
    mut progress: F,
) -> Result<()>
where
    F: FnMut(&str),
{
    ensure!(sm64_path != mm_path, "Choose two different ROM files.");
    ensure!(
        output_path != sm64_path && output_path != mm_path,
        "The output cannot overwrite either input ROM."
    );

    progress("Reading Super Mario 64…");
    let sm64 = read_and_normalize(sm64_path).context("Could not read the Super Mario 64 ROM")?;
    ensure_sha1(&sm64, SM64_SHA1, "Super Mario 64 US")?;

    progress("Reading Majora's Mask…");
    let mm_input = read_and_normalize(mm_path).context("Could not read the Majora's Mask ROM")?;
    let mm_hash = sha1_hex(&mm_input);
    let mm = if mm_hash == MM_DECOMPRESSED_SHA1 {
        mm_input
    } else if mm_hash == MM_COMPRESSED_SHA1 {
        progress("Decompressing Majora's Mask…");
        decompress_mm(&mm_input)?
    } else {
        bail!("Majora's Mask must be the NTSC-US revision (compressed or decompressed). Found SHA-1 {mm_hash}");
    };
    ensure_sha1(&mm, MM_DECOMPRESSED_SHA1, "decompressed Majora's Mask US")?;

    progress("Combining both ROMs…");
    let mut dictionary = mm;
    dictionary.reserve(sm64.len());
    dictionary.extend_from_slice(&sm64);
    drop(sm64);

    let mut decoder = zstd::stream::read::Decoder::with_ref_prefix(Cursor::new(PATCH), &dictionary)
        .context("The embedded two-ROM recipe is damaged")?;
    let mut output = Vec::with_capacity(52_297_728);
    decoder
        .read_to_end(&mut output)
        .context("Could not apply the embedded two-ROM recipe")?;
    ensure_sha1(&output, OUTPUT_SHA1, "Mario's Mask output")?;

    progress("Writing Mario's Mask…");
    write_atomic(output_path, &output)?;
    progress("Done!");
    Ok(())
}

fn write_atomic(path: &Path, data: &[u8]) -> Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent).with_context(|| format!("Could not create {}", parent.display()))?;
    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("MariosMask.z64");
    let temporary: PathBuf = parent.join(format!(".{name}.{}.tmp", std::process::id()));
    let result = (|| -> Result<()> {
        let mut file = fs::File::create(&temporary)
            .with_context(|| format!("Could not create {}", temporary.display()))?;
        file.write_all(data)?;
        file.sync_all()?;
        fs::rename(&temporary, path)
            .with_context(|| format!("Could not save {}", path.display()))?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

fn read_and_normalize(path: &Path) -> Result<Vec<u8>> {
    let data = fs::read(path).with_context(|| format!("Could not read {}", path.display()))?;
    ensure!(
        data.len() <= MAX_INPUT_SIZE,
        "{} is too large to be a ROM",
        path.display()
    );
    let unpacked = if data.starts_with(b"PK\x03\x04") {
        read_zip(&data)?
    } else if data.starts_with(b"\x1F\x8B\x08") {
        read_limited(GzDecoder::new(Cursor::new(data)), "gzip ROM")?
    } else {
        data
    };
    normalize_byte_order(unpacked)
}

fn read_zip(data: &[u8]) -> Result<Vec<u8>> {
    let mut archive = zip::ZipArchive::new(Cursor::new(data)).context("Invalid ZIP file")?;
    let files: Vec<usize> = (0..archive.len())
        .filter(|index| {
            archive
                .by_index(*index)
                .map(|entry| !entry.is_dir())
                .unwrap_or(false)
        })
        .collect();
    let roms: Vec<usize> = files
        .iter()
        .copied()
        .filter(|index| {
            archive
                .by_index(*index)
                .ok()
                .and_then(|entry| {
                    Path::new(entry.name())
                        .extension()
                        .map(|value| value.to_ascii_lowercase())
                })
                .is_some_and(|extension| {
                    matches!(extension.to_str(), Some("z64" | "v64" | "n64" | "rom"))
                })
        })
        .collect();
    let candidates = if roms.is_empty() { &files } else { &roms };
    ensure!(
        candidates.len() == 1,
        "ZIP files must contain exactly one ROM"
    );
    let entry = archive
        .by_index(candidates[0])
        .context("Could not read the ROM inside the ZIP")?;
    read_limited(entry, "ZIP ROM")
}

fn read_limited<R: Read>(reader: R, label: &str) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    reader
        .take((MAX_INPUT_SIZE + 1) as u64)
        .read_to_end(&mut output)
        .with_context(|| format!("Could not decompress {label}"))?;
    ensure!(output.len() <= MAX_INPUT_SIZE, "{label} is too large");
    Ok(output)
}

fn normalize_byte_order(mut data: Vec<u8>) -> Result<Vec<u8>> {
    ensure!(data.len() >= 4, "ROM is truncated");
    match &data[..4] {
        b"\x80\x37\x12\x40" => {}
        b"\x37\x80\x40\x12" => {
            ensure!(data.len() % 2 == 0, "byte-swapped ROM has an odd size");
            for pair in data.chunks_exact_mut(2) {
                pair.swap(0, 1);
            }
        }
        b"\x40\x12\x37\x80" => {
            ensure!(data.len() % 4 == 0, "little-endian ROM has a non-word size");
            for word in data.chunks_exact_mut(4) {
                word.reverse();
            }
        }
        _ => bail!("Not a recognised N64 ROM"),
    }
    Ok(data)
}

fn decompress_mm(input: &[u8]) -> Result<Vec<u8>> {
    ensure!(
        input.len() > DMADATA_START + 16,
        "Majora's Mask ROM is truncated"
    );
    let mut entries = Vec::new();
    for index in 0..4096usize {
        let offset = DMADATA_START + index * 16;
        ensure!(
            offset + 16 <= input.len(),
            "Majora's Mask DMA table has no terminator"
        );
        let entry = DmaEntry::from_bytes(&input[offset..offset + 16])?;
        if entry.is_end() {
            break;
        }
        ensure!(
            entry.vrom_start <= entry.vrom_end,
            "Majora's Mask DMA entry is reversed"
        );
        entries.push(entry);
    }
    ensure!(!entries.is_empty(), "Majora's Mask DMA table is empty");
    let last_vrom = entries.last().unwrap().vrom_end as usize;
    let output_len = round_up(last_vrom, 17);
    ensure!(
        output_len <= MAX_INPUT_SIZE,
        "decompressed Majora's Mask ROM is implausibly large"
    );
    let mut output = vec![0u8; output_len];

    for entry in &entries {
        if entry.is_syms() {
            continue;
        }
        let vstart = entry.vrom_start as usize;
        let vend = entry.vrom_end as usize;
        ensure!(
            vend <= output.len(),
            "Majora's Mask virtual segment exceeds the ROM"
        );
        let segment = if entry.rom_end != 0 {
            let start = entry.rom_start as usize;
            let end = entry.rom_end as usize;
            ensure!(
                start < end && end <= input.len(),
                "Majora's Mask compressed segment exceeds the ROM"
            );
            yaz0_decompress(&input[start..end])?
        } else {
            let start = entry.rom_start as usize;
            let end = start
                .checked_add(vend - vstart)
                .context("Majora's Mask segment overflow")?;
            ensure!(end <= input.len(), "Majora's Mask segment exceeds the ROM");
            input[start..end].to_vec()
        };
        ensure!(
            segment.len() == vend - vstart,
            "Majora's Mask segment decompressed to the wrong size"
        );
        output[vstart..vend].copy_from_slice(&segment);
    }

    for (index, entry) in entries.iter().enumerate() {
        let rewritten = if entry.is_syms() {
            *entry
        } else {
            DmaEntry {
                vrom_start: entry.vrom_start,
                vrom_end: entry.vrom_end,
                rom_start: entry.vrom_start,
                rom_end: 0,
            }
        };
        rewritten.write(&mut output, DMADATA_START + index * 16)?;
    }
    output[DMADATA_START + entries.len() * 16..DMADATA_START + entries.len() * 16 + 16].fill(0);
    output[round_up(last_vrom, 12)..output_len].fill(0xFF);
    update_x105_checksum(&mut output)?;
    Ok(output)
}

fn yaz0_decompress(input: &[u8]) -> Result<Vec<u8>> {
    ensure!(
        input.len() >= 16 && &input[..4] == b"Yaz0",
        "Invalid Yaz0 segment"
    );
    let expected = be32(input, 4)? as usize;
    ensure!(expected <= MAX_INPUT_SIZE, "Yaz0 segment is too large");
    let mut output = Vec::with_capacity(expected);
    let mut source = 16usize;
    let mut code = 0u8;
    let mut bits = 0u8;
    while output.len() < expected {
        if bits == 0 {
            ensure!(source < input.len(), "truncated Yaz0 control stream");
            code = input[source];
            source += 1;
            bits = 8;
        }
        if code & 0x80 != 0 {
            ensure!(source < input.len(), "truncated Yaz0 literal");
            output.push(input[source]);
            source += 1;
        } else {
            ensure!(source + 2 <= input.len(), "truncated Yaz0 back-reference");
            let first = input[source];
            let second = input[source + 1];
            source += 2;
            let distance = (((first as usize & 0x0F) << 8) | second as usize) + 1;
            ensure!(distance <= output.len(), "invalid Yaz0 back-reference");
            let mut length = (first >> 4) as usize;
            if length == 0 {
                ensure!(source < input.len(), "truncated Yaz0 long back-reference");
                length = input[source] as usize + 0x12;
                source += 1;
            } else {
                length += 2;
            }
            for _ in 0..length.min(expected - output.len()) {
                let value = output[output.len() - distance];
                output.push(value);
            }
        }
        code <<= 1;
        bits -= 1;
    }
    Ok(output)
}

fn update_x105_checksum(rom: &mut [u8]) -> Result<()> {
    ensure!(
        rom.len() >= 0x101000,
        "ROM is too small for its N64 checksum"
    );
    let mut t1 = 0xDF26_F436u32;
    let mut t2 = t1;
    let mut t3 = t1;
    let mut t4 = t1;
    let mut t5 = t1;
    let mut t6 = t1;
    for offset in (0x1000..0x101000).step_by(4) {
        let value = be32(rom, offset)?;
        let sum = t6.wrapping_add(value);
        if sum < t6 {
            t4 = t4.wrapping_add(1);
        }
        t6 = sum;
        t3 ^= value;
        let rotated = value.rotate_left(value & 31);
        t5 = t5.wrapping_add(rotated);
        if t2 > value {
            t2 ^= rotated;
        } else {
            t2 ^= t6 ^ value;
        }
        let boot = be32(rom, 0x750 + (offset & 0xFF))?;
        t1 = t1.wrapping_add(boot ^ value);
    }
    rom[0x10..0x14].copy_from_slice(&(t6 ^ t4 ^ t3).to_be_bytes());
    rom[0x14..0x18].copy_from_slice(&(t5 ^ t2 ^ t1).to_be_bytes());
    Ok(())
}

fn be32(data: &[u8], offset: usize) -> Result<u32> {
    let bytes: [u8; 4] = data
        .get(offset..offset + 4)
        .context("truncated big-endian word")?
        .try_into()
        .unwrap();
    Ok(u32::from_be_bytes(bytes))
}

fn round_up(value: usize, shift: u32) -> usize {
    let alignment = 1usize << shift;
    (value + alignment - 1) & !(alignment - 1)
}

fn sha1_hex(data: &[u8]) -> String {
    format!("{:x}", Sha1::digest(data))
}

fn ensure_sha1(data: &[u8], expected: &str, label: &str) -> Result<()> {
    let actual = sha1_hex(data);
    ensure!(
        actual == expected,
        "{label} has the wrong revision (SHA-1 {actual})"
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_all_n64_byte_orders() {
        let canonical = vec![0x80, 0x37, 0x12, 0x40, 1, 2, 3, 4];
        let v64 = vec![0x37, 0x80, 0x40, 0x12, 2, 1, 4, 3];
        let n64 = vec![0x40, 0x12, 0x37, 0x80, 4, 3, 2, 1];
        assert_eq!(normalize_byte_order(canonical.clone()).unwrap(), canonical);
        assert_eq!(normalize_byte_order(v64).unwrap(), canonical);
        assert_eq!(normalize_byte_order(n64).unwrap(), canonical);
    }

    #[test]
    fn decompresses_yaz0_literals_and_overlapping_copy() {
        let mut encoded = b"Yaz0\0\0\0\x08\0\0\0\0\0\0\0\0".to_vec();
        encoded.extend_from_slice(&[0xE0, b'A', b'B', b'C', 0x30, 0x02]);
        assert_eq!(yaz0_decompress(&encoded).unwrap(), b"ABCABCAB");
    }

    #[test]
    fn zip_selects_the_only_rom_and_ignores_readme() {
        let destination = Cursor::new(Vec::new());
        let mut writer = zip::ZipWriter::new(destination);
        let options = zip::write::SimpleFileOptions::default();
        writer.start_file("README.txt", options).unwrap();
        writer.write_all(b"not a ROM").unwrap();
        writer.start_file("game.z64", options).unwrap();
        writer.write_all(b"\x80\x37\x12\x40rom bytes").unwrap();
        let archive = writer.finish().unwrap().into_inner();
        assert_eq!(read_zip(&archive).unwrap(), b"\x80\x37\x12\x40rom bytes");
    }
}
