# Heart-history prototype

Binary Pulse places a wide, quiet heart-rate history behind the binary time. The dim trace and faint fill fade toward the edges of the face. Labels are hidden by default, with optional timespan and range captions beneath the date. Choose a 30-minute, 1-hour, 6-hour, or 24-hour window, and use a subtle or clear graph with any of the existing provider layouts. The clock stays centered, the native readouts remain legible, and the bottom system-indicator reserve remains clear.

This is an unreleased Wear OS 7 prototype. **Binary Pulse** installs alongside **Binary**, and **Binary Heart History** is a separate on-watch application. The existing Binary installation does not need to be replaced.

## Preview

These Wear OS emulator captures use invented readings. They do not show anyone's health data. The companion app identifies preview mode; the watch face follows the selected label preference without a demo badge.

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

For a physical watch, check that it runs Wear OS 7 (Android API 37) before installing. Put the watch and computer on the same Wi-Fi network, enable the watch's developer options, then enable **ADB debugging** and **Wireless debugging**. Choose **Pair new device**, use the IP address and pairing port shown there, and enter its pairing code when prompted. Return to the main Wireless debugging screen for the connection address; its port can differ from the pairing port. These steps follow Android's [Wi-Fi debugging guide](https://developer.android.com/training/wearables/get-started/debug-wifi).

```sh
adb pair WATCH_IP:PAIRING_PORT
adb connect WATCH_IP:CONNECTION_PORT
adb devices -l
```

Use the connected device's exact serial from `adb devices -l` in place of `DEVICE_SERIAL` below. Confirm its API level, then install the history app before the face so its provider is available during setup. The same installation commands work with an explicitly selected Wear OS 7 emulator.

```sh
adb -s DEVICE_SERIAL shell getprop ro.build.version.sdk
adb -s DEVICE_SERIAL install -r history/build/outputs/apk/debug/history-debug.apk
adb -s DEVICE_SERIAL install -r watchface/build/outputs/apk/prototype/watchface-prototype.apk
```

The SDK check must report `37` or newer. In the downloadable prototype bundle, the corresponding APKs are named `binary-heart-history.apk` and `binary-pulse-prototype.apk`.

1. Open **Binary Heart History** from the watch's app list.
2. Choose **Preview sample data** for an immediate demonstration, or **Start recording** and grant heart-rate access followed by background access.
3. Choose the time window in the app. It applies to both the preview and watch-face graph.
4. Under **Graph labels**, keep **None** for the default minimal face, or choose **Time window** or **Time + range**. This setting changes the face; the app's chart keeps its labels.
5. Long-press the watch face, choose **Add new**, and select **Binary Pulse**. Its default layout enables the clear graph and two ordinary providers.
6. In the face editor, use **Layout** to select subtle or clear heart history with no ordinary providers, or with two, three, or four. If automatic provider selection is unavailable, assign **Heart history graph** to **Heart history background** in the complication picker.

Wear OS allows only one active setting to control complication-slot enablement. Graph visibility and provider count therefore share the Layout selector. Choosing a layout without history disables the image slot completely. Use the supplied **Heart history graph** provider, which supplies no tap action. The graph renders below the ordinary complications, whose opaque backgrounds preserve their contrast and whose normal actions remain reachable.

Recording starts with an empty history and fills as the watch delivers readings. It does not import an existing fitness app's history. Preview pauses recording and preserves eligible recorded data; **Start recording** resumes it. **Stop and erase history** clears it after confirmation. The decimal background is suppressed in active mode while history is selected; its configured AOD behavior remains independent.

The time-window controls are in the on-watch app:

<img src="screenshots/history-settings.png" alt="On-watch controls for 30 minutes, 1 hour, 6 hours, and 24 hours" width="260">

## Preview data

The preview is a deterministic synthetic day with one reading per minute. It combines small resting fluctuations, a lower sleep period, a walking peak, and a stronger exercise peak, spanning approximately 45 to 163 BPM across the full day. Two deliberate interruptions leave five and thirty-two minutes between consecutive readings. This exercises interrupted collection as well as continuous segments.

Every refresh regenerates the same shape relative to the new end time. Its timestamps advance, but the preview does not evolve or scroll through different activity. It is a visual fixture, not a continuous sensor simulation. Real recording stores incoming readings and advances the rolling window over that history.

The shorter windows show less of the fixture: thirty minutes covers modest variation, one hour includes the walking peak, six hours adds the exercise peak, and twenty-four hours includes the lower sleep period. The renderer groups readings into display buckets and preserves each bucket's minimum and maximum. At the day scale, the short interruption falls inside a bucket and can disappear; the longer interruption remains visible. Separate tests exercise empty, stale, invalid, isolated, and out-of-order readings.

## How the graph behaves

| Choice | Behavior |
| --- | --- |
| Window | Rolling 30 minutes, 1 hour, 6 hours, or 24 hours, ending at image generation |
| Labels | None by default; optionally show the time window, or the time window and observed BPM range |
| Refresh | Requests Wear OS updates about every five minutes; explicit setting changes request an immediate refresh |
| Trace | Dim bucket averages with a faint min/max envelope to retain short peaks and a soft fill beneath each connected segment |
| Missing data | Breaks both the trace and its fill when adjacent readings are more than two minutes apart; gaps shorter than a display bucket can disappear at long spans |
| Scale | Adjusts to the visible range with padding; the optional range caption gives the observed minimum and maximum in BPM |
| Age | The range caption includes the newest reading's age; a stale notice appears after fifteen minutes even when labels are hidden |
| Always-on display | Hides the graph to preserve the established low-activity clock presentation |
| No data | Displays a waiting or setup prompt rather than invented readings |

This is a periodically refreshed trend, not a beat-to-beat pulse or ECG waveform. Sensor cadence, batching, and availability belong to the device's Health Services implementation. The native heart-rate readout and this stored history can update at different times. A graph image expires after ten minutes if it is not refreshed. See Android's [passive monitoring guide](https://developer.android.com/health-and-fitness/health-services/monitor-background) and [complication update guidance](https://developer.android.com/training/wearables/complications/exposing-data).

The on-watch app keeps a brighter chart with guide lines for closer inspection. The watch-face image uses the wider, dimmer treatment. The tiny lightning bolt beside the battery value means Wear OS reports charging; the separate bottom-center charging indicator belongs to the system.

Hiding labels leaves fresh history entirely free of captions in both preview and recording modes. Stale or empty histories retain their status notices. See the [optional time and range captions](screenshots/history-labels.png) for the more detailed treatment.

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

The prototype has been checked on a Wear OS 7 emulator for Health Services callback delivery with emulated sensor values, the separate permission prompts, reboot registration, sample-window updates, and active/AOD rendering. Actionable world-clock providers at every ordinary slot position verified that the overlapping background leaves their actions reachable. Tapping the system stopwatch indicator opened the ongoing activity. Storage tests cover expiration, out-of-order batches, unreliable values, late callbacks after stopping, permission-loss handling, and sample isolation. Image tests check payload size, transparent edges, and unfilled gaps. Layout checks cover foreground layer order, readouts, ordinary provider targets, and the ongoing-activity reserve. Official WFF validation and memory evaluation complement these checks; see the [verification guide](layout-verification.md).

Physical-watch installation, long-duration reliability, battery impact, and manufacturer-specific sensor cadence remain unverified. No release or Play submission is part of this prototype. On-wrist testing and health-permission distribution requirements need review before publication.

## Remove the prototype

Select the original Binary face, then uninstall the two prototype packages:

```sh
adb -s DEVICE_SERIAL uninstall dev.j256.binarywatchface.prototype
adb -s DEVICE_SERIAL uninstall dev.j256.binarywatchface.history
```

This removes the prototype face settings and local heart-rate history. It leaves the original Binary package installed.
