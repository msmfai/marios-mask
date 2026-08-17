use jni::objects::{JClass, JString};
use jni::sys::{jint, jstring};
use jni::JNIEnv;
use std::path::Path;
use std::ptr;

fn path_from_java(env: &mut JNIEnv<'_>, value: &JString<'_>) -> Result<String, String> {
    env.get_string(value)
        .map(|text| text.into())
        .map_err(|error| format!("Could not read an Android file path: {error}"))
}

fn build(
    env: &mut JNIEnv<'_>,
    sm64: &JString<'_>,
    oot: &JString<'_>,
    mm: &JString<'_>,
    output: &JString<'_>,
    red: jint,
    green: jint,
    blue: jint,
) -> Result<(), String> {
    let sm64 = path_from_java(env, sm64)?;
    let oot = path_from_java(env, oot)?;
    let mm = path_from_java(env, mm)?;
    let output = path_from_java(env, output)?;
    let components = [red, green, blue];
    if components.iter().any(|value| !(0..=255).contains(value)) {
        return Err("Mario colour components must be between 0 and 255.".to_owned());
    }
    crate::build_from_paths_with_options(
        Path::new(&sm64),
        Path::new(&oot),
        Path::new(&mm),
        Path::new(&output),
        crate::BuildOptions {
            mario_color: [red as u8, green as u8, blue as u8],
        },
        |_| {},
    )
    .map_err(|error| format!("{error:#}"))
}

/// Returns an empty Java string on success and a user-facing error on failure.
/// No panic or Rust-owned pointer crosses the JNI boundary.
#[no_mangle]
pub extern "system" fn Java_ai_smf_mariosmask_MainActivity_nativeBuild(
    mut env: JNIEnv<'_>,
    _class: JClass<'_>,
    sm64: JString<'_>,
    oot: JString<'_>,
    mm: JString<'_>,
    output: JString<'_>,
    red: jint,
    green: jint,
    blue: jint,
) -> jstring {
    let message = match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        build(&mut env, &sm64, &oot, &mm, &output, red, green, blue)
    })) {
        Ok(Ok(())) => String::new(),
        Ok(Err(error)) => error,
        Err(_) => "The native builder stopped unexpectedly.".to_owned(),
    };
    env.new_string(message)
        .map(|text| text.into_raw())
        .unwrap_or_else(|_| ptr::null_mut())
}
