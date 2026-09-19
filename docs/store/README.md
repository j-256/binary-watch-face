# Google Play listing

This directory contains the source assets and copy for the Wear OS Google Play listing.

## Default listing

App name:

```text
Binary
```

Short description:

```text
A deeply customizable true-binary watch face for Wear OS 7.
```

Full description:

```text
Read time in true binary, with each bit aligned and clearly weighted. Binary is a deeply customizable watch face built for Wear OS 7.

TRUE BINARY TIME
- Choose 12-hour or 24-hour time
- Show or hide a binary seconds row
- Show bit weights in active and AOD modes or only while active
- Keep every row aligned across the dial

MAKE IT YOURS
- Start with Terminal, Seconds, Cyan dashboard, or Light presets
- Pick independent dot, text, and decimal-backdrop colors
- Adjust backdrop opacity, size, position, and active/AOD visibility
- Choose tiny through huge display sizes
- Select glow, bezel, and tick effects
- Use ISO 8601 by default or choose a regional date format
- Show native heart rate beside the watch battery in decimal, hexadecimal, or binary
- Configure two, three, or four complications

ALWAYS-ON DISPLAY
Keep the selected color with a dense, low-power dot pattern. Choose dim, normal, or bright rendering. Date, weekday, paired battery and heart rate, and the decimal backdrop can each be included or omitted from the always-on display.

PRIVATE BY DESIGN
Binary is a resource-only Watch Face Format watch face. It has no executable app code, network access, analytics, advertising, accounts, or data collection. Time, battery, heart rate, settings, and complication data remain on your watch.

Requires Wear OS 7.
```

## Assets

- `app-icon.png`: 512 x 512 app icon derived from the exact default watch-face capture
- `feature-graphic.png`: 1024 x 500 feature graphic using the exact default watch-face capture

Upload screenshots in the table order. Keep `screenshot-terminal-green.png` first because it shows the exact factory defaults and is also the lead image on GitHub.

| Screenshot | Clock and date | Binary styling | Layout and data |
| --- | --- | --- | --- |
| `screenshot-terminal-green.png` | 24-hour with mixed-case weekday and ISO date | Exact Terminal defaults: weights shown, seconds hidden, glow effect, all ticks | Large display, centered active backdrop, paired decimal battery and native heart rate; step count and unread notifications |
| `screenshot-light.png` | 24-hour with mixed-case weekday and ISO date | Dark-gray bezel dots on the Light preset | Large display, centered active backdrop, paired decimal battery and native heart rate; step count and unread notifications |
| `screenshot-seconds.png` | 24-hour with day-month and no weekday | Weights hidden, seconds shown, bezel effect, wave ticks | Normal display, lowered active backdrop, paired binary battery and native heart rate; step count, unread notifications, and world clock |
| `screenshot-cyan-12h.png` | 12-hour with ISO date and no weekday | Weights and seconds hidden, no dot effect, single tick | Small display, backdrop hidden, paired hexadecimal battery and native heart rate; sunrise/sunset, world clock, step count, and unread notifications |
| `screenshot-aod.png` | Terminal time with supplemental AOD information hidden | Normal-color patterned dots with weights retained | Step count and unread notifications remain available at low power |

No screenshot uses a battery or heart-rate complication because each active configuration already includes the watch face's native paired readouts. The Terminal and AOD captures intentionally retain the same step-count and unread-notification providers to demonstrate complication continuity at low power. The Seconds capture selects a world clock in its center slot to show populated content without a calendar account; the preset's default provider remains the next event.

Store screenshots use the screenshot-only build's fixed 72 BPM heart rate. Layout diagnostic images use a higher fixed value to verify three-digit clearance. Production builds continue to use the native WFF heart-rate source.

## Closed beta release

Release name:

```text
0.4.0 - Readout and complication layout
```

Release notes:

```text
<en-US>
Layout update for Binary, a configurable binary watch face for Wear OS 7.

- Move heart rate and battery above the lower complications
- Reserve bottom-center space for system activity indicators
- Balance the two-, three-, and four-complication layouts
- Keep the binary time in its established position
</en-US>
```
