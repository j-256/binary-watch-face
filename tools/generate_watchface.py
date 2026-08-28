#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


WATCH_SIZE = 450
WFF_VERSION = 5
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "watchface/src/main/res/raw/watchface.xml"
XML_HEADER = '<?xml version="1.0" encoding="utf-8"?>\n'

THEME_ID = "themeColor"
COLOR_ACTIVE = f"[CONFIGURATION.{THEME_ID}.0]"
COLOR_INACTIVE = f"[CONFIGURATION.{THEME_ID}.1]"
COLOR_HINT = f"[CONFIGURATION.{THEME_ID}.2]"
COLOR_ACCENT = f"[CONFIGURATION.{THEME_ID}.3]"
COLOR_BLACK = "#000000"

CLOCK_MODE_ID = "clockMode"
SHOW_SECONDS_ID = "showSeconds"
SHOW_HINTS_ID = "showDecimalHints"
SHOW_WEIGHTS_ID = "showBitWeights"
DATE_FORMAT_ID = "dateFormat"
SHOW_BATTERY_ID = "showBattery"
SHOW_TICKS_ID = "showSecondTicks"
COMPLICATION_COUNT_ID = "complicationCount"

HOUR_12_WEIGHTS = (8, 4, 2, 1)
HOUR_24_WEIGHTS = (16, 8, 4, 2, 1)
SIX_BIT_WEIGHTS = (32, 16, 8, 4, 2, 1)
BIT_X_POSITIONS = {
    4: (132, 185, 238, 291),
    5: (106, 159, 212, 265, 318),
    6: (79, 132, 185, 238, 291, 344),
}
DOT_SIZE = 24


@dataclass(frozen=True)
class Theme:
    option_id: str
    label: str
    colors: tuple[str, str, str, str]


@dataclass(frozen=True)
class ComplicationSlotSpec:
    slot_id: int
    name: str
    label: str
    x: int
    y: int
    size: int
    provider: str
    provider_type: str


THEMES = (
    Theme(
        "terminal",
        "theme_terminal",
        ("#39FF88", "#174F2D", "#0B2616", "#9BFFBB"),
    ),
    Theme(
        "monochrome",
        "theme_monochrome",
        ("#FFFFFF", "#4A4A4A", "#1C1C1C", "#D8D8D8"),
    ),
    Theme(
        "amber",
        "theme_amber",
        ("#FFB000", "#593E00", "#291C00", "#FFD166"),
    ),
    Theme(
        "cyan",
        "theme_cyan",
        ("#37E6FF", "#124C55", "#08252A", "#A7F5FF"),
    ),
    Theme(
        "red",
        "theme_red",
        ("#FF4D5A", "#561A20", "#280C0F", "#FFADB4"),
    ),
    Theme(
        "violet",
        "theme_violet",
        ("#C792EA", "#412F4D", "#1E1624", "#E6C6FA"),
    ),
)

COMPLICATION_SLOTS = (
    ComplicationSlotSpec(0, "upper_left", "slot_upper_left", 66, 72, 76, "STEP_COUNT", "SHORT_TEXT"),
    ComplicationSlotSpec(1, "upper_right", "slot_upper_right", 308, 72, 76, "NEXT_EVENT", "SHORT_TEXT"),
    ComplicationSlotSpec(2, "lower_center", "slot_lower_center", 187, 326, 76, "WATCH_BATTERY", "RANGED_VALUE"),
    ComplicationSlotSpec(3, "lower_left", "slot_lower_left", 66, 310, 76, "STEP_COUNT", "SHORT_TEXT"),
    ComplicationSlotSpec(4, "lower_right", "slot_lower_right", 308, 310, 76, "DATE", "SHORT_TEXT"),
)

COMPLICATION_LAYOUTS = {
    "2": (0, 1),
    "3": (0, 1, 2),
    "4": (0, 1, 3, 4),
}


def element(parent: ET.Element, tag: str, **attributes: object) -> ET.Element:
    serialized = {name: str(value) for name, value in attributes.items()}
    return ET.SubElement(parent, tag, serialized)


def add_variant(parent: ET.Element, target: str, value: object) -> None:
    element(parent, "Variant", mode="AMBIENT", target=target, value=value)


def add_screen_reader(parent: ET.Element, text: str, parameters: Iterable[str] = ()) -> None:
    reader = element(parent, "ScreenReader", stringId=text)
    for expression in parameters:
        element(reader, "Parameter", expression=expression)


def add_text(
    parent: ET.Element,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    size: int,
    color: str,
    template: str,
    parameters: Sequence[str] = (),
    alpha: int = 255,
    ambient_alpha: int | None = None,
    weight: str = "NORMAL",
) -> ET.Element:
    part = element(
        parent,
        "PartText",
        x=x,
        y=y,
        width=width,
        height=height,
        alpha=alpha,
    )
    if ambient_alpha is not None:
        add_variant(part, "alpha", ambient_alpha)
    text = element(part, "Text", align="CENTER", ellipsis="TRUE")
    font = element(
        text,
        "Font",
        family="SYNC_TO_DEVICE",
        size=size,
        weight=weight,
        color=color,
    )
    if parameters:
        template_element = element(font, "Template")
        template_element.text = template
        for expression in parameters:
            element(template_element, "Parameter", expression=expression)
    else:
        font.text = template
    return part


def add_empty_group(parent: ET.Element, name: str) -> ET.Element:
    return element(parent, "Group", name=name, x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE, alpha=0)


def add_boolean_group(
    parent: ET.Element,
    setting_id: str,
    name: str,
    builder: Callable[[ET.Element], None],
) -> None:
    configuration = element(parent, "BooleanConfiguration", id=setting_id)
    option = element(configuration, "BooleanOption", id="TRUE")
    group = element(option, "Group", name=name, x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    builder(group)


def add_user_configurations(root: ET.Element) -> None:
    configurations = element(root, "UserConfigurations")

    colors = element(
        configurations,
        "ColorConfiguration",
        id=THEME_ID,
        displayName="setting_theme",
        screenReaderText="setting_theme",
        defaultValue="terminal",
    )
    for theme in THEMES:
        element(
            colors,
            "ColorOption",
            id=theme.option_id,
            displayName=theme.label,
            screenReaderText=theme.label,
            colors=" ".join(theme.colors),
        )

    clock_mode = element(
        configurations,
        "ListConfiguration",
        id=CLOCK_MODE_ID,
        displayName="setting_clock_mode",
        screenReaderText="setting_clock_mode",
        defaultValue="system",
    )
    for option_id, label in (
        ("system", "clock_mode_system"),
        ("12", "clock_mode_12"),
        ("24", "clock_mode_24"),
    ):
        element(clock_mode, "ListOption", id=option_id, displayName=label, screenReaderText=label)

    for setting_id, label, default in (
        (SHOW_SECONDS_ID, "setting_show_seconds", "FALSE"),
        (SHOW_HINTS_ID, "setting_show_decimal_hints", "TRUE"),
        (SHOW_WEIGHTS_ID, "setting_show_bit_weights", "TRUE"),
        (SHOW_BATTERY_ID, "setting_show_battery", "TRUE"),
        (SHOW_TICKS_ID, "setting_show_second_ticks", "TRUE"),
    ):
        element(
            configurations,
            "BooleanConfiguration",
            id=setting_id,
            displayName=label,
            screenReaderText=label,
            defaultValue=default,
        )

    date_format = element(
        configurations,
        "ListConfiguration",
        id=DATE_FORMAT_ID,
        displayName="setting_date_format",
        screenReaderText="setting_date_format",
        defaultValue="friendly",
    )
    for option_id, label in (
        ("friendly", "date_format_friendly"),
        ("iso", "date_format_iso"),
        ("unix", "date_format_unix"),
        ("off", "date_format_off"),
    ):
        element(date_format, "ListOption", id=option_id, displayName=label, screenReaderText=label)

    complication_count = element(
        configurations,
        "ListConfiguration",
        id=COMPLICATION_COUNT_ID,
        displayName="setting_complication_count",
        screenReaderText="setting_complication_count",
        defaultValue="2",
    )
    for option_id, slot_ids in COMPLICATION_LAYOUTS.items():
        label = f"complication_count_{option_id}"
        element(
            complication_count,
            "ListOption",
            id=option_id,
            displayName=label,
            screenReaderText=label,
            complicationSlotIds=" ".join(str(slot_id) for slot_id in slot_ids),
        )


def add_tick_ring(scene: ET.Element) -> None:
    def build(group: ET.Element) -> None:
        add_variant(group, "alpha", 0)
        for second in range(60):
            major = second % 5 == 0
            width = 3 if major else 2
            height = 12 if major else 7
            part = element(
                group,
                "PartDraw",
                x=0,
                y=0,
                width=WATCH_SIZE,
                height=WATCH_SIZE,
                angle=second * 6,
                pivotX=0.5,
                pivotY=0.5,
                alpha=190 if major else 120,
            )
            rectangle = element(
                part,
                "RoundRectangle",
                x=(WATCH_SIZE - width) / 2,
                y=13,
                width=width,
                height=height,
                cornerRadiusX=width / 2,
                cornerRadiusY=width / 2,
            )
            element(rectangle, "Fill", color=COLOR_INACTIVE)

        current = element(
            group,
            "PartDraw",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
            pivotX=0.5,
            pivotY=0.5,
        )
        marker = element(
            current,
            "RoundRectangle",
            x=222,
            y=11,
            width=6,
            height=16,
            cornerRadiusX=3,
            cornerRadiusY=3,
        )
        element(marker, "Fill", color=COLOR_ACCENT)
        element(current, "Transform", target="angle", value="[SECOND] * 6")

    add_boolean_group(scene, SHOW_TICKS_ID, "second_ticks", build)


def add_binary_dot(parent: ET.Element, x: int, y: int, source: str, bit: int) -> None:
    outline = element(parent, "PartDraw", x=x, y=y, width=DOT_SIZE, height=DOT_SIZE)
    add_variant(outline, "alpha", 96)
    outline_ellipse = element(outline, "Ellipse", x=1, y=1, width=DOT_SIZE - 2, height=DOT_SIZE - 2)
    element(outline_ellipse, "Stroke", color=COLOR_INACTIVE, thickness=2)

    active = element(parent, "PartDraw", x=x, y=y, width=DOT_SIZE, height=DOT_SIZE)
    active_ellipse = element(active, "Ellipse", x=1, y=1, width=DOT_SIZE - 2, height=DOT_SIZE - 2)
    element(active_ellipse, "Fill", color=COLOR_ACTIVE)
    element(
        active,
        "Transform",
        target="alpha",
        value=f"floor(({source}) / {bit}) % 2 == 1 ? 255 : 0",
    )


def add_binary_row(
    parent: ET.Element,
    *,
    name: str,
    source: str,
    weights: Sequence[int],
    y: int,
) -> None:
    positions = BIT_X_POSITIONS[len(weights)]

    def build_hint(group: ET.Element) -> None:
        add_variant(group, "alpha", 0)
        add_text(
            group,
            x=75,
            y=y - 43,
            width=300,
            height=94,
            size=82,
            color=COLOR_HINT,
            template="%d",
            parameters=(source,),
            weight="EXTRA_BOLD",
        )

    add_boolean_group(parent, SHOW_HINTS_ID, f"{name}_decimal_hint", build_hint)

    def build_weights(group: ET.Element) -> None:
        add_variant(group, "alpha", 0)
        for x, bit in zip(positions, weights):
            add_text(
                group,
                x=x - 7,
                y=y - 23,
                width=DOT_SIZE + 14,
                height=18,
                size=13,
                color=COLOR_ACCENT,
                template=str(bit),
                alpha=210,
            )

    add_boolean_group(parent, SHOW_WEIGHTS_ID, f"{name}_bit_weights", build_weights)

    for x, bit in zip(positions, weights):
        add_binary_dot(parent, x, y, source, bit)


def add_clock_layout(
    parent: ET.Element,
    *,
    name: str,
    hour_source: str,
    hour_weights: Sequence[int],
    include_seconds: bool,
) -> None:
    group = element(parent, "Group", name=name, x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_variant(group, "alpha", 200)

    if include_seconds:
        rows = (
            ("hour", hour_source, hour_weights, 148),
            ("minute", "[MINUTE]", SIX_BIT_WEIGHTS, 210),
            ("second", "[SECOND]", SIX_BIT_WEIGHTS, 272),
        )
        add_screen_reader(group, "Time is %d:%02d:%02d", (hour_source, "[MINUTE]", "[SECOND]"))
    else:
        rows = (
            ("hour", hour_source, hour_weights, 174),
            ("minute", "[MINUTE]", SIX_BIT_WEIGHTS, 236),
        )
        add_screen_reader(group, "Time is %d:%02d", (hour_source, "[MINUTE]"))

    for row_name, source, weights, y in rows:
        add_binary_row(
            group,
            name=f"{name}_{row_name}",
            source=source,
            weights=weights,
            y=y,
        )


def add_clock_variant(
    parent: ET.Element,
    *,
    name: str,
    hour_source: str,
    hour_weights: Sequence[int],
) -> None:
    seconds = element(parent, "BooleanConfiguration", id=SHOW_SECONDS_ID)
    on = element(seconds, "BooleanOption", id="TRUE")
    add_clock_layout(
        on,
        name=f"{name}_with_seconds",
        hour_source=hour_source,
        hour_weights=hour_weights,
        include_seconds=True,
    )
    off = element(seconds, "BooleanOption", id="FALSE")
    add_clock_layout(
        off,
        name=f"{name}_without_seconds",
        hour_source=hour_source,
        hour_weights=hour_weights,
        include_seconds=False,
    )


def add_clock(scene: ET.Element) -> None:
    clock_mode = element(scene, "ListConfiguration", id=CLOCK_MODE_ID)

    system = element(clock_mode, "ListOption", id="system")
    condition = element(system, "Condition")
    expressions = element(condition, "Expressions")
    expression = element(expressions, "Expression", name="system_uses_24_hour")
    expression.text = "[IS_24_HOUR_MODE]"
    compare = element(condition, "Compare", expression="system_uses_24_hour")
    system_24 = element(compare, "Group", name="system_24_hour", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_clock_variant(
        system_24,
        name="system_24_hour_clock",
        hour_source="[HOUR_0_23]",
        hour_weights=HOUR_24_WEIGHTS,
    )
    default = element(condition, "Default")
    system_12 = element(default, "Group", name="system_12_hour", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_clock_variant(
        system_12,
        name="system_12_hour_clock",
        hour_source="[HOUR_1_12]",
        hour_weights=HOUR_12_WEIGHTS,
    )

    twelve = element(clock_mode, "ListOption", id="12")
    twelve_group = element(twelve, "Group", name="forced_12_hour", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_clock_variant(
        twelve_group,
        name="forced_12_hour_clock",
        hour_source="[HOUR_1_12]",
        hour_weights=HOUR_12_WEIGHTS,
    )

    twenty_four = element(clock_mode, "ListOption", id="24")
    twenty_four_group = element(
        twenty_four,
        "Group",
        name="forced_24_hour",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
    )
    add_clock_variant(
        twenty_four_group,
        name="forced_24_hour_clock",
        hour_source="[HOUR_0_23]",
        hour_weights=HOUR_24_WEIGHTS,
    )


def add_date(scene: ET.Element) -> None:
    date = element(scene, "ListConfiguration", id=DATE_FORMAT_ID)

    friendly = element(date, "ListOption", id="friendly")
    friendly_text = add_text(
        friendly,
        x=105,
        y=36,
        width=240,
        height=28,
        size=20,
        color=COLOR_ACTIVE,
        template="%s %02d %s",
        parameters=("[DAY_OF_WEEK_S]", "[DAY]", "[MONTH_S]"),
        ambient_alpha=160,
    )
    add_screen_reader(friendly_text, "%s %d %s", ("[DAY_OF_WEEK_S]", "[DAY]", "[MONTH_S]"))

    iso = element(date, "ListOption", id="iso")
    iso_text = add_text(
        iso,
        x=105,
        y=36,
        width=240,
        height=28,
        size=20,
        color=COLOR_ACTIVE,
        template="%04d-%02d-%02d",
        parameters=("[YEAR]", "[MONTH]", "[DAY]"),
        ambient_alpha=160,
    )
    add_screen_reader(iso_text, "Date %d-%02d-%02d", ("[YEAR]", "[MONTH]", "[DAY]"))

    unix = element(date, "ListOption", id="unix")
    unix_text = add_text(
        unix,
        x=105,
        y=36,
        width=240,
        height=28,
        size=18,
        color=COLOR_ACTIVE,
        template="%d",
        parameters=("floor([UTC_TIMESTAMP] / 1000)",),
        ambient_alpha=160,
    )
    add_screen_reader(unix_text, "Unix time %d", ("floor([UTC_TIMESTAMP] / 1000)",))

    off = element(date, "ListOption", id="off")
    add_empty_group(off, "date_hidden")


def add_battery(scene: ET.Element) -> None:
    def build(group: ET.Element) -> None:
        text = add_text(
            group,
            x=155,
            y=394,
            width=140,
            height=27,
            size=20,
            color=COLOR_ACTIVE,
            template="%d%%",
            parameters=("[BATTERY_PERCENT]",),
            ambient_alpha=160,
        )
        add_screen_reader(text, "Battery %d percent", ("[BATTERY_PERCENT]",))

    add_boolean_group(scene, SHOW_BATTERY_ID, "battery", build)


def add_complication_shell(parent: ET.Element, size: int) -> None:
    draw = element(parent, "PartDraw", x=0, y=0, width=size, height=size)
    background = element(draw, "Ellipse", x=2, y=2, width=size - 4, height=size - 4)
    element(background, "Fill", color=COLOR_BLACK)
    outline = element(draw, "Ellipse", x=2, y=2, width=size - 4, height=size - 4)
    element(outline, "Stroke", color=COLOR_INACTIVE, thickness=2)


def add_short_text_complication(slot: ET.Element, size: int) -> None:
    complication = element(slot, "Complication", type="SHORT_TEXT")
    add_complication_shell(complication, size)

    condition = element(complication, "Condition")
    expressions = element(condition, "Expressions")
    has_icon = element(expressions, "Expression", name="short_text_has_icon")
    has_icon.text = "[COMPLICATION.MONOCHROMATIC_IMAGE] != null"

    compare = element(condition, "Compare", expression="short_text_has_icon")
    with_icon = element(compare, "Group", name="short_text_with_icon", x=0, y=0, width=size, height=size)
    icon = element(with_icon, "PartImage", x=26, y=10, width=24, height=24, tintColor=COLOR_ACCENT)
    element(icon, "Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")
    add_text(
        with_icon,
        x=7,
        y=39,
        width=size - 14,
        height=24,
        size=17,
        color=COLOR_ACTIVE,
        template="%s",
        parameters=("[COMPLICATION.TEXT]",),
    )

    default = element(condition, "Default")
    add_text(
        default,
        x=7,
        y=25,
        width=size - 14,
        height=28,
        size=20,
        color=COLOR_ACTIVE,
        template="%s",
        parameters=("[COMPLICATION.TEXT]",),
    )


def add_image_complications(slot: ET.Element, size: int) -> None:
    small = element(slot, "Complication", type="SMALL_IMAGE")
    add_complication_shell(small, size)
    small_image = element(small, "PartImage", x=14, y=14, width=size - 28, height=size - 28)
    element(small_image, "Image", resource="[COMPLICATION.SMALL_IMAGE]")

    monochromatic = element(slot, "Complication", type="MONOCHROMATIC_IMAGE")
    add_complication_shell(monochromatic, size)
    monochromatic_image = element(
        monochromatic,
        "PartImage",
        x=18,
        y=18,
        width=size - 36,
        height=size - 36,
        tintColor=COLOR_ACTIVE,
    )
    element(monochromatic_image, "Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")


def add_ranged_value_complication(slot: ET.Element, size: int) -> None:
    complication = element(slot, "Complication", type="RANGED_VALUE")
    add_complication_shell(complication, size)

    draw = element(complication, "PartDraw", x=0, y=0, width=size, height=size)
    background = element(
        draw,
        "Arc",
        centerX=size / 2,
        centerY=size / 2,
        width=size - 12,
        height=size - 12,
        startAngle=-150,
        endAngle=150,
    )
    element(background, "Stroke", color=COLOR_INACTIVE, thickness=4, cap="ROUND")
    progress = element(
        draw,
        "Arc",
        centerX=size / 2,
        centerY=size / 2,
        width=size - 12,
        height=size - 12,
        startAngle=-150,
        endAngle=150,
    )
    element(progress, "Stroke", color=COLOR_ACTIVE, thickness=4, cap="ROUND")
    element(
        progress,
        "Transform",
        target="endAngle",
        value=(
            "-150 + (((clamp([COMPLICATION.RANGED_VALUE_VALUE], "
            "[COMPLICATION.RANGED_VALUE_MIN], [COMPLICATION.RANGED_VALUE_MAX]) - "
            "[COMPLICATION.RANGED_VALUE_MIN]) / ([COMPLICATION.RANGED_VALUE_MAX] - "
            "[COMPLICATION.RANGED_VALUE_MIN])) * 300)"
        ),
    )

    condition = element(complication, "Condition")
    expressions = element(condition, "Expressions")
    has_text = element(expressions, "Expression", name="ranged_value_has_text")
    has_text.text = "[COMPLICATION.TEXT] != null"
    compare = element(condition, "Compare", expression="ranged_value_has_text")
    add_text(
        compare,
        x=10,
        y=25,
        width=size - 20,
        height=27,
        size=18,
        color=COLOR_ACCENT,
        template="%s",
        parameters=("[COMPLICATION.TEXT]",),
    )
    default = element(condition, "Default")
    add_text(
        default,
        x=10,
        y=25,
        width=size - 20,
        height=27,
        size=18,
        color=COLOR_ACCENT,
        template="%.0f",
        parameters=("[COMPLICATION.RANGED_VALUE_VALUE]",),
    )


def add_complications(scene: ET.Element) -> None:
    supported = "SHORT_TEXT MONOCHROMATIC_IMAGE SMALL_IMAGE RANGED_VALUE EMPTY"
    for specification in COMPLICATION_SLOTS:
        slot = element(
            scene,
            "ComplicationSlot",
            x=specification.x,
            y=specification.y,
            width=specification.size,
            height=specification.size,
            slotId=specification.slot_id,
            name=specification.name,
            displayName=specification.label,
            supportedTypes=supported,
            isCustomizable="TRUE",
        )
        add_variant(slot, "alpha", 0)
        element(
            slot,
            "DefaultProviderPolicy",
            defaultSystemProvider=specification.provider,
            defaultSystemProviderType=specification.provider_type,
        )
        element(
            slot,
            "BoundingOval",
            x=0,
            y=0,
            width=specification.size,
            height=specification.size,
            outlinePadding=2,
        )
        add_short_text_complication(slot, specification.size)
        add_image_complications(slot, specification.size)
        add_ranged_value_complication(slot, specification.size)
        element(slot, "Complication", type="EMPTY")


def build_watchface() -> ET.Element:
    root = ET.Element("WatchFace", {"width": str(WATCH_SIZE), "height": str(WATCH_SIZE), "clipShape": "CIRCLE"})
    root.append(ET.Comment(f" Generated by tools/generate_watchface.py for WFF {WFF_VERSION} "))
    element(root, "Metadata", key="CLOCK_TYPE", value="DIGITAL")
    element(root, "Metadata", key="PREVIEW_TIME", value="15:23:37")
    add_user_configurations(root)

    scene = element(root, "Scene", backgroundColor=COLOR_BLACK)
    add_tick_ring(scene)
    add_date(scene)
    add_clock(scene)
    add_battery(scene)
    add_complications(scene)
    return root


def render_watchface() -> str:
    root = build_watchface()
    ET.indent(root, space="    ")
    return XML_HEADER + ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Binary Watch Face WFF definition",
        epilog="Exit status: 0 for success, 1 when --check finds stale output, and 2 for invalid usage.",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="fail when the generated definition differs from the output file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="write to this path instead of the project watchface.xml",
    )
    parser.add_argument("_positional", nargs="*", help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    if options._positional:
        parser.error(f"unrecognized arguments: {' '.join(options._positional)}")
    del options._positional
    return options


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments if arguments is not None else sys.argv[1:])
    generated = render_watchface()
    output = options.output

    if options.check:
        if not output.exists() or output.read_text(encoding="utf-8") != generated:
            print(f"Generated watch face differs from {output}", file=sys.stderr)
            return 1
        print(f"Generated watch face is up to date: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
