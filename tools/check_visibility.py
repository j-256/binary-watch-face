#!/usr/bin/env python3
"""Report reference visibility contracts and palette limits without a device"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__:
    from . import visibility
else:
    import visibility


PREVIEW_TEMPLATE = Path(__file__).with_name("visibility_preview.html")


def report(model: visibility.VisibilityModel) -> dict:
    if __package__:
        from . import generate_watchface as face
    else:
        import generate_watchface as face
    checks = model.checks()
    palettes = []
    for color in face.COLOR_CHOICES:
        for appearance in face.APPEARANCES:
            foreground, background = visibility.rgb(color.colors[0]), visibility.rgb(appearance.colors[0])
            main_contrast = visibility.contrast(foreground, background)
            presets = {}
            for preset in visibility.GRAPH_PRESETS:
                contrasts = model.graph_contrasts(preset, foreground, background)
                floors = model.presets[preset]["minimum_contrast"]
                presets[preset] = {
                    "contrast": contrasts,
                    "below_reference_floor": [role for role, floor in floors.items() if contrasts[role] < floor],
                    "foreground_below_floor": [role for role, floor in floors.items() if main_contrast < floor],
                }
            palettes.append({"color": color.option_id, "appearance": appearance.option_id,
                             "foreground": color.colors[0], "background": appearance.colors[0],
                             "main_contrast": main_contrast, "presets": presets})
    return {
        "schema_version": 1,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "model": model.data,
        "provider_alpha": {role: model.role_alpha(role) for role in visibility.GRAPH_ROLES},
        "face_alpha": {preset: model.face_alpha(preset) for preset in visibility.GRAPH_PRESETS},
        "ambient_alpha": {preset: model.ambient_alpha(preset) for preset in ("dim", "normal", "bright")},
        "ambient_graph_alpha": model.ambient_graph_alpha,
        "bit_weight_alpha": {role: model.weight_alpha(role) for role in ("uniform", "lit", "unlit")},
        "reference_contrast": {preset: model.graph_contrasts(preset, *model.reference) for preset in visibility.GRAPH_PRESETS},
        "palettes": palettes,
        "colors": {color.option_id: color.colors for color in face.COLOR_CHOICES},
        "backgrounds": {appearance.option_id: appearance.colors[0] for appearance in face.APPEARANCES},
        "backdrop_opacity": {choice.option_id: choice.value for choice in face.BACKDROP_OPACITY_CHOICES},
        "limitations": [
            "Predicted solid-core sRGB contrast on a flat background; not measured display luminance or perceived brightness",
            "The shared bitmap has one tint and face opacity; role targets are calibrated only in the reference palette",
            "Anti-aliasing, scaling, overlapping marks, the decimal backdrop and foreground occlusion require rendered verification",
            "Reference floors protect the calibration; permitted user palette combinations can fall below them",
        ],
    }


def render_text(result: dict) -> str:
    lines = [f"{'PASS' if result['passed'] else 'FAIL'} reference visibility calibration",
             "Predicted solid-core contrast on the reference background:",
             "Preset    Face alpha   Trace   Marks   Times"]
    for preset, contrasts in result["reference_contrast"].items():
        lines.append(f"{preset:8} {result['face_alpha'][preset]:10}  {contrasts['trace']:6.2f}"
                     f"  {contrasts['marks']:6.2f}  {contrasts['time_labels']:6.2f}")
    for check in result["checks"]:
        if not check["passed"]:
            lines.append(f"FAIL {check['name']}")
    lines.extend(["", "Palette predictions (foreground / Clear trace):", "Color          Dark          Light"])
    for color in result["colors"]:
        cells = []
        for appearance in ("dark", "light"):
            palette = next(row for row in result["palettes"] if row["color"] == color and row["appearance"] == appearance)
            cells.append(f"{palette['main_contrast']:5.2f} / {palette['presets']['clear']['contrast']['trace']:4.2f}")
        lines.append(f"{color:14} {'  '.join(cells)}")
    lines.extend(["", *result["limitations"], "Use --format html for an interactive preview or --format json for full results."])
    return "\n".join(lines) + "\n"


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check visibility budgets and predict the composited graph contrast",
        epilog="Results go to stdout. Exit status: 0 for passing contracts, 1 for failed contracts, 2 for invalid input. Requires Python 3 only.",
    )
    parser.add_argument("-m", "--model", type=Path, default=visibility.MODEL_PATH, help="visibility JSON source")
    parser.add_argument("-f", "--format", choices=("text", "json", "html"), default="text", help="output format (default: text)")
    parser.add_argument("_positional", nargs="*", help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    if options._positional:
        parser.error(f"unrecognized arguments: {' '.join(options._positional)}")
    try:
        result = report(visibility.load_model(options.model))
        if options.format == "json":
            output = json.dumps(result, indent=2, allow_nan=False) + "\n"
        elif options.format == "html":
            payload = json.dumps(result, allow_nan=False).replace("<", "\\u003c")
            output = PREVIEW_TEMPLATE.read_text(encoding="utf-8").replace("__VISIBILITY_DATA__", payload)
        else:
            output = render_text(result)
    except (OSError, ValueError) as error:
        print(f"Visibility input error: {error}", file=sys.stderr)
        return 2
    print(output, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
