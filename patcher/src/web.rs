use wasm_bindgen::prelude::*;

use crate::{build_from_rom_bytes_with_options, BuildOptions, GameMode};

#[wasm_bindgen]
pub fn build_marios_mask(
    sm64: Vec<u8>,
    oot: Vec<u8>,
    mm: Vec<u8>,
    palette: Vec<u8>,
    mode: String,
) -> Result<Vec<u8>, JsValue> {
    let game_mode = GameMode::parse(&mode)
        .ok_or_else(|| JsValue::from_str(&format!("Unknown game mode {mode:?}")))?;
    if palette.len() != 18 {
        return Err(JsValue::from_str(
            "Mario palette must contain exactly six RGB colours",
        ));
    }
    let mut mario_palette = [[0u8; 3]; 6];
    for (group, color) in mario_palette.iter_mut().zip(palette.chunks_exact(3)) {
        group.copy_from_slice(color);
    }
    build_from_rom_bytes_with_options(
        sm64,
        oot,
        mm,
        BuildOptions {
            mario_palette,
            game_mode,
        },
        |_| {},
    )
    .map_err(|error| JsValue::from_str(&format!("{error:#}")))
}
