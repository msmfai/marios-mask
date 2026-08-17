# Android builder

The Android app is a thin Storage Access Framework UI over the same Rust recipe
engine used by the desktop builder. It requests no broad storage permission and
no network permission. All three source ROMs are copied into the app's private cache,
validated and combined locally, then removed after the selected output document
has been written.

Supported release ABIs are `arm64-v8a` for physical 64-bit Android devices and
`x86_64` for Android emulators. The minimum supported system is Android 8.0
(API 26).

The generated JNI libraries and APK are build products and must not be committed.
Build the Rust engine before invoking Gradle:

```sh
cd patcher
cargo ndk -t arm64-v8a -t x86_64 \
  -o ../android/app/src/main/jniLibs \
  build --release --locked --no-default-features --features android-jni
cd ..
gradle -p android :app:lintDebug :app:assembleDebug
```

Release builds require the four `ANDROID_KEY*`/`ANDROID_KEYSTORE*` environment
variables enforced by `android/app/build.gradle`. GitHub Actions owns release
signing and publishes `MariosMaskBuilder-android.apk`.
