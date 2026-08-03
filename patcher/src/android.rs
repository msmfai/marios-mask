use jni::objects::{JClass, JString};
use jni::sys::jstring;
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
    mm: &JString<'_>,
    output: &JString<'_>,
) -> Result<(), String> {
    let sm64 = path_from_java(env, sm64)?;
    let mm = path_from_java(env, mm)?;
    let output = path_from_java(env, output)?;
    crate::build_from_paths(Path::new(&sm64), Path::new(&mm), Path::new(&output), |_| {})
        .map_err(|error| format!("{error:#}"))
}

/// Returns an empty Java string on success and a user-facing error on failure.
/// No panic or Rust-owned pointer crosses the JNI boundary.
#[no_mangle]
pub extern "system" fn Java_ai_smf_mariosmask_MainActivity_nativeBuild(
    mut env: JNIEnv<'_>,
    _class: JClass<'_>,
    sm64: JString<'_>,
    mm: JString<'_>,
    output: JString<'_>,
) -> jstring {
    let message = match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        build(&mut env, &sm64, &mm, &output)
    })) {
        Ok(Ok(())) => String::new(),
        Ok(Err(error)) => error,
        Err(_) => "The native builder stopped unexpectedly.".to_owned(),
    };
    env.new_string(message)
        .map(|text| text.into_raw())
        .unwrap_or_else(|_| ptr::null_mut())
}
