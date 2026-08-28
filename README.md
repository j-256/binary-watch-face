# Binary Watch Face

Binary Watch Face is a resource-only Wear OS face that presents hours, minutes, and optional seconds as binary values. It is an independent implementation inspired by a retired face that no longer installs on current Wear OS watches.

The project is under active development. Its first target is Pixel Watch 5, with compatibility extending to Wear OS 4 and later through Watch Face Format 1.

## Planned experience

- System, 12-hour, and 24-hour modes
- Four- or five-bit hour rows and six-bit minute and second rows
- Optional decimal hints, bit weights, date, battery, and second ticks
- Phosphor terminal green by default, with additional monochrome, amber, cyan, red, and violet themes
- Two complications by default, with balanced two-, three-, and four-slot layouts
- Standard provider actions on complications and no custom whole-face tap actions
- Low-luminance always-on display

## Build

The build requires JDK 17 and the standalone [Android CLI](https://developer.android.com/tools/agents/android-cli). Install the required SDK components with:

```sh
android --no-metrics sdk install platform-tools emulator platforms/android-37.0 build-tools/36.0.0 system-images/android-37.0/android-wear-signed/arm64-v8a
```

On macOS, the CLI uses the standard `$HOME/Library/Android/sdk` location unless another SDK path is configured. Point `JAVA_HOME` to JDK 17, then run:

```sh
./gradlew assembleDebug
./gradlew bundleRelease
```

The debug APK is written beneath `watchface/build/outputs/apk/debug/`. The unsigned release bundle is written beneath `watchface/build/outputs/bundle/release/` and must be signed with a private release key before publication.

## License

Copyright 2026 James Klein

Licensed under the GNU Affero General Public License, version 3 only. See [LICENSE](LICENSE).
