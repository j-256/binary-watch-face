# Visibility model

[`design/visibility.json`](../design/visibility.json) defines the visual budgets shared by the resource-only face and the History bitmap renderer. Change the intended contrast and geometry there, then run `python3 tools/generate_watchface.py`. The generator writes the WFF variants and `GraphVisibility.java`; its `--check` mode rejects stale output from either module.

The initial calibration reproduces the brighter graph's provider alphas, face preset alphas, stroke sizes, bit-weight emphasis and AOD brightness. It introduces no settings or background work. All solving happens at build time; the watch receives constants.

## What a weight means

Opaque foreground is the reference weight of `1`. A component's weight describes its contrast above the flat background relative to that foreground:

```text
target contrast = 1 + visibility * (foreground contrast - 1)
visibility = (component contrast - 1) / (foreground contrast - 1)
```

This normalization is a project design convention. Contrast uses the [W3C relative luminance](https://www.w3.org/TR/WCAG22/#dfn-relative-luminance) and [contrast ratio](https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio) definitions. Blend sRGB channels first, then linearize the resulting color for luminance. Multiplying alpha by a visibility weight would produce a different result.

These weights do not measure perceived brightness, physical display luminance, occupied area or visual importance. Keep stroke width, marker size and font size alongside the weights. A thin line with the same core contrast can be harder to follow than a thicker one. Text size and anti-aliasing also matter.

## How both renderers share the model

History draws transparent white pixels for the trace, marks, labels, status, fill and range. The face applies the selected text tint and a single Faint, Subtle or Clear opacity to that entire image. The effective opacity at a fully covered pixel is:

```text
effective opacity = (provider alpha / 255) * (face alpha / 255)
```

First, the solver derives each provider alpha from its role weight in the active reference palette. It then derives each preset's face alpha from the requested final trace weight, accounting for the provider alpha already present. It searches the representable byte values for the nearest target contrast. This prevents an unintended second dimming factor from being mistaken for the requested contrast.

`graph.roles` describes the undimmed provider, which is also the Clear calibration. `graph.presets` specifies final trace targets; marks and labels retain their provider relationship through the shared face opacity. Inspect their final values in the report rather than assuming all weights scale linearly with that opacity. Marks cross the trace, so their centers are brighter than their extensions. A separate contract keeps those intersections below the timestamps.

The active reference is terminal green on black. AOD has a white-on-black reference and separate Dim, Normal and Bright foreground weights; it keeps the graph hidden. Native heart-rate visibility remains controlled independently. Existing decimal-backdrop percentages, including 7.5%, remain literal opacity choices in the face generator. They are not reinterpreted as contrast weights.

The model governs graph roles, graph geometry, bit-weight emphasis and AOD brightness. The main foreground remains the opaque reference. Decorative bezel effects, independently colored decimal digits and third-party complication content retain their own controls. They are not implicitly assigned graph weights.

## Reference floors and palette limits

`minimum_contrast` protects the ideal solid-core calibration against accidental dimming. `minimum_rendered_contrast` separately protects the measured bitmap after tinting, scaling and face opacity. Bitmap filtering can distribute the line across neighboring pixels and lower its brightest pixel, so the rendered trace floors include that measured loss. The Android test logs contrast for the trace, marker extensions, intersections and timestamps across time windows and watch resolutions. These are project regression floors for the optional background, not accessibility compliance claims. The Faint trace intentionally has low contrast. Tapping the background exposes the larger inspection graph in History.

The provider does not receive the face's selected palette. Its components are baked into one image with one face tint and opacity, so the reference role targets cannot be independently normalized for every palette without changing that contract. Other palettes retain the calibrated alphas. The report evaluates every supported foreground/theme combination and identifies components below the reference floors, including cases where even opaque foreground falls short. Selecting an unsuitable foreground/background pair does not make the reference calibration fail.

Predictions cover solid pixels against a flat background. They exclude anti-aliasing, scaling, the faint fill beneath the trace, range shading, marker intersections and foreground occlusion. The decimal backdrop and normal complications paint above the graph. Final pixels can differ from the prediction, and outdoor illumination or the watch's brightness setting changes real-world legibility. Use Android rendering tests and actual face captures alongside the model.

## Inspect and tune

```sh
python3 tools/check_visibility.py
python3 tools/check_visibility.py --format json > visibility.json
python3 tools/check_visibility.py --format html > visibility.html
```

Open the standalone HTML file in a browser. It compares graph presets, colors, themes, AOD brightness and backdrop opacity with an illustrative trace and live contrast table. It runs offline without dependencies or telemetry. The drawing uses invented readings and simplified watch geometry; it is a calibration aid, not a Wear OS screenshot. The machine-readable report includes role/preset alphas, reference checks, palette predictions and their limitations.

`-f` is the short form of `--format`; accepted formats are `text`, `json` and `html`. `-m` / `--model PATH` checks an alternative JSON model without changing the repository's model or generated resources. `-h` / `--help` prints usage. Results go to stdout; input errors go to stderr. Exit status is `0` when reference contracts pass, `1` when a contract fails, and `2` for invalid usage or input. The command requires only Python 3.

After adjusting a budget, regenerate resources and run:

```sh
python3 tools/generate_watchface.py
python3 tools/generate_watchface.py --check
python3 tools/check_visibility.py
python3 -m unittest discover -s tests -v
python3 tools/check_layout.py
./gradlew check assembleDebug bundleRelease :watchface:assemblePrototype
ANDROID_SERIAL=emulator-5554 ./gradlew :history:connectedDebugAndroidTest
```

Select a disposable Wear OS emulator explicitly; the History integration suite clears its local data. `GraphVisibilityTest` renders the actual provider through a Canvas tint and face-opacity stage at watch resolutions, then checks the rendered floors and trace/mark/timestamp hierarchy. It checks marker extensions away from the brighter trace intersections. Other History tests cover gaps, isolated points, marker shapes and every valid `HH:mm` label. The freshness check couples Java and WFF generation, while mathematical tests cover gamma, quantization and compounded alpha.

Inspect active Faint, Subtle and Clear, a light theme and confirmed AOD using the [layout verification workflow](layout-verification.md). Include a system ongoing-activity indicator. Preserve captures and measurements with their source revision before changing the calibration further. Color or alpha predictions alone do not establish a physical-watch result.
