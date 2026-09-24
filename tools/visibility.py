"""Build-time visibility budgets shared by the WFF face and History renderer"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "design/visibility.json"
JAVA_OUTPUT = PROJECT_ROOT / "history/src/main/java/dev/j256/binarywatchface/history/GraphVisibility.java"
MAX_ALPHA = 255
GRAPH_ROLES = ("trace", "marks", "time_labels", "status", "fill", "range")
GRAPH_PRESETS = ("faint", "subtle", "clear")
GEOMETRY_KEYS = (
    "trace_width", "mark_half_length", "mark_stroke_width", "mark_dot_radius",
    "mark_triangle_half_width", "mark_triangle_half_height", "time_label_size",
    "day_label_size", "status_size",
)
RGB = tuple[float, float, float]


def rgb(hex_color: str) -> RGB:
    if not isinstance(hex_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color):
        raise ValueError(f"Expected #RRGGBB color, got {hex_color!r}")
    return tuple(int(hex_color[index:index + 2], 16) for index in (1, 3, 5))


def luminance(color: RGB) -> float:
    channels = (channel / MAX_ALPHA for channel in color)
    linear = (channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels)
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first: RGB, second: RGB) -> float:
    low, high = sorted((luminance(first), luminance(second)))
    return (high + 0.05) / (low + 0.05)


def composite(foreground: RGB, background: RGB, opacity: float) -> RGB:
    if not math.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError("Opacity must be finite and between zero and one")
    # Match the sRGB channel blending in the bitmap/tint pipeline before linearizing
    return tuple(fg * opacity + bg * (1 - opacity) for fg, bg in zip(foreground, background))


def contrast_at(foreground: RGB, background: RGB, *alphas: int) -> float:
    opacity = math.prod(alpha / MAX_ALPHA for alpha in alphas)
    return contrast(composite(foreground, background, opacity), background)


def target_contrast(visibility: float, foreground: RGB, background: RGB) -> float:
    if not math.isfinite(visibility) or not 0 <= visibility <= 1:
        raise ValueError("Visibility must be finite and between zero and one")
    return 1 + visibility * (contrast(foreground, background) - 1)


@lru_cache(maxsize=256)
def solve_alpha(visibility: float, foreground: RGB, background: RGB, *, source_alpha: int = MAX_ALPHA) -> int:
    """Choose the nearest representable contrast across both compositing stages"""
    if isinstance(source_alpha, bool) or not isinstance(source_alpha, int) or not 0 <= source_alpha <= MAX_ALPHA:
        raise ValueError("Source alpha must be an integer from 0 through 255")
    target = target_contrast(visibility, foreground, background)
    # Search all byte values rather than assume every color pair is monotonic
    return min(range(MAX_ALPHA + 1),
               key=lambda alpha: abs(contrast_at(foreground, background, source_alpha, alpha) - target))


def number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number from {low} through {high}")
    return float(value)


def keys(value: object, expected: tuple[str, ...], name: str) -> None:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{name} must contain exactly: {', '.join(expected)}")


@dataclass(frozen=True)
class VisibilityModel:
    data: dict

    @property
    def reference(self) -> tuple[RGB, RGB]:
        return rgb(self.data["reference"]["foreground"]), rgb(self.data["reference"]["background"])

    @property
    def geometry(self) -> dict[str, float]:
        return self.data["graph"]["geometry"]

    @property
    def presets(self) -> dict:
        return self.data["graph"]["presets"]

    def role_alpha(self, role: str) -> int:
        return solve_alpha(self.data["graph"]["roles"][role]["visibility"], *self.reference)

    def face_alpha(self, preset: str) -> int:
        return solve_alpha(self.presets[preset]["trace_visibility"], *self.reference,
                           source_alpha=self.role_alpha("trace"))

    def weight_alpha(self, role: str) -> int:
        return solve_alpha(self.data["bit_weights"][role], *self.reference)

    def ambient_alpha(self, preset: str) -> int:
        ambient = self.data["ambient"]
        return solve_alpha(ambient["main_visibility"][preset], rgb(ambient["reference"]["foreground"]),
                           rgb(ambient["reference"]["background"]))

    @property
    def ambient_graph_alpha(self) -> int:
        return round(self.data["ambient"]["graph_visibility"] * MAX_ALPHA)

    def graph_contrasts(self, preset: str, foreground: RGB, background: RGB) -> dict[str, float]:
        return {role: contrast_at(foreground, background, self.role_alpha(role), self.face_alpha(preset))
                for role in GRAPH_ROLES}

    def checks(self) -> list[dict]:
        checks = []
        previous = 0
        for preset in GRAPH_PRESETS:
            face_alpha = self.face_alpha(preset)
            checks.append({"name": f"{preset}: increasing face opacity", "passed": face_alpha > previous})
            previous = face_alpha
            contrasts = self.graph_contrasts(preset, *self.reference)
            for role, minimum in self.presets[preset]["minimum_contrast"].items():
                checks.append({"name": f"{preset}: {role} contrast", "passed": contrasts[role] >= minimum,
                               "actual": contrasts[role], "minimum": minimum})
                checks.append({"name": f"{preset}: {role} rendered floor within reference floor",
                               "passed": 1 < self.presets[preset]["minimum_rendered_contrast"][role] <= minimum})
            checks.append({"name": f"{preset}: trace < marks < timestamps < foreground",
                           "passed": 1 < contrasts["trace"] < contrasts["marks"] < contrasts["time_labels"]
                           < contrast(*self.reference)})
            checks.append({"name": f"{preset}: fill and range below trace",
                           "passed": max(contrasts["fill"], contrasts["range"]) < contrasts["trace"]})
            # Marks cross the line, so their overlapping center is brighter than either stroke
            trace_opacity = self.role_alpha("trace") / MAX_ALPHA
            mark_opacity = self.role_alpha("marks") / MAX_ALPHA
            overlap = trace_opacity + mark_opacity * (1 - trace_opacity)
            checks.append({"name": f"{preset}: marker intersections below timestamps",
                           "passed": overlap < self.role_alpha("time_labels") / MAX_ALPHA})
        ambient = [self.ambient_alpha(preset) for preset in ("dim", "normal", "bright")]
        weights = [self.weight_alpha(role) for role in ("unlit", "uniform", "lit")]
        checks.append({"name": "bit weights: unlit < uniform < lit", "passed": 0 < weights[0] < weights[1] < weights[2]})
        checks.append({"name": "ambient: dim < normal < bright", "passed": 0 < ambient[0] < ambient[1] < ambient[2]})
        checks.append({"name": "ambient: history hidden", "passed": self.ambient_graph_alpha == 0})
        checks.append({"name": "trace width retains a core at watch size", "passed": self.geometry["trace_width"] >= 2})
        return checks

    def require_calibration(self) -> None:
        failures = [check["name"] for check in self.checks() if not check["passed"]]
        if failures:
            raise ValueError("Visibility calibration failed: " + "; ".join(failures))

    def render_java(self) -> str:
        lines = ["package dev.j256.binarywatchface.history;", "",
                 "// Generated from design/visibility.json by tools/generate_watchface.py",
                 "// Ratios describe reference contrast, not literal alpha or perceived brightness",
                 "final class GraphVisibility {"]
        for role in GRAPH_ROLES:
            lines.append(f"    static final int {role.upper()}_ALPHA = {self.role_alpha(role)};")
        for key, value in self.geometry.items():
            lines.append(f"    static final float {key.upper()} = {float(value)}f;")
        lines.extend(["", "    // Face-side values also exercise the final composite in Android rendering tests"])
        for preset in GRAPH_PRESETS:
            lines.append(f"    static final int FACE_{preset.upper()}_ALPHA = {self.face_alpha(preset)};")
            for role, minimum in self.presets[preset]["minimum_contrast"].items():
                lines.append(f"    static final double {preset.upper()}_{role.upper()}_MIN_CONTRAST = {float(minimum)};")
            for role, minimum in self.presets[preset]["minimum_rendered_contrast"].items():
                lines.append(f"    static final double {preset.upper()}_{role.upper()}_MIN_RENDERED_CONTRAST = {float(minimum)};")
        lines.extend([f'    static final int REFERENCE_FOREGROUND = 0xFF{self.data["reference"]["foreground"][1:]};',
                      f'    static final int REFERENCE_BACKGROUND = 0xFF{self.data["reference"]["background"][1:]};',
                      "", "    private GraphVisibility() {}", "}", ""])
        return "\n".join(lines)


def load_model(path: Path = MODEL_PATH) -> VisibilityModel:
    data = json.loads(path.read_text(encoding="utf-8"))
    keys(data, ("schema_version", "reference", "bit_weights", "graph", "ambient"), "model")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported visibility schema version")
    keys(data["ambient"], ("reference", "main_visibility", "graph_visibility"), "ambient")
    for name, reference in (("reference", data["reference"]), ("ambient.reference", data["ambient"]["reference"])):
        keys(reference, ("foreground", "background"), name)
        for color in reference.values():
            rgb(color)
        if contrast(rgb(reference["foreground"]), rgb(reference["background"])) <= 1:
            raise ValueError(f"{name} must provide visible foreground contrast")
    keys(data["bit_weights"], ("uniform", "lit", "unlit"), "bit_weights")
    for role, value in data["bit_weights"].items():
        number(value, f"bit_weights.{role}", 0, 1)
    graph = data["graph"]
    keys(graph, ("roles", "geometry", "presets"), "graph")
    keys(graph["roles"], GRAPH_ROLES, "graph.roles")
    for role, value in graph["roles"].items():
        keys(value, ("visibility",), f"graph.roles.{role}")
        number(value["visibility"], role, 0, 1)
    keys(graph["geometry"], GEOMETRY_KEYS, "graph.geometry")
    for key, value in graph["geometry"].items():
        number(value, key, 0.1, 50)
    keys(graph["presets"], GRAPH_PRESETS, "graph.presets")
    for preset, value in graph["presets"].items():
        keys(value, ("trace_visibility", "minimum_contrast", "minimum_rendered_contrast"), f"graph.presets.{preset}")
        number(value["trace_visibility"], preset, 0, graph["roles"]["trace"]["visibility"])
        for kind in ("minimum_contrast", "minimum_rendered_contrast"):
            keys(value[kind], ("trace", "marks", "time_labels"), f"{preset}.{kind}")
            for role, minimum in value[kind].items():
                number(minimum, f"{preset}.{role}.{kind}", 1, 21)
    ambient = data["ambient"]
    keys(ambient, ("reference", "main_visibility", "graph_visibility"), "ambient")
    keys(ambient["main_visibility"], ("dim", "normal", "bright"), "ambient.main_visibility")
    for preset, value in ambient["main_visibility"].items():
        number(value, f"ambient.{preset}", 0, 1)
    number(ambient["graph_visibility"], "ambient.graph_visibility", 0, 0)
    return VisibilityModel(data)
