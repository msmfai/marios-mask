use anyhow::{bail, ensure, Context, Result};
use marios_mask_builder::recipe::{self, Command};
use std::fs;
use std::path::Path;

const MIN_MATCH: usize = 8;
const BUCKET_BITS: usize = 24;
const BUCKET_COUNT: usize = 1 << BUCKET_BITS;
const EMPTY: u32 = u32::MAX;
const MAX_CANDIDATES: usize = 64;

fn main() {
    if let Err(error) = run() {
        eprintln!("Error: {error:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let arguments: Vec<String> = std::env::args().collect();
    match arguments.as_slice() {
        [_, command, sm64_path, mm_path, output_path, recipe_path] if command == "create" => {
            create(
                Path::new(sm64_path),
                Path::new(mm_path),
                Path::new(output_path),
                Path::new(recipe_path),
            )
        }
        [_, command, sm64_path, mm_path, recipe_path] if command == "verify" => {
            verify(
                Path::new(sm64_path),
                Path::new(mm_path),
                Path::new(recipe_path),
            )
        }
        _ => bail!(
            "usage:\n  {} create <sm64.z64> <decompressed-mm.z64> <output.z64> <recipe.mmrecipe>\n  {} verify <sm64.z64> <decompressed-mm.z64> <recipe.mmrecipe>",
            arguments.first().map(String::as_str).unwrap_or("marios-mask-recipe"),
            arguments.first().map(String::as_str).unwrap_or("marios-mask-recipe"),
        ),
    }
}

fn create(sm64_path: &Path, mm_path: &Path, output_path: &Path, recipe_path: &Path) -> Result<()> {
    let sm64 =
        fs::read(sm64_path).with_context(|| format!("could not read {}", sm64_path.display()))?;
    let mm = fs::read(mm_path).with_context(|| format!("could not read {}", mm_path.display()))?;
    let output = fs::read(output_path)
        .with_context(|| format!("could not read {}", output_path.display()))?;
    ensure!(
        mm.len() + sm64.len() < u32::MAX as usize,
        "combined inputs exceed the recipe offset limit"
    );

    eprintln!(
        "Indexing {} input bytes with {} buckets…",
        mm.len() + sm64.len(),
        BUCKET_COUNT
    );
    let mut index = SourceIndex::new(&mm, &sm64);
    eprintln!("Matching {} output bytes…", output.len());
    let commands = index.commands_for(&output);
    let encoded = recipe::encode(&mm, &sm64, &output, &commands)?;
    let parent = recipe_path.parent().unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent)?;
    fs::write(recipe_path, &encoded)
        .with_context(|| format!("could not write {}", recipe_path.display()))?;
    let (_, stats) = recipe::apply(&encoded, &mm, &sm64)?;
    print!("{}", stats.report());
    println!("recipe bytes: {}", encoded.len());
    Ok(())
}

fn verify(sm64_path: &Path, mm_path: &Path, recipe_path: &Path) -> Result<()> {
    let sm64 =
        fs::read(sm64_path).with_context(|| format!("could not read {}", sm64_path.display()))?;
    let mm = fs::read(mm_path).with_context(|| format!("could not read {}", mm_path.display()))?;
    let encoded = fs::read(recipe_path)
        .with_context(|| format!("could not read {}", recipe_path.display()))?;
    let (_, stats) = recipe::apply(&encoded, &mm, &sm64)?;
    print!("{}", stats.report());
    println!("recipe bytes: {}", encoded.len());
    Ok(())
}

struct SourceIndex<'a> {
    mm: &'a [u8],
    sm64: &'a [u8],
    input_heads: Vec<u32>,
    input_next: Vec<u32>,
    output_heads: Vec<u32>,
    output_next: Vec<u32>,
}

impl<'a> SourceIndex<'a> {
    fn new(mm: &'a [u8], sm64: &'a [u8]) -> Self {
        let total = mm.len() + sm64.len();
        let mut index = Self {
            mm,
            sm64,
            input_heads: vec![EMPTY; BUCKET_COUNT],
            input_next: vec![EMPTY; total],
            output_heads: vec![EMPTY; BUCKET_COUNT],
            output_next: Vec::new(),
        };
        if total >= MIN_MATCH {
            for position in 0..=total - MIN_MATCH {
                if position < mm.len() && position + MIN_MATCH > mm.len() {
                    continue;
                }
                let bucket = bucket(index.source_slice(position, MIN_MATCH)) as usize;
                index.input_next[position] = index.input_heads[bucket];
                index.input_heads[bucket] = position as u32;
            }
        }
        index
    }

    fn commands_for(&mut self, output: &[u8]) -> Vec<Command> {
        self.output_next = vec![EMPTY; output.len()];
        let mut commands = Vec::new();
        let mut position = 0;
        let mut literal_start = 0;
        while position + MIN_MATCH <= output.len() {
            let input_match = self.best_input_match(&output[position..]);
            let output_match = self.best_output_match(output, position);
            let best = match (input_match, output_match) {
                (Some(input), Some(output)) if output.1 > input.1 => {
                    Some(Match::Output(output.0, output.1))
                }
                (Some(input), _) => Some(Match::Input(input.0, input.1)),
                (None, Some(output)) => Some(Match::Output(output.0, output.1)),
                (None, None) => None,
            };
            let Some(best) = best else {
                self.insert_output(output, position);
                position += 1;
                continue;
            };
            let length = best.length();
            if literal_start < position {
                push_literal(&mut commands, &output[literal_start..position]);
            }
            match best {
                Match::Input(source_position, _) => {
                    self.push_input_copy(&mut commands, source_position, length)
                }
                Match::Output(source_position, _) => {
                    push_output_copy(&mut commands, source_position, length)
                }
            }
            for written in position..position + length {
                self.insert_output(output, written);
            }
            position += length;
            literal_start = position;
        }
        if literal_start < output.len() {
            push_literal(&mut commands, &output[literal_start..]);
        }
        commands
    }

    fn best_input_match(&self, output: &[u8]) -> Option<(usize, usize)> {
        if output.len() < MIN_MATCH {
            return None;
        }
        let mut candidate = self.input_heads[bucket(&output[..MIN_MATCH]) as usize];
        let mut checked = 0;
        let mut best = None;
        while candidate != EMPTY && checked < MAX_CANDIDATES {
            let source_position = candidate as usize;
            if self.source_slice(source_position, MIN_MATCH) == &output[..MIN_MATCH] {
                let length = self.match_length(source_position, output);
                if best.map_or(true, |(_, best_length)| length > best_length) {
                    best = Some((source_position, length));
                }
            }
            candidate = self.input_next[source_position];
            checked += 1;
        }
        best
    }

    fn best_output_match(&self, output: &[u8], position: usize) -> Option<(usize, usize)> {
        if position + MIN_MATCH > output.len() {
            return None;
        }
        let mut candidate =
            self.output_heads[bucket(&output[position..position + MIN_MATCH]) as usize];
        let mut checked = 0;
        let mut best = None;
        while candidate != EMPTY && checked < MAX_CANDIDATES {
            let source_position = candidate as usize;
            if output[source_position..source_position + MIN_MATCH]
                == output[position..position + MIN_MATCH]
            {
                let limit = (output.len() - position).min(output.len() - source_position);
                let mut length = MIN_MATCH;
                while length < limit
                    && output[source_position + length] == output[position + length]
                {
                    length += 1;
                }
                if best.map_or(true, |(_, best_length)| length > best_length) {
                    best = Some((source_position, length));
                }
            }
            candidate = self.output_next[source_position];
            checked += 1;
        }
        best
    }

    fn match_length(&self, source_position: usize, output: &[u8]) -> usize {
        let source_remaining = if source_position < self.mm.len() {
            &self.mm[source_position..]
        } else {
            &self.sm64[source_position - self.mm.len()..]
        };
        let limit = source_remaining.len().min(output.len());
        let mut length = MIN_MATCH;
        while length < limit && source_remaining[length] == output[length] {
            length += 1;
        }
        length
    }

    fn source_slice(&self, position: usize, length: usize) -> &[u8] {
        if position < self.mm.len() {
            &self.mm[position..position + length]
        } else {
            let offset = position - self.mm.len();
            &self.sm64[offset..offset + length]
        }
    }

    fn insert_output(&mut self, output: &[u8], position: usize) {
        if position + MIN_MATCH > output.len() {
            return;
        }
        let bucket = bucket(&output[position..position + MIN_MATCH]) as usize;
        self.output_next[position] = self.output_heads[bucket];
        self.output_heads[bucket] = position as u32;
    }

    fn push_input_copy(&self, commands: &mut Vec<Command>, source_position: usize, length: usize) {
        let (is_mm, offset) = if source_position < self.mm.len() {
            (true, source_position)
        } else {
            (false, source_position - self.mm.len())
        };
        let offset = offset as u32;
        let length = length as u32;
        match commands.last_mut() {
            Some(Command::CopyMm {
                offset: previous_offset,
                length: previous_length,
            }) if is_mm && *previous_offset + *previous_length == offset => {
                *previous_length += length;
            }
            Some(Command::CopySm64 {
                offset: previous_offset,
                length: previous_length,
            }) if !is_mm && *previous_offset + *previous_length == offset => {
                *previous_length += length;
            }
            _ if is_mm => commands.push(Command::CopyMm { offset, length }),
            _ => commands.push(Command::CopySm64 { offset, length }),
        }
    }
}

enum Match {
    Input(usize, usize),
    Output(usize, usize),
}

impl Match {
    fn length(&self) -> usize {
        match self {
            Self::Input(_, length) | Self::Output(_, length) => *length,
        }
    }
}

fn push_output_copy(commands: &mut Vec<Command>, source_position: usize, length: usize) {
    let offset = source_position as u32;
    let length = length as u32;
    match commands.last_mut() {
        Some(Command::CopyOutput {
            offset: previous_offset,
            length: previous_length,
        }) if *previous_offset + *previous_length == offset => {
            *previous_length += length;
        }
        _ => commands.push(Command::CopyOutput { offset, length }),
    }
}

fn push_literal(commands: &mut Vec<Command>, bytes: &[u8]) {
    if bytes.is_empty() {
        return;
    }
    match commands.last_mut() {
        Some(Command::Literal(previous)) => previous.extend_from_slice(bytes),
        _ => commands.push(Command::Literal(bytes.to_vec())),
    }
}

fn bucket(bytes: &[u8]) -> u32 {
    debug_assert!(bytes.len() >= MIN_MATCH);
    let first = u64::from_le_bytes(bytes[..8].try_into().unwrap());
    let mut value = first ^ 0x9E37_79B9_7F4A_7C15;
    value ^= value >> 30;
    value = value.wrapping_mul(0xBF58_476D_1CE4_E5B9);
    value ^= value >> 27;
    value = value.wrapping_mul(0x94D0_49BB_1331_11EB);
    value ^= value >> 31;
    (value as u32) & ((BUCKET_COUNT as u32) - 1)
}
