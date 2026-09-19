# Project cover

The project cover is rendered from the screenshot-only Binary APK on a fresh Wear OS 7 emulator at 454 by 454 pixels. This variant fixes heart rate at 72 BPM because the emulator does not provide passive heart-rate history to the native WFF data source. Production builds continue to use the native source. The capture verifies that the APK contains the generated screenshot watch-face XML and that the active renderer is displaying Binary before replacing `cover.png`.

```sh
python3 tools/capture_cover.py
```

The command requires Python 3, JDK 17, and `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) pointing to an Android SDK with platform 37.0, build-tools 36.0.0, platform-tools, cmdline-tools/latest, emulator, and the signed Wear OS 7 system image. Install `system-images/android-37.0/android-wear-signed/arm64-v8a` on Apple silicon, or the `x86_64` image on Intel and Linux. Set `JAVA_HOME` when the JDK is not selected by the shell. Linux requires access to KVM.

Capture first checks the generator and builds the APK, then creates and removes its own virtual device. It disconnects simulated charging, activates Binary through the watch-face picker, and verifies the renderer's package identity. Existing emulators and application data are not used. The default face uses the emulator's date, time, and battery state. Store screenshots remain separately curated; see [the store asset guide](../store/README.md).

CI captures after the generator tests and build, then uploads the image for review. A successful build on `main` commits a changed cover. Pull requests only produce an artifact. Scheduled and manual runs refresh the cover without a source change; a superseded build does not overwrite a newer revision. A failed capture preserves the committed image and fails the workflow.

`layout-four-ongoing.png` and `layout-four-ambient.png` are separate clearance checks used by the [design considerations](../design-considerations.md). They show the four-slot layout at Huge size with a sample heart rate of 180 BPM, binary battery, and an ongoing-activity test app's system indicator. Capture ambient evidence only after the renderer reports ambient mode; a dimmed interactive frame is not an AOD capture. These diagnostic images are not refreshed by the default cover command.

For a connected physical watch, use the read-only capture command in the [layout verification guide](../layout-verification.md). It saves the screenshot with verified package, version, mode, and settings instead of replacing the public cover.
