use anyhow::{bail, ensure, Context, Result};
use sha2::{Digest, Sha256};
use std::fmt::Write as _;

pub const MAGIC: &[u8; 8] = b"MMRECP02";
const HEADER_SIZE: usize = 8 + 8 + 32 + 32 + 32 + 32 + 4;
const COPY_MM: u8 = 0;
const COPY_SM64: u8 = 1;
const LITERAL: u8 = 2;
const COPY_OUTPUT: u8 = 3;
const COPY_OOT: u8 = 4;
const MAX_COMMANDS: usize = 8_000_000;
const MAX_OUTPUT_SIZE: usize = 128 * 1024 * 1024;

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RecipeStats {
    pub commands: usize,
    pub output_bytes: usize,
    pub mm_bytes: usize,
    pub sm64_bytes: usize,
    pub oot_bytes: usize,
    pub literal_origin_bytes: usize,
    pub stored_literal_bytes: usize,
    pub output_copy_bytes: usize,
    pub literal_payload_sha256: String,
    pub literal_ranges: Vec<LiteralRange>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LiteralRange {
    pub output_offset: usize,
    pub length: usize,
    pub sha256: String,
}

impl RecipeStats {
    pub fn source_bytes(&self) -> usize {
        self.mm_bytes + self.sm64_bytes + self.oot_bytes
    }

    pub fn source_percent(&self) -> f64 {
        if self.output_bytes == 0 {
            0.0
        } else {
            100.0 * self.source_bytes() as f64 / self.output_bytes as f64
        }
    }

    pub fn report(&self) -> String {
        format!(
            "commands: {}\noutput bytes: {}\nMM-origin bytes: {}\nSM64-origin bytes: {}\nOoT-origin bytes: {}\nliteral-origin bytes: {}\nstored literal bytes: {}\noutput-copy bytes: {}\nliteral payload SHA-256: {}\ninput-derived: {:.4}%\n",
            self.commands,
            self.output_bytes,
            self.mm_bytes,
            self.sm64_bytes,
            self.oot_bytes,
            self.literal_origin_bytes,
            self.stored_literal_bytes,
            self.output_copy_bytes,
            self.literal_payload_sha256,
            self.source_percent(),
        )
    }

    pub fn literal_report(&self) -> String {
        let mut report = String::new();
        for literal in &self.literal_ranges {
            let _ = writeln!(
                report,
                "literal 0x{:08X} {} {}",
                literal.output_offset, literal.length, literal.sha256
            );
        }
        report
    }
}

pub fn apply(
    recipe: &[u8],
    mm: &[u8],
    sm64: &[u8],
    oot: &[u8],
    oot_source: &[u8],
) -> Result<(Vec<u8>, RecipeStats)> {
    let header = Header::parse(recipe)?;
    header.validate_inputs(mm, sm64, oot)?;
    let mut cursor = HEADER_SIZE;
    let mut output = Vec::with_capacity(header.output_size);
    let mut origins = Vec::with_capacity(header.output_size);
    let mut literal_payload_hasher = Sha256::new();
    let mut stats = RecipeStats {
        commands: header.command_count,
        output_bytes: header.output_size,
        ..RecipeStats::default()
    };

    for command_index in 0..header.command_count {
        let kind = take_u8(recipe, &mut cursor)
            .with_context(|| format!("recipe command {command_index} has no opcode"))?;
        match kind {
            COPY_MM | COPY_SM64 | COPY_OOT => {
                let offset = take_u32(recipe, &mut cursor)? as usize;
                let length = take_u32(recipe, &mut cursor)? as usize;
                ensure!(
                    length > 0,
                    "recipe command {command_index} is an empty copy"
                );
                let source = match kind {
                    COPY_MM => mm,
                    COPY_SM64 => sm64,
                    COPY_OOT => oot_source,
                    _ => unreachable!(),
                };
                let end = offset
                    .checked_add(length)
                    .context("recipe copy range overflows")?;
                let bytes = source
                    .get(offset..end)
                    .with_context(|| format!("recipe command {command_index} exceeds its input"))?;
                output.extend_from_slice(bytes);
                if kind == COPY_MM {
                    stats.mm_bytes += length;
                    origins.resize(origins.len() + length, COPY_MM);
                } else if kind == COPY_SM64 {
                    stats.sm64_bytes += length;
                    origins.resize(origins.len() + length, COPY_SM64);
                } else {
                    stats.oot_bytes += length;
                    origins.resize(origins.len() + length, COPY_OOT);
                }
            }
            LITERAL => {
                let length = take_u32(recipe, &mut cursor)? as usize;
                ensure!(
                    length > 0,
                    "recipe command {command_index} is an empty literal"
                );
                let end = cursor
                    .checked_add(length)
                    .context("recipe literal range overflows")?;
                let bytes = recipe
                    .get(cursor..end)
                    .with_context(|| format!("recipe command {command_index} is truncated"))?;
                stats.literal_ranges.push(LiteralRange {
                    output_offset: output.len(),
                    length,
                    sha256: sha256_hex(bytes),
                });
                stats.literal_origin_bytes += length;
                stats.stored_literal_bytes += length;
                literal_payload_hasher.update(bytes);
                output.extend_from_slice(bytes);
                origins.resize(origins.len() + length, LITERAL);
                cursor = end;
            }
            COPY_OUTPUT => {
                let offset = take_u32(recipe, &mut cursor)? as usize;
                let length = take_u32(recipe, &mut cursor)? as usize;
                ensure!(
                    length > 0,
                    "recipe command {command_index} is an empty output copy"
                );
                ensure!(
                    offset < output.len(),
                    "recipe command {command_index} references unwritten output"
                );
                ensure!(
                    output.len().saturating_add(length) <= header.output_size,
                    "recipe writes beyond its declared output size"
                );
                for relative in 0..length {
                    let source = offset
                        .checked_add(relative)
                        .context("recipe output-copy range overflows")?;
                    ensure!(
                        source < output.len(),
                        "recipe command {command_index} references unwritten output"
                    );
                    let origin = origins[source];
                    output.push(output[source]);
                    origins.push(origin);
                    match origin {
                        COPY_MM => stats.mm_bytes += 1,
                        COPY_SM64 => stats.sm64_bytes += 1,
                        COPY_OOT => stats.oot_bytes += 1,
                        LITERAL => stats.literal_origin_bytes += 1,
                        _ => unreachable!("validated origin tag"),
                    }
                }
                stats.output_copy_bytes += length;
            }
            _ => bail!("recipe command {command_index} has unknown opcode {kind}"),
        }
        ensure!(
            output.len() <= header.output_size,
            "recipe writes beyond its declared output size"
        );
    }

    ensure!(cursor == recipe.len(), "recipe has trailing bytes");
    ensure!(
        output.len() == header.output_size,
        "recipe produced {} bytes; expected {}",
        output.len(),
        header.output_size
    );
    ensure!(
        Sha256::digest(&output).as_slice() == header.output_sha256,
        "recipe output SHA-256 does not match its manifest"
    );
    stats.literal_payload_sha256 = format!("{:x}", literal_payload_hasher.finalize());
    Ok((output, stats))
}

#[derive(Clone, Debug)]
pub enum Command {
    CopyMm { offset: u32, length: u32 },
    CopySm64 { offset: u32, length: u32 },
    CopyOot { offset: u32, length: u32 },
    CopyOutput { offset: u32, length: u32 },
    Literal(Vec<u8>),
}

impl Command {
    fn output_length(&self) -> usize {
        match self {
            Self::CopyMm { length, .. }
            | Self::CopySm64 { length, .. }
            | Self::CopyOot { length, .. }
            | Self::CopyOutput { length, .. } => *length as usize,
            Self::Literal(bytes) => bytes.len(),
        }
    }
}

pub fn encode(
    mm: &[u8],
    sm64: &[u8],
    oot: &[u8],
    output: &[u8],
    commands: &[Command],
) -> Result<Vec<u8>> {
    ensure!(
        output.len() <= MAX_OUTPUT_SIZE,
        "output exceeds the recipe size limit"
    );
    ensure!(
        commands.len() <= MAX_COMMANDS,
        "recipe has too many commands"
    );
    let described_size: usize = commands.iter().map(Command::output_length).sum();
    ensure!(
        described_size == output.len(),
        "commands describe {described_size} bytes; output has {}",
        output.len()
    );

    let literal_size: usize = commands
        .iter()
        .filter_map(|command| match command {
            Command::Literal(bytes) => Some(bytes.len()),
            _ => None,
        })
        .sum();
    let mut recipe = Vec::with_capacity(HEADER_SIZE + commands.len() * 9 + literal_size);
    recipe.extend_from_slice(MAGIC);
    recipe.extend_from_slice(&(output.len() as u64).to_le_bytes());
    recipe.extend_from_slice(&Sha256::digest(mm));
    recipe.extend_from_slice(&Sha256::digest(sm64));
    recipe.extend_from_slice(&Sha256::digest(oot));
    recipe.extend_from_slice(&Sha256::digest(output));
    recipe.extend_from_slice(&(commands.len() as u32).to_le_bytes());

    for command in commands {
        match command {
            Command::CopyMm { offset, length } => {
                recipe.push(COPY_MM);
                recipe.extend_from_slice(&offset.to_le_bytes());
                recipe.extend_from_slice(&length.to_le_bytes());
            }
            Command::CopySm64 { offset, length } => {
                recipe.push(COPY_SM64);
                recipe.extend_from_slice(&offset.to_le_bytes());
                recipe.extend_from_slice(&length.to_le_bytes());
            }
            Command::CopyOot { offset, length } => {
                recipe.push(COPY_OOT);
                recipe.extend_from_slice(&offset.to_le_bytes());
                recipe.extend_from_slice(&length.to_le_bytes());
            }
            Command::CopyOutput { offset, length } => {
                recipe.push(COPY_OUTPUT);
                recipe.extend_from_slice(&offset.to_le_bytes());
                recipe.extend_from_slice(&length.to_le_bytes());
            }
            Command::Literal(bytes) => {
                ensure!(
                    bytes.len() <= u32::MAX as usize,
                    "literal exceeds the format limit"
                );
                recipe.push(LITERAL);
                recipe.extend_from_slice(&(bytes.len() as u32).to_le_bytes());
                recipe.extend_from_slice(bytes);
            }
        }
    }
    Ok(recipe)
}

struct Header {
    output_size: usize,
    mm_sha256: [u8; 32],
    sm64_sha256: [u8; 32],
    oot_sha256: [u8; 32],
    output_sha256: [u8; 32],
    command_count: usize,
}

impl Header {
    fn parse(recipe: &[u8]) -> Result<Self> {
        ensure!(recipe.len() >= HEADER_SIZE, "recipe header is truncated");
        ensure!(&recipe[..8] == MAGIC, "recipe magic/version is unsupported");
        let output_size = u64::from_le_bytes(recipe[8..16].try_into().unwrap()) as usize;
        ensure!(
            output_size <= MAX_OUTPUT_SIZE,
            "recipe output exceeds the size limit"
        );
        let command_count = u32::from_le_bytes(recipe[144..148].try_into().unwrap()) as usize;
        ensure!(
            command_count <= MAX_COMMANDS,
            "recipe command count exceeds the limit"
        );
        Ok(Self {
            output_size,
            mm_sha256: recipe[16..48].try_into().unwrap(),
            sm64_sha256: recipe[48..80].try_into().unwrap(),
            oot_sha256: recipe[80..112].try_into().unwrap(),
            output_sha256: recipe[112..144].try_into().unwrap(),
            command_count,
        })
    }

    fn validate_inputs(&self, mm: &[u8], sm64: &[u8], oot: &[u8]) -> Result<()> {
        ensure!(
            Sha256::digest(mm).as_slice() == self.mm_sha256,
            "Majora's Mask SHA-256 does not match the recipe"
        );
        ensure!(
            Sha256::digest(sm64).as_slice() == self.sm64_sha256,
            "Super Mario 64 SHA-256 does not match the recipe"
        );
        ensure!(
            Sha256::digest(oot).as_slice() == self.oot_sha256,
            "Ocarina of Time SHA-256 does not match the recipe"
        );
        Ok(())
    }
}

fn take_u8(data: &[u8], cursor: &mut usize) -> Result<u8> {
    let value = *data.get(*cursor).context("truncated recipe")?;
    *cursor += 1;
    Ok(value)
}

fn take_u32(data: &[u8], cursor: &mut usize) -> Result<u32> {
    let end = cursor.checked_add(4).context("recipe cursor overflows")?;
    let bytes = data.get(*cursor..end).context("truncated recipe word")?;
    *cursor = end;
    Ok(u32::from_le_bytes(bytes.try_into().unwrap()))
}

fn sha256_hex(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn applies_and_reports_each_byte_class() {
        let mm = b"abcdefgh";
        let sm64 = b"01234567";
        let oot = b"oot-rom";
        let output = b"abc123!gh";
        let commands = vec![
            Command::CopyMm {
                offset: 0,
                length: 3,
            },
            Command::CopySm64 {
                offset: 1,
                length: 3,
            },
            Command::Literal(vec![b'!']),
            Command::CopyMm {
                offset: 6,
                length: 2,
            },
        ];
        let encoded = encode(mm, sm64, oot, output, &commands).unwrap();
        let (actual, stats) = apply(&encoded, mm, sm64, oot, b"").unwrap();
        assert_eq!(actual, output);
        assert_eq!(stats.mm_bytes, 5);
        assert_eq!(stats.sm64_bytes, 3);
        assert_eq!(stats.literal_origin_bytes, 1);
        assert_eq!(stats.stored_literal_bytes, 1);
        assert_eq!(stats.output_bytes, output.len());
    }

    #[test]
    fn output_copies_preserve_transitive_origins() {
        let mm = b"abcdefgh";
        let sm64 = b"01234567";
        let oot = b"oot-rom";
        let output = b"ab!ab!ab!";
        let commands = vec![
            Command::CopyMm {
                offset: 0,
                length: 2,
            },
            Command::Literal(vec![b'!']),
            Command::CopyOutput {
                offset: 0,
                length: 6,
            },
        ];
        let encoded = encode(mm, sm64, oot, output, &commands).unwrap();
        let (actual, stats) = apply(&encoded, mm, sm64, oot, b"").unwrap();
        assert_eq!(actual, output);
        assert_eq!(stats.mm_bytes, 6);
        assert_eq!(stats.literal_origin_bytes, 3);
        assert_eq!(stats.stored_literal_bytes, 1);
        assert_eq!(stats.output_copy_bytes, 6);
    }

    #[test]
    fn rejects_trailing_bytes() {
        let mm = b"abcdefgh";
        let sm64 = b"01234567";
        let oot = b"oot-rom";
        let output = b"abc";
        let mut encoded = encode(
            mm,
            sm64,
            oot,
            output,
            &[Command::CopyMm {
                offset: 0,
                length: 3,
            }],
        )
        .unwrap();
        encoded.push(0);
        assert!(apply(&encoded, mm, sm64, oot, b"")
            .unwrap_err()
            .to_string()
            .contains("trailing"));
    }
}
