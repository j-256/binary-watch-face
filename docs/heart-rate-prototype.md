# Heart-history prototype

Binary Pulse places a quiet heart-rate history behind the binary time. Choose a 30-minute, 1-hour, 6-hour, or 24-hour window, and use a subtle or clear graph with any of the existing provider layouts. The clock stays centered, the native readouts remain separate, and the bottom system-indicator reserve remains clear.

This is an unreleased Wear OS 7 prototype. **Binary Pulse** installs alongside **Binary**, and **Binary Heart History** is a separate on-watch application. The existing Binary installation does not need to be replaced.

## Preview

These Wear OS emulator captures use invented readings labeled **SAMPLE**. They do not show anyone's health data.

<p align="center">
  <img src="screenshots/history-hour.png" alt="One-hour sample graph behind the centered binary clock" width="31%">
  <img src="screenshots/history-six-hours.png" alt="Six-hour sample graph showing activity and gaps" width="31%">
  <img src="screenshots/history-day.png" alt="Day-long sample history behind the binary clock" width="31%">
</p>

The [30-minute view](screenshots/history-half-hour.png) gives the closest look at short-term changes.

Light appearance uses the same image tinted to the selected text color. The largest clock keeps its bit weights clear of the graph caption. In confirmed AOD, the graph is hidden and the system's stopwatch indicator remains clear of the face content. The native 128 BPM value in these layout fixtures is synthetic too.

<p align="center">
  <img src="screenshots/history-light.png" alt="Light appearance with the sample graph and a clear stopwatch indicator" width="31%">
  <img src="screenshots/history-dense.png" alt="Large clock with bit weights and four provider slots over a sample graph" width="31%">
  <img src="screenshots/history-ambient.png" alt="Confirmed ambient rendering hides the graph and clears the system stopwatch indicator" width="31%">
</p>

## Try it

Use the [repository toolchain](../README.md#toolchain), including JDK 17 and Android API 37, to build both APKs:

```sh
python3 tools/generate_watchface.py --check
./gradlew check :history:assembleDebug :watchface:assemblePrototype
```

Install on an explicitly selected Wear OS 7 emulator or test watch:

```sh
adb -s DEVICE_SERIAL install -r history/build/outputs/apk/debug/history-debug.apk
adb -s DEVICE_SERIAL install -r watchface/build/outputs/apk/prototype/watchface-prototype.apk
```

1. Open **Binary Heart History** from the watch's app list.
2. Choose **Preview sample data** for an immediate demonstration, or **Start recording** and grant heart-rate access followed by background access.
3. Choose the time window in the app. It applies to both the preview and watch-face graph.
4. Long-press the watch face, choose **Add new**, and select **Binary Pulse**. Its default layout enables the clear graph and two ordinary providers.
5. In the face editor, use **Layout** to select subtle or clear heart history with no ordinary providers, or with two, three, or four. If automatic provider selection is unavailable, assign **Heart history graph** to **Heart history background** in the complication picker.

Wear OS allows only one active setting to control complication-slot enablement. Graph visibility and provider count therefore share the Layout selector. Choosing a layout without history disables the image slot completely. The graph supplies no tap action; ordinary providers keep their normal actions.

Recording starts with an empty history and fills as the watch delivers readings. It does not import an existing fitness app's history. Preview pauses recording and preserves eligible recorded data; **Start recording** resumes it. **Stop and erase history** clears it after confirmation. The decimal background is suppressed in active mode while history is selected; its configured AOD behavior remains independent.

The time-window controls are in the on-watch app:

<img src="screenshots/history-settings.png" alt="On-watch controls for 30 minutes, 1 hour, 6 hours, and 24 hours" width="260">

## How the graph behaves

| Choice | Behavior |
| --- | --- |
| Window | Rolling 30 minutes, 1 hour, 6 hours, or 24 hours, ending at image generation |
| Refresh | Requests Wear OS updates about every five minutes; explicit setting changes request an immediate refresh |
| Trace | Bucket averages with a faint min/max envelope to retain short peaks |
| Missing data | Breaks the trace when adjacent readings are more than two minutes apart; gaps shorter than a display bucket can disappear at long spans |
| Scale | Adjusts to the visible range with padding; the header gives the observed minimum and maximum in BPM |
| Age | Shows the age of the newest reading; labels it stale after fifteen minutes |
| Always-on display | Hides the graph to preserve the established low-activity clock presentation |
| No data | Displays a waiting or setup prompt rather than invented readings |

This is a periodically refreshed trend, not a beat-to-beat pulse or ECG waveform. Sensor cadence, batching, and availability belong to the device's Health Services implementation. The native heart-rate readout and this stored history can update at different times. A graph image expires after ten minutes if it is not refreshed. See Android's [passive monitoring guide](https://developer.android.com/health-and-fitness/health-services/monitor-background) and [complication update guidance](https://developer.android.com/training/wearables/complications/exposing-data).

## Architecture and privacy

The `watchface` module remains resource-only with `android:hasCode="false"`. Watch Face Format exposes a scalar heart rate but does not provide a history buffer for this graph. The separate `history` app receives passive Health Services callbacks, stores a bounded local series, and renders a transparent image complication. WFF draws that image below the binary clock and tints it to the selected text color. See the [WFF data-source reference](https://developer.android.com/reference/wear-os/wff/common/attributes/source-type).

The recorder uses the Wear OS health permissions for heart-rate and background access, requested separately. It checks passive heart-rate capability before registering and schedules recovery after reboot or package replacement. A short, bounded registration attempt runs off the UI and image-delivery thread. Unsupported devices and registration failures have visible status messages. See the [Health Services permission guide](https://developer.android.com/health-and-fitness/health-services/permissions).

Readings stay in private app storage. Values outside the supported input range of 25 to 240 BPM, invalid numbers, future timestamps, and sensor readings marked unreliable or no-contact are excluded. Storage retains at most one value per second, keeping the newest reading when batches arrive out of order. Collection, reads, and background maintenance prune data outside the preceding 24 hours. The app requests no network access and disables backup. Logs report operation, outcome, duration, and sample count without recording health values. See the [privacy policy](../PRIVACY.md), including system image caching and delayed maintenance when the app is stopped.

## Verification

Run the ordinary generator, geometry, lint, JVM, and build checks:

```sh
python3 -m unittest discover -s tests -v
python3 tools/generate_watchface.py --check
python3 tools/check_layout.py
./gradlew check assembleDebug bundleRelease :watchface:assemblePrototype
```

Run database and lifecycle integration tests on a disposable emulator. These tests erase the history app's data:

```sh
ANDROID_SERIAL=EMULATOR_SERIAL ./gradlew :history:connectedDebugAndroidTest
```

The prototype has been checked on a Wear OS 7 emulator for Health Services callback delivery with emulated sensor values, the separate permission prompts, reboot registration, sample-window updates, and active/AOD rendering. Tapping the system stopwatch indicator opened the ongoing activity. Storage tests cover expiration, out-of-order batches, unreliable values, late callbacks after stopping, permission-loss handling, and sample isolation. Layout checks cover the background slot, readouts, provider targets, and the ongoing-activity reserve. Official WFF validation and memory evaluation complement these checks; see the [verification guide](layout-verification.md).

Physical-watch installation, long-duration reliability, battery impact, and manufacturer-specific sensor cadence remain unverified. No release or Play submission is part of this prototype. On-wrist testing and health-permission distribution requirements need review before publication.

## Remove the prototype

Select the original Binary face, then uninstall the two prototype packages:

```sh
adb -s DEVICE_SERIAL uninstall dev.j256.binarywatchface.prototype
adb -s DEVICE_SERIAL uninstall dev.j256.binarywatchface.history
```

This removes the prototype face settings and local heart-rate history. It leaves the original Binary package installed.
