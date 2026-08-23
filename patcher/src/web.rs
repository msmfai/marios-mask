use wasm_bindgen::prelude::*;

use crate::{build_from_rom_bytes_with_options, BuildOptions};

#[wasm_bindgen]
pub fn build_marios_mask(
    sm64: Vec<u8>,
    oot: Vec<u8>,
    mm: Vec<u8>,
    red: u8,
    green: u8,
    blue: u8,
) -> Result<Vec<u8>, JsValue> {
    build_from_rom_bytes_with_options(
        sm64,
        oot,
        mm,
        BuildOptions {
            mario_color: [red, green, blue],
        },
        |_| {},
    )
    .map_err(|error| JsValue::from_str(&format!("{error:#}")))
}
