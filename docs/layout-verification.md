# Layout verification

Use geometry checks for repeatable padding requirements and device captures for actual glyphs, provider content, and system overlays. The [design considerations](design-considerations.md) define the protected areas and the hardware cases behind them.

## Check geometry

Run from the repository root with Python 3:

```sh
python3 tools/generate_watchface.py --check
python3 tools/check_layout.py
python3 -m unittest discover -s tests -v
```

The clearance command reports the tightest gap in each category, in the watch face's 450-unit design coordinates. `--json` reports each comparison for use by other tools. An optional positional path checks another uncompiled Binary WFF XML file against the generator's layout rules.

| Check | Required space |
| --- | --- |
| Native readouts below the largest clock, including seconds | Six design units |
| Native readouts and complication outlines | Six design units |
| Complication outlines enabled together | Six design units |
| Bottom system rectangle and native readouts or complications | Four design units |
| Taller rounded activity pill and native readouts or complications | Four design units |

Complication measurements include `BoundingOval` outline padding. The lower-pair, center, and side slots are checked in their enabled combinations. The command shares geometry helpers with the generator tests. Regression cases deliberately move a readout back into the system area, move the center slot into the taller pill, and make complications collide. CI runs the tests, generated-file check, and clearance command before building.

The optional heart-history image deliberately overlaps ordinary face content from behind. Its bounds must clear the system reserve, and its scene order must precede native readouts and ordinary complications. The supplied history provider has no tap action. Verify touch routing with actionable providers in every ordinary slot position, including the optional center slot; painted layer order alone does not prove that taps reach them.

Exit status is `0` when all gaps pass, `1` for insufficient clearance, and `2` for invalid input or usage. The command needs no SDK, emulator, device, or image-processing dependency.

## Capture a connected watch

`tools/capture_watch.py` reads the selected watch's renderer and saves `watch.png` with a `snapshot.json` receipt. It requires Python 3 and Android platform-tools. Locate `adb` with `--adb`, `ANDROID_HOME`/`ANDROID_SDK_ROOT`, or `PATH`. Replace `SERIAL` with the target from `adb devices -l` and `VERSION` with the installed version name.

Leave Binary visible with a stopwatch, timer, or another ongoing activity. Capture active mode first:

```sh
python3 tools/capture_watch.py \
    --serial SERIAL --expected-version VERSION --mode active \
    --output "$HOME/binary-watch-captures/active"
```

Let the watch enter always-on mode, then capture it while comparing its selections with the first receipt:

```sh
python3 tools/capture_watch.py \
    --serial SERIAL --expected-version VERSION --mode ambient \
    --compare-with "$HOME/binary-watch-captures/active/snapshot.json" \
    --output "$HOME/binary-watch-captures/ambient"
```

Each output directory must be new. Captures can contain personal health and complication data, so keep them outside tracked project files. The receipt includes the rendered package and version, actual mode, image dimensions, selected style, and provider identities exposed by the renderer. Raw runtime dumps and complication values are omitted from the receipt.

The command checks visibility, package identity, version, and both ambient-state signals before capture. It reads the renderer again afterward and rejects evidence if its state changed. This prevents a dimmed interactive frame from being labeled as AOD. All device commands are reads; installation, waking the screen, selecting the face, and starting or tapping an activity remain explicit operator actions.

For update verification, capture before installation and use that receipt with `--compare-with` after installing the new version. Version and rendering mode may change; selected style, enabled slots, and reported provider identities must agree. Missing identities for enabled providers are reported as unverified and make a requested comparison fail. The comparison requires the same device serial and package. A device reconnect that changes its serial requires a new baseline.

Exit status is `0` for a successful capture and requested comparison, `1` for device/capture failure or changed/unverifiable selections, `2` for invalid input or an unmet precondition such as the wrong render mode, and `3` for missing `adb`. Results are JSON on stdout; diagnostics are on stderr. Both commands support `-h` and `--help`.

## Measure and review system overlays

Inspect active and ambient screenshots for the full pill silhouette, its upper edge, and the visible gap to every enabled complication and native readout. Confirm the actual return action by tapping the pill and returning to Binary. A successful capture verifies its provenance; it does not automatically identify the pill or establish its invisible tap target.

Convert pixel coordinates to design coordinates with `design_x = pixel_x * 450 / image_width` and the corresponding height ratio for `design_y`. Measure a rounded outline rather than treating the empty corners of its bounding box as painted content. Preserve padding beyond the observed shape and account for additional activity types and animation states when changing the named reserves in `tools/generate_watchface.py`.

The Pixel Watch stopwatch measurements recorded in the design guide used a green face to distinguish the gray, white, and purple pill from watch-face content. Color-based segmentation depends on that palette; it is evidence for those captures, not a general collision detector. The geometry gate protects the documented reserve independently of screenshot colors.
