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
- Pick independent dot, text, and decimal-backdrop colors
- Adjust backdrop opacity, size, position, and active/AOD visibility
- Choose tiny through huge display sizes
- Select glow, bezel, and tick effects
- Use ISO date or several regional date formats
- Show the watch battery in decimal, hexadecimal, or binary
- Configure two, three, or four complications

ALWAYS-ON DISPLAY
Keep the selected color with a dense, low-power dot pattern. Choose dim, normal, or bright rendering. Date, weekday, watch battery, and the decimal backdrop can each be included or omitted from the always-on display.

PRIVATE BY DESIGN
Binary is a resource-only Watch Face Format watch face. It has no executable app code, network access, analytics, advertising, accounts, or data collection. Time, battery, settings, and complication data remain on your watch.

Requires Wear OS 7.
```

## Assets

- `app-icon.png`: 512 x 512 app icon derived from the terminal-green watch-face capture
- `feature-graphic.png`: 1024 x 500 feature graphic using the terminal-green watch-face capture

| Screenshot | Clock and date | Binary styling | Layout and data |
| --- | --- | --- | --- |
| `screenshot-terminal-green.png` | 24-hour with uppercase dotted day-month and weekday | Weights shown, seconds hidden, glow effect, all ticks | Large display, centered active backdrop, decimal battery, two complications |
| `screenshot-seconds.png` | 24-hour with day-month and no weekday | Weights hidden, seconds shown, bezel effect, wave ticks | Normal display, lowered active backdrop, binary battery, three complications |
| `screenshot-cyan-12h.png` | 12-hour with ISO date and no weekday | Weights and seconds hidden, no dot effect, single tick | Small display, backdrop hidden, hexadecimal battery, four complications |

The screenshots use notification, heart-rate, sunrise/sunset, and app-shortcut complications. None uses a battery complication because each configuration already includes the watch face's native battery readout.

## Closed beta release

Release name:

```text
0.1.0 - Closed beta 1
```

Release notes:

```text
<en-US>
First closed beta of Binary, a configurable binary watch face for Wear OS 7.

- Display time in 12- or 24-hour true binary
- Customize colors, size, effects, ticks, date, battery, and backdrop
- Choose two, three, or four complications
- Use a configurable low-power always-on display
</en-US>
```
