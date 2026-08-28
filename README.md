# Binary Watch Face

Binary Watch Face is a resource-only Wear OS face that presents hours, minutes, and optional seconds as true binary values. It is an independent implementation inspired by a retired face that no longer installs on newer watches.

![Binary Watch Face in 24-hour mode](watchface/src/main/res/drawable/preview.png)

The leftmost dot in each row is the most significant bit. Add the weights above the lit dots to read the value. For example, `23` is `16 + 4 + 2 + 1`.

## Features

- Follows the watch's 12- or 24-hour system setting, with overrides for either mode
- Uses four hour bits in 12-hour mode, five in 24-hour mode, and six for minutes and seconds
- Offers optional decimal hints, bit weights, a seconds row, date, battery level, and second ticks
- Defaults to phosphor terminal green on true black, with monochrome, amber, cyan, red, and violet themes
- Provides two complications by default and configurable two-, three-, and four-slot layouts
- Preserves normal provider actions on complications without defining any whole-face or custom tap actions
- Removes high-activity decoration, hints, weights, and complications in always-on display mode

## Compatibility

The watch face uses Watch Face Format 5 and requires Wear OS 7, API level 37. Format 5 is required to let a setting enable exactly two, three, or four complication slots without leaving invisible tap targets. That compatibility choice favors Pixel Watch 5 and other Wear OS 7 watches over older devices.

## Customize

Long-press the active face and choose **Edit**. The on-watch editor groups related switches onto compact pages. Available settings cover color, clock mode, date format, the complication count, the seconds row, decimal hints, bit weights, battery level, and second ticks. Each enabled complication can be assigned through the normal Wear OS complication picker.

The complication layouts keep the upper-left and upper-right providers stable when the count changes:

- Two: upper left and upper right
- Three: the upper pair plus lower center
- Four: the upper pair plus lower left and lower right

## Toolchain

The build requires JDK 17, Python 3, and the standalone [Android CLI](https://developer.android.com/tools/agents/android-cli). On macOS, `$HOME/Library/Android/sdk` is the standard SDK location. Install the project SDK packages with:

```sh
android --no-metrics sdk install platform-tools platforms/android-37.0 build-tools/36.0.0
```

Add the emulator and signed Wear OS 7 image for device testing:

```sh
android --no-metrics sdk install emulator system-images/android-37.0/android-wear-signed/arm64-v8a
```

Android CLI can start and manage an existing watch AVD, but its built-in `emulator create` command only accepts the hardware profiles shown by `--list-profiles`. Install the SDK command-line-tools component when a Wear profile is not listed, then create the AVD with `avdmanager`:

```sh
android --no-metrics sdk install cmdline-tools/latest
"$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" create avd \
    --name binary_watch_face_api_37 \
    --package 'system-images;android-37.0;android-wear-signed;arm64-v8a' \
    --device wearos_large_round
android --no-metrics emulator start --cold binary_watch_face_api_37
```

The SDK's `avdmanager` is used only for the Wear hardware profile. Package installation and emulator startup remain on Android CLI; the deprecated `sdkmanager` command is not needed.

## Build and install

Generate and build the resource-only APK and app bundle:

```sh
python3 tools/generate_watchface.py --check
./gradlew check assembleDebug bundleRelease
```

Install the debug APK without launching an activity:

```sh
android --no-metrics install \
    --device=emulator-5554 \
    --apks=watchface/build/outputs/apk/debug/watchface-debug.apk
```

On the watch, long-press the active face, scroll to **Add new**, and select **Binary Watch Face**. The release app bundle is written beneath `watchface/build/outputs/bundle/release/` and must be signed with a private release key before publication.

## Verification

Run the generator tests, generated-file check, and Android build with:

```sh
python3 -m unittest discover -s tests -v
python3 tools/generate_watchface.py --check
./gradlew check assembleDebug bundleRelease
```

Before publication, also run Google's [Watch Face Format validator and Memory Footprint Evaluator](https://github.com/google/watchface):

```sh
java -jar /path/to/wff-validator.jar 5 watchface/src/main/res/raw/watchface.xml
java -jar /path/to/memory-footprint.jar \
    --watch-face watchface/build/outputs/apk/debug/watchface-debug.apk \
    --schema-version 5 \
    --ambient-limit-mb 10 \
    --active-limit-mb 100 \
    --apply-v1-offload-limitations \
    --estimate-optimization
```

The GitHub Actions workflow repeats the deterministic generator checks and full Android build using Android CLI rather than `sdkmanager`.

## Privacy

The watch face contains no executable Android code, network access, analytics, or data-collection permissions. See [PRIVACY.md](PRIVACY.md).

## License

Copyright 2026 James Klein

Licensed under the GNU Affero General Public License, version 3 only. See [LICENSE](LICENSE).
