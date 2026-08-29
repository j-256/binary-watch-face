#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
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

DOT_COLOR_ID = "dotColor"
TEXT_COLOR_ID = "textColor"
APPEARANCE_ID = "appearance"
BACKDROP_COLOR_ID = "backdropColor"
BACKDROP_OPACITY_ID = "backdropOpacity"
BACKDROP_LAYOUT_ID = "backdropLayout"
BACKDROP_VISIBILITY_ID = "backdropVisibility"
COLOR_DOT_ACTIVE = f"[CONFIGURATION.{DOT_COLOR_ID}.0]"
COLOR_DOT_INACTIVE = f"[CONFIGURATION.{DOT_COLOR_ID}.1]"
COLOR_DOT_AMBIENT = f"[CONFIGURATION.{DOT_COLOR_ID}.2]"
COLOR_TEXT_ACTIVE = f"[CONFIGURATION.{TEXT_COLOR_ID}.0]"
COLOR_TEXT_INACTIVE = f"[CONFIGURATION.{TEXT_COLOR_ID}.1]"
COLOR_TEXT_AMBIENT = f"[CONFIGURATION.{TEXT_COLOR_ID}.2]"
COLOR_BACKGROUND = f"[CONFIGURATION.{APPEARANCE_ID}.0]"
COLOR_BACKDROP = f"[CONFIGURATION.{BACKDROP_COLOR_ID}.0]"
COLOR_COMPLICATION_BACKGROUND = f"[CONFIGURATION.{APPEARANCE_ID}.2]"
COLOR_AMBIENT_BACKDROP = f"[CONFIGURATION.{APPEARANCE_ID}.3]"
COLOR_BLACK = "#000000"
COLOR_AMBIENT_MONO = "#FFFFFF"
COLOR_BACKDROP_DARK = "#242424"
COLOR_BACKDROP_LIGHT = "#E0E0E0"
AMBIENT_DITHER_ROW_COUNT = 7
AMBIENT_DITHER_DASH_MULTIPLIER = 2
AMBIENT_DITHER_GAP = 1

CLOCK_MODE_ID = "clockMode"
SIZE_ID = "displaySize"
DOT_EFFECT_ID = "dotEffect"
SHOW_SECONDS_ID = "showSeconds"
SHOW_WEIGHTS_ID = "showBitWeights"
DATE_FORMAT_ID = "dateFormat"
SHOW_WEEKDAY_ID = "showWeekday"
UPPERCASE_DATE_ID = "uppercaseDate"
AMBIENT_INFO_ID = "ambientInfo"
AMBIENT_COLOR_ID = "ambientColor"
BATTERY_DISPLAY_ID = "batteryDisplay"
TICK_STYLE_ID = "tickStyle"
COMPLICATION_COUNT_ID = "complicationCount"

CONFIGURATION_HIGHLIGHTS = {
    DOT_COLOR_ID: "@drawable/highlight_dots",
    TEXT_COLOR_ID: "@drawable/highlight_text",
    APPEARANCE_ID: "@drawable/highlight_full_face",
    BACKDROP_COLOR_ID: "@drawable/highlight_clock",
    BACKDROP_OPACITY_ID: "@drawable/highlight_clock",
    BACKDROP_LAYOUT_ID: "@drawable/highlight_clock",
    BACKDROP_VISIBILITY_ID: "@drawable/highlight_clock",
    SIZE_ID: "@drawable/highlight_clock",
    CLOCK_MODE_ID: "@drawable/highlight_hour_row",
    DOT_EFFECT_ID: "@drawable/highlight_dots",
    SHOW_SECONDS_ID: "@drawable/highlight_seconds",
    SHOW_WEIGHTS_ID: "@drawable/highlight_weights",
    DATE_FORMAT_ID: "@drawable/highlight_date",
    SHOW_WEEKDAY_ID: "@drawable/highlight_date",
    UPPERCASE_DATE_ID: "@drawable/highlight_date",
    AMBIENT_INFO_ID: "@drawable/highlight_date_battery",
    AMBIENT_COLOR_ID: "@drawable/highlight_full_face",
    BATTERY_DISPLAY_ID: "@drawable/highlight_battery",
    TICK_STYLE_ID: "@drawable/highlight_ticks",
    COMPLICATION_COUNT_ID: "@drawable/highlight_complications",
}

BINARY_SETTINGS = (
    (SHOW_SECONDS_ID, "setting_show_seconds", "FALSE", "seconds_shown", "seconds_hidden"),
    (SHOW_WEIGHTS_ID, "setting_show_bit_weights", "TRUE", "bit_weights_shown", "bit_weights_hidden"),
    (SHOW_WEEKDAY_ID, "setting_show_weekday", "TRUE", "weekday_shown", "weekday_hidden"),
    (UPPERCASE_DATE_ID, "setting_uppercase_date", "FALSE", "date_case_uppercase", "date_case_mixed"),
)

HOUR_12_WEIGHTS = (8, 4, 2, 1)
HOUR_24_WEIGHTS = (16, 8, 4, 2, 1)
SIX_BIT_WEIGHTS = (32, 16, 8, 4, 2, 1)
REFERENCE_ROW_SPAN = 188
REFERENCE_DOT_SIZE = 23
DECIMAL_BACKDROP_SIZE = 240
BATTERY_READOUT_Y = 390
SIDE_COMPLICATION_SIZE = 84
SIDE_COMPLICATION_Y = (WATCH_SIZE - SIDE_COMPLICATION_SIZE) // 2
CLOCK_ROW_LAYOUT = {
    False: (150, 210),
    True: (106, 162, 218),
}


@dataclass(frozen=True)
class ColorChoice:
    option_id: str
    label: str
    colors: tuple[str, str, str]


@dataclass(frozen=True)
class Appearance:
    option_id: str
    label: str
    colors: tuple[str, str, str, str]


@dataclass(frozen=True)
class SizeChoice:
    option_id: str
    label: str
    scale: float


@dataclass(frozen=True)
class NumericChoice:
    option_id: str
    label: str
    value: int | float


@dataclass(frozen=True)
class AmbientAppearanceChoice:
    option_id: str
    label: str
    alpha: int
    uses_color: bool


@dataclass(frozen=True)
class BackdropLayoutChoice:
    option_id: str
    label: str
    scale: float
    y_offset: int


@dataclass(frozen=True)
class DateFormatSpec:
    option_id: str
    label: str
    template: str
    parameters: tuple[str, ...]
    size: int = 20


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


COLOR_CHOICES = (
    ColorChoice("terminal", "color_terminal", ("#28FE14", "#0C4A06", "#28FE14")),
    ColorChoice("white", "color_white", ("#FFFFFF", "#4A4A4A", "#FFFFFF")),
    ColorChoice("yellow", "color_yellow", ("#FFEA00", "#4D4600", "#FFF176")),
    ColorChoice("amber", "color_amber", ("#FFB000", "#593E00", "#FFD166")),
    ColorChoice("orange", "color_orange", ("#FF8C00", "#572F00", "#FFCC80")),
    ColorChoice("red", "color_red", ("#FF3B30", "#571410", "#FF9B94")),
    ColorChoice("pink", "color_pink", ("#FF2D95", "#571034", "#FF9BC9")),
    ColorChoice("violet", "color_violet", ("#C792EA", "#412F4D", "#E6C6FA")),
    ColorChoice("purple", "color_purple", ("#9C6ADE", "#35244B", "#D4B8F5")),
    ColorChoice("blue", "color_blue", ("#448AFF", "#172F57", "#9EC5FF")),
    ColorChoice("cyan", "color_cyan", ("#00E5FF", "#004E57", "#8AF4FF")),
    ColorChoice("lime", "color_lime", ("#99CC00", "#344500", "#D0F06B")),
    ColorChoice("green", "color_green", ("#00C853", "#00441C", "#7BE6A8")),
    ColorChoice("light_gray", "color_light_gray", ("#BDBDBD", "#404040", "#E0E0E0")),
    ColorChoice("medium_gray", "color_medium_gray", ("#757575", "#282828", "#BDBDBD")),
    ColorChoice("dark_gray", "color_dark_gray", ("#424242", "#171717", "#8A8A8A")),
)

APPEARANCES = (
    Appearance("dark", "appearance_dark", ("#000000", COLOR_BACKDROP_DARK, "#000000", "#666666")),
    Appearance("light", "appearance_light", ("#F4F4F4", COLOR_BACKDROP_LIGHT, "#F4F4F4", "#666666")),
)

SIZE_CHOICES = (
    SizeChoice("tiny", "size_tiny", 0.8),
    SizeChoice("small", "size_small", 0.9),
    SizeChoice("normal", "size_normal", 1.0),
    SizeChoice("large", "size_large", 1.1),
    SizeChoice("huge", "size_huge", 1.2),
)
DEFAULT_SIZE_ID = "large"
BASE_SIZE_ID = "normal"
DISPLAY_SIZE_VALUES = tuple(
    (choice.option_id, choice.scale) for choice in SIZE_CHOICES
)

DEFAULT_BACKDROP_COLOR_ID = "medium_gray"
DEFAULT_BACKDROP_OPACITY_ID = "30"
DEFAULT_BACKDROP_LAYOUT_ID = "normal_centered"
DEFAULT_BACKDROP_VISIBILITY_ID = "active"
BACKDROP_OPACITY_CHOICES = (
    NumericChoice("5", "backdrop_opacity_5", 13),
    NumericChoice("10", "backdrop_opacity_10", 26),
    NumericChoice("15", "backdrop_opacity_15", 38),
    NumericChoice("30", "backdrop_opacity_30", 77),
    NumericChoice("50", "backdrop_opacity_50", 128),
    NumericChoice("75", "backdrop_opacity_75", 191),
    NumericChoice("100", "backdrop_opacity_100", 255),
)
BACKDROP_LAYOUT_CHOICES = (
    BackdropLayoutChoice("small_raised", "backdrop_layout_small_raised", 0.8, -24),
    BackdropLayoutChoice("normal_raised", "backdrop_layout_normal_raised", 1.0, -24),
    BackdropLayoutChoice("large_raised", "backdrop_layout_large_raised", 1.2, -24),
    BackdropLayoutChoice("small_centered", "backdrop_layout_small_centered", 0.8, 0),
    BackdropLayoutChoice("normal_centered", "backdrop_layout_normal_centered", 1.0, 0),
    BackdropLayoutChoice("large_centered", "backdrop_layout_large_centered", 1.2, 0),
    BackdropLayoutChoice("small_lowered", "backdrop_layout_small_lowered", 0.8, 24),
    BackdropLayoutChoice("normal_lowered", "backdrop_layout_normal_lowered", 1.0, 24),
    BackdropLayoutChoice("large_lowered", "backdrop_layout_large_lowered", 1.2, 24),
)
BACKDROP_OPACITY_VALUES = tuple(
    (choice.option_id, choice.value) for choice in BACKDROP_OPACITY_CHOICES
)
BACKDROP_LAYOUT_SCALE_VALUES = tuple(
    (choice.option_id, choice.scale) for choice in BACKDROP_LAYOUT_CHOICES
)
BACKDROP_LAYOUT_Y_VALUES = tuple(
    (choice.option_id, choice.y_offset) for choice in BACKDROP_LAYOUT_CHOICES
)
BACKDROP_VISIBILITY_OPTIONS = (
    ("off", "backdrop_visibility_off"),
    ("active", "backdrop_visibility_active"),
    ("ambient", "backdrop_visibility_ambient"),
    ("both", "backdrop_visibility_both"),
)
AMBIENT_INFO_OPTIONS = (
    ("off", "ambient_info_off"),
    ("date", "ambient_info_date"),
    ("date_weekday", "ambient_info_date_weekday"),
    ("battery", "ambient_info_battery"),
    ("date_battery", "ambient_info_date_battery"),
    ("date_weekday_battery", "ambient_info_date_weekday_battery"),
)
DEFAULT_AMBIENT_APPEARANCE_ID = "TRUE"
AMBIENT_APPEARANCE_CHOICES = (
    AmbientAppearanceChoice("dim_color", "ambient_appearance_dim_color", 128, True),
    AmbientAppearanceChoice("TRUE", "ambient_appearance_normal_color", 192, True),
    AmbientAppearanceChoice("bright_color", "ambient_appearance_bright_color", 255, True),
    AmbientAppearanceChoice("dim_mono", "ambient_appearance_dim_mono", 128, False),
    AmbientAppearanceChoice("FALSE", "ambient_appearance_normal_mono", 192, False),
    AmbientAppearanceChoice("bright_mono", "ambient_appearance_bright_mono", 255, False),
)
AMBIENT_BRIGHTNESS_VALUES = tuple(
    (choice.option_id, choice.alpha) for choice in AMBIENT_APPEARANCE_CHOICES
)
AMBIENT_COLOR_OPTION_IDS = tuple(
    choice.option_id for choice in AMBIENT_APPEARANCE_CHOICES if choice.uses_color
)
AMBIENT_DATE_OPTION_IDS = (
    "date",
    "date_weekday",
    "date_battery",
    "date_weekday_battery",
)
AMBIENT_WEEKDAY_OPTION_IDS = ("date_weekday", "date_weekday_battery")
AMBIENT_BATTERY_OPTION_IDS = ("battery", "date_battery", "date_weekday_battery")
BACKDROP_ACTIVE_OPTION_IDS = ("active", "both")
BACKDROP_AMBIENT_OPTION_IDS = ("ambient", "both")

DATE_FORMATS = (
    DateFormatSpec("month_day", "date_format_month_day", "%s %02d", ("[MONTH_S]", "[DAY]")),
    DateFormatSpec(
        "month_day_numeric",
        "date_format_month_day_numeric",
        "%02d/%02d",
        ("[MONTH]", "[DAY]"),
    ),
    DateFormatSpec("day_month", "date_format_day_month", "%02d %s", ("[DAY]", "[MONTH_S]")),
    DateFormatSpec(
        "day_month_numeric",
        "date_format_day_month_numeric",
        "%02d/%02d",
        ("[DAY]", "[MONTH]"),
    ),
    DateFormatSpec("day_month_dots", "date_format_day_month_dots", "%02d.%02d", ("[DAY]", "[MONTH]")),
    DateFormatSpec("iso", "date_format_iso", "%04d-%02d-%02d", ("[YEAR]", "[MONTH]", "[DAY]")),
    DateFormatSpec("unix", "date_format_unix", "%d", ("floor([UTC_TIMESTAMP] / 1000)",), 18),
)

COMPLICATION_SLOTS = (
    ComplicationSlotSpec(0, "lower_left", "slot_lower_left", 87, 277, 106, "STEP_COUNT", "SHORT_TEXT"),
    ComplicationSlotSpec(1, "lower_right", "slot_lower_right", 257, 277, 106, "HEART_RATE", "RANGED_VALUE"),
    ComplicationSlotSpec(2, "lower_center", "slot_lower_center", 190, 264, 70, "NEXT_EVENT", "SHORT_TEXT"),
    ComplicationSlotSpec(3, "middle_left", "slot_middle_left", 0, SIDE_COMPLICATION_Y, SIDE_COMPLICATION_SIZE, "SUNRISE_SUNSET", "SHORT_TEXT"),
    ComplicationSlotSpec(4, "middle_right", "slot_middle_right", WATCH_SIZE - SIDE_COMPLICATION_SIZE, SIDE_COMPLICATION_Y, SIDE_COMPLICATION_SIZE, "UNREAD_NOTIFICATION_COUNT", "SHORT_TEXT"),
)

COMPLICATION_LAYOUTS = {
    "2": (0, 1),
    "3": (0, 1, 2),
    "4": (0, 1, 3, 4),
}


def element(parent: ET.Element, tag: str, **attributes: object) -> ET.Element:
    serialized = {name: str(value) for name, value in attributes.items()}
    return ET.SubElement(parent, tag, serialized)


def configuration_value_expression(
    configuration_id: str,
    values: Sequence[tuple[str, int | float]],
    default_id: str,
) -> str:
    default = next(value for option_id, value in values if option_id == default_id)
    expression = str(default)
    for option_id, value in reversed(values):
        if option_id == default_id:
            continue
        expression = (
            f'[CONFIGURATION.{configuration_id}] == "{option_id}" '
            f"? {value} : {expression}"
        )
    return expression


def configuration_matches_expression(
    configuration_id: str,
    option_ids: Sequence[str],
) -> str:
    return " || ".join(
        f'[CONFIGURATION.{configuration_id}] == "{option_id}"'
        for option_id in option_ids
    )


def ambient_brightness_expression() -> str:
    return configuration_value_expression(
        AMBIENT_COLOR_ID,
        AMBIENT_BRIGHTNESS_VALUES,
        DEFAULT_AMBIENT_APPEARANCE_ID,
    )


def add_ambient_color_condition(
    parent: ET.Element,
    *,
    name: str,
    color: str,
    monochrome: str,
    builder: Callable[[ET.Element, str, str], None],
) -> None:
    condition = element(parent, "Condition")
    expressions = element(condition, "Expressions")
    expression_name = f"{name}_uses_color"
    expression = element(expressions, "Expression", name=expression_name)
    expression.text = configuration_matches_expression(
        AMBIENT_COLOR_ID,
        AMBIENT_COLOR_OPTION_IDS,
    )
    compare = element(condition, "Compare", expression=expression_name)
    builder(compare, color, "color")
    default = element(condition, "Default")
    builder(default, monochrome, "mono")


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
    name: str | None = None,
    ellipsis: bool = True,
    outline_color: str | None = None,
    outline_width: int = 1,
    uppercase: bool = False,
) -> ET.Element:
    attributes: dict[str, object] = {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "alpha": alpha,
    }
    if name is not None:
        attributes["name"] = name
    part = element(parent, "PartText", **attributes)
    if ambient_alpha is not None:
        add_variant(part, "alpha", ambient_alpha)
    text = element(part, "Text", align="CENTER", ellipsis=str(ellipsis).upper())
    font = element(
        text,
        "Font",
        family="SYNC_TO_DEVICE",
        size=size,
        weight=weight,
        color=color,
    )
    formatter_parent = font
    if outline_color is not None:
        formatter_parent = element(font, "Outline", color=outline_color, width=outline_width)
    if uppercase:
        formatter_parent = element(formatter_parent, "Upper")
    if parameters:
        template_element = element(formatter_parent, "Template")
        template_element.text = template
        for expression in parameters:
            element(template_element, "Parameter", expression=expression)
    else:
        formatter_parent.text = template
    return part


def add_empty_group(parent: ET.Element, name: str) -> ET.Element:
    return element(parent, "Group", name=name, x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE, alpha=0)


def add_user_configuration(
    parent: ET.Element,
    tag: str,
    *,
    configuration_id: str,
    display_name: str,
    default_value: str,
) -> ET.Element:
    return element(
        parent,
        tag,
        id=configuration_id,
        displayName=display_name,
        screenReaderText=display_name,
        defaultValue=default_value,
        highlight=CONFIGURATION_HIGHLIGHTS[configuration_id],
    )


def add_enabled_group(
    parent: ET.Element,
    setting_id: str,
    name: str,
    builder: Callable[[ET.Element], None],
) -> None:
    configuration = element(parent, "ListConfiguration", id=setting_id)
    option = element(configuration, "ListOption", id="TRUE")
    group = element(option, "Group", name=name, x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    builder(group)


def add_user_configurations(root: ET.Element) -> None:
    configurations = element(root, "UserConfigurations")

    for configuration_id, label, option_label_prefix in (
        (DOT_COLOR_ID, "setting_dot_color", "dots"),
        (TEXT_COLOR_ID, "setting_text_color", "text"),
    ):
        colors = add_user_configuration(
            configurations,
            "ColorConfiguration",
            configuration_id=configuration_id,
            display_name=label,
            default_value="terminal",
        )
        for choice in COLOR_CHOICES:
            option_label = f"{option_label_prefix}_{choice.label}"
            element(
                colors,
                "ColorOption",
                id=choice.option_id,
                displayName=option_label,
                screenReaderText=option_label,
                colors=" ".join(choice.colors),
            )

    appearance = add_user_configuration(
        configurations,
        "ColorConfiguration",
        configuration_id=APPEARANCE_ID,
        display_name="setting_appearance",
        default_value="dark",
    )
    for choice in APPEARANCES:
        element(
            appearance,
            "ColorOption",
            id=choice.option_id,
            displayName=choice.label,
            screenReaderText=choice.label,
            colors=" ".join(choice.colors),
        )

    backdrop_color = add_user_configuration(
        configurations,
        "ColorConfiguration",
        configuration_id=BACKDROP_COLOR_ID,
        display_name="setting_backdrop_color",
        default_value=DEFAULT_BACKDROP_COLOR_ID,
    )
    for choice in COLOR_CHOICES:
        option_label = f"backdrop_{choice.label}"
        element(
            backdrop_color,
            "ColorOption",
            id=choice.option_id,
            displayName=option_label,
            screenReaderText=option_label,
            colors=choice.colors[0],
        )

    backdrop_opacity = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=BACKDROP_OPACITY_ID,
        display_name="setting_backdrop_opacity",
        default_value=DEFAULT_BACKDROP_OPACITY_ID,
    )
    for choice in BACKDROP_OPACITY_CHOICES:
        element(
            backdrop_opacity,
            "ListOption",
            id=choice.option_id,
            displayName=choice.label,
            screenReaderText=choice.label,
        )

    backdrop_layout = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=BACKDROP_LAYOUT_ID,
        display_name="setting_backdrop_layout",
        default_value=DEFAULT_BACKDROP_LAYOUT_ID,
    )
    for choice in BACKDROP_LAYOUT_CHOICES:
        element(
            backdrop_layout,
            "ListOption",
            id=choice.option_id,
            displayName=choice.label,
            screenReaderText=choice.label,
        )

    backdrop_visibility = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=BACKDROP_VISIBILITY_ID,
        display_name="setting_backdrop_visibility",
        default_value=DEFAULT_BACKDROP_VISIBILITY_ID,
    )
    for option_id, label in BACKDROP_VISIBILITY_OPTIONS:
        element(
            backdrop_visibility,
            "ListOption",
            id=option_id,
            displayName=label,
            screenReaderText=label,
        )

    size = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=SIZE_ID,
        display_name="setting_display_size",
        default_value=DEFAULT_SIZE_ID,
    )
    for choice in SIZE_CHOICES:
        element(size, "ListOption", id=choice.option_id, displayName=choice.label, screenReaderText=choice.label)

    clock_mode = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=CLOCK_MODE_ID,
        display_name="setting_clock_mode",
        default_value="24",
    )
    for option_id, label in (
        ("12", "clock_mode_12"),
        ("24", "clock_mode_24"),
    ):
        element(clock_mode, "ListOption", id=option_id, displayName=label, screenReaderText=label)

    dot_effect = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=DOT_EFFECT_ID,
        display_name="setting_dot_effect",
        default_value="glow",
    )
    for option_id, label in (
        ("none", "dot_effect_none"),
        ("glow", "dot_effect_glow"),
        ("bezel", "dot_effect_bezel"),
    ):
        element(dot_effect, "ListOption", id=option_id, displayName=label, screenReaderText=label)

    tick_style = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=TICK_STYLE_ID,
        display_name="setting_tick_style",
        default_value="all",
    )
    for option_id, label in (
        ("none", "tick_style_none"),
        ("single", "tick_style_single"),
        ("wave", "tick_style_wave"),
        ("boost", "tick_style_boost"),
        ("all", "tick_style_all"),
    ):
        element(tick_style, "ListOption", id=option_id, displayName=label, screenReaderText=label)

    for setting_id, label, default, enabled_label, disabled_label in BINARY_SETTINGS:
        setting = add_user_configuration(
            configurations,
            "ListConfiguration",
            configuration_id=setting_id,
            display_name=label,
            default_value=default,
        )
        for option_id, option_label in (("TRUE", enabled_label), ("FALSE", disabled_label)):
            element(
                setting,
                "ListOption",
                id=option_id,
                displayName=option_label,
                screenReaderText=option_label,
            )

    ambient_appearance = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=AMBIENT_COLOR_ID,
        display_name="setting_ambient_appearance",
        default_value=DEFAULT_AMBIENT_APPEARANCE_ID,
    )
    for choice in AMBIENT_APPEARANCE_CHOICES:
        element(
            ambient_appearance,
            "ListOption",
            id=choice.option_id,
            displayName=choice.label,
            screenReaderText=choice.label,
        )

    ambient_info = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=AMBIENT_INFO_ID,
        display_name="setting_ambient_info",
        default_value="off",
    )
    for option_id, label in AMBIENT_INFO_OPTIONS:
        element(
            ambient_info,
            "ListOption",
            id=option_id,
            displayName=label,
            screenReaderText=label,
        )

    date_format = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=DATE_FORMAT_ID,
        display_name="setting_date_format",
        default_value="iso",
    )
    for specification in DATE_FORMATS:
        element(
            date_format,
            "ListOption",
            id=specification.option_id,
            displayName=specification.label,
            screenReaderText=specification.label,
        )
    element(date_format, "ListOption", id="off", displayName="date_format_off", screenReaderText="date_format_off")

    battery_display = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=BATTERY_DISPLAY_ID,
        display_name="setting_battery_display",
        default_value="decimal",
    )
    for option_id, label in (
        ("decimal", "battery_display_decimal"),
        ("hex", "battery_display_hex"),
        ("binary", "battery_display_binary"),
        ("off", "battery_display_off"),
    ):
        element(battery_display, "ListOption", id=option_id, displayName=label, screenReaderText=label)

    complication_count = add_user_configuration(
        configurations,
        "ListConfiguration",
        configuration_id=COMPLICATION_COUNT_ID,
        display_name="setting_complication_count",
        default_value="2",
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


def add_static_ticks(parent: ET.Element, *, every: int, alpha: int) -> None:
    for second in range(0, 60, every):
        major = second % 5 == 0
        width = 3 if major else 2
        height = 12 if major else 7
        part = element(
            parent,
            "PartDraw",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
            angle=second * 6,
            pivotX=0.5,
            pivotY=0.5,
            alpha=alpha if major else round(alpha * 0.65),
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
        element(rectangle, "Fill", color=COLOR_TEXT_INACTIVE)


def add_current_tick(
    parent: ET.Element,
    *,
    angle_offset: int = 0,
    alpha: int = 255,
    width: int = 6,
    height: int = 16,
) -> None:
    current = element(
        parent,
        "PartDraw",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
        pivotX=0.5,
        pivotY=0.5,
        alpha=alpha,
    )
    marker = element(
        current,
        "RoundRectangle",
        x=(WATCH_SIZE - width) / 2,
        y=11,
        width=width,
        height=height,
        cornerRadiusX=width / 2,
        cornerRadiusY=width / 2,
    )
    element(marker, "Fill", color=COLOR_DOT_ACTIVE)
    element(current, "Transform", target="angle", value=f"[SECOND] * 6 + {angle_offset}")


def add_tick_ring(scene: ET.Element) -> None:
    configuration = element(scene, "ListConfiguration", id=TICK_STYLE_ID)

    none = element(configuration, "ListOption", id="none")
    add_empty_group(none, "ticks_none")

    single = element(configuration, "ListOption", id="single")
    single_group = element(single, "Group", name="ticks_single", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_variant(single_group, "alpha", 0)
    add_current_tick(single_group)

    wave = element(configuration, "ListOption", id="wave")
    wave_group = element(wave, "Group", name="ticks_wave", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_variant(wave_group, "alpha", 0)
    add_static_ticks(wave_group, every=5, alpha=70)
    for offset, alpha, height in ((-18, 50, 8), (-12, 85, 10), (-6, 140, 13), (0, 255, 16)):
        add_current_tick(wave_group, angle_offset=offset, alpha=alpha, width=4, height=height)

    boost = element(configuration, "ListOption", id="boost")
    boost_group = element(boost, "Group", name="ticks_boost", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_variant(boost_group, "alpha", 0)
    add_static_ticks(boost_group, every=1, alpha=95)
    for offset, alpha, height in ((-6, 100, 12), (0, 255, 20), (6, 100, 12)):
        add_current_tick(boost_group, angle_offset=offset, alpha=alpha, width=6, height=height)

    all_option = element(configuration, "ListOption", id="all")
    all_group = element(all_option, "Group", name="ticks_all", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_variant(all_group, "alpha", 0)
    add_static_ticks(all_group, every=1, alpha=190)
    add_current_tick(all_group)


def bit_geometry(bit_count: int, size: SizeChoice) -> tuple[int, tuple[int, ...]]:
    dot_size = round(REFERENCE_DOT_SIZE * size.scale)
    span = round(REFERENCE_ROW_SPAN * size.scale)
    left_center = (WATCH_SIZE - span) / 2
    centers = tuple(round(left_center + index * span / (bit_count - 1)) for index in range(bit_count))
    return dot_size, tuple(round(center - dot_size / 2) for center in centers)


def ambient_dither_rows(dot_size: int) -> tuple[tuple[int, int, int, int, int], ...]:
    center = dot_size / 2
    radius = dot_size / 2 - 2
    thickness = max(1, round(dot_size / 12))
    rows: list[tuple[int, int, int, int, int]] = []
    for index in range(1, AMBIENT_DITHER_ROW_COUNT + 1):
        fraction = index / (AMBIENT_DITHER_ROW_COUNT + 1)
        y = round(dot_size * fraction)
        half_span = math.sqrt(max(0, radius**2 - (y - center) ** 2)) - thickness
        start = max(1, round(center - half_span))
        end = min(dot_size - 1, round(center + half_span))
        rows.append((y, start, end, thickness, thickness if index % 2 else 0))
    return tuple(rows)


def add_active_dot_effect(parent: ET.Element, *, name: str, dot_size: int) -> None:
    configuration = element(parent, "ListConfiguration", id=DOT_EFFECT_ID)

    none = element(configuration, "ListOption", id="none")
    none_group = element(none, "Group", name=f"{name}_plain", x=0, y=0, width=dot_size, height=dot_size)
    add_variant(none_group, "alpha", 0)
    none_draw = element(none_group, "PartDraw", x=0, y=0, width=dot_size, height=dot_size)
    none_ellipse = element(none_draw, "Ellipse", x=1, y=1, width=dot_size - 2, height=dot_size - 2)
    element(none_ellipse, "Fill", color=COLOR_DOT_ACTIVE)

    glow = element(configuration, "ListOption", id="glow")
    glow_group = element(glow, "Group", name=f"{name}_glow", x=0, y=0, width=dot_size, height=dot_size)
    add_variant(glow_group, "alpha", 0)
    halo = element(glow_group, "PartDraw", x=0, y=0, width=dot_size, height=dot_size, alpha=110)
    halo_ellipse = element(halo, "Ellipse", x=1, y=1, width=dot_size - 2, height=dot_size - 2)
    element(halo_ellipse, "Stroke", color=COLOR_DOT_AMBIENT, thickness=max(3, round(dot_size / 6)))
    glow_draw = element(glow_group, "PartDraw", x=0, y=0, width=dot_size, height=dot_size)
    glow_ellipse = element(glow_draw, "Ellipse", x=3, y=3, width=dot_size - 6, height=dot_size - 6)
    element(glow_ellipse, "Fill", color=COLOR_DOT_ACTIVE)

    bezel = element(configuration, "ListOption", id="bezel")
    bezel_group = element(bezel, "Group", name=f"{name}_bezel", x=0, y=0, width=dot_size, height=dot_size)
    add_variant(bezel_group, "alpha", 0)
    bezel_draw = element(bezel_group, "PartDraw", x=0, y=0, width=dot_size, height=dot_size)
    bezel_outer = element(bezel_draw, "Ellipse", x=1, y=1, width=dot_size - 2, height=dot_size - 2)
    element(bezel_outer, "Fill", color=COLOR_DOT_ACTIVE)
    bezel_inner = element(bezel_draw, "Ellipse", x=4, y=4, width=dot_size - 8, height=dot_size - 8)
    element(bezel_inner, "Fill", color=COLOR_BACKGROUND)
    bezel_core = element(bezel_draw, "Ellipse", x=7, y=7, width=dot_size - 14, height=dot_size - 14)
    element(bezel_core, "Fill", color=COLOR_DOT_ACTIVE)


def add_ambient_dot(
    parent: ET.Element,
    *,
    name: str,
    x: int,
    y: int,
    dot_size: int,
    source: str,
    bit: int,
) -> None:
    def build_ambient(option: ET.Element, color: str, suffix: str) -> None:
        group = element(
            option,
            "Group",
            name=f"{name}_ambient_{suffix}",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
            alpha=0,
        )
        add_variant(group, "alpha", ambient_brightness_expression())

        outline = element(
            group,
            "PartDraw",
            x=x,
            y=y,
            width=dot_size,
            height=dot_size,
            alpha=255,
        )
        outline_ellipse = element(outline, "Ellipse", x=1, y=1, width=dot_size - 2, height=dot_size - 2)
        element(outline_ellipse, "Stroke", color=color, thickness=max(1, round(dot_size / 12)))

        lit = element(group, "Group", name=f"{name}_ambient_lit_{suffix}", x=x, y=y, width=dot_size, height=dot_size)
        element(lit, "Transform", target="alpha", value=f"floor(({source}) / {bit}) % 2 == 1 ? 255 : 0")
        pattern = element(
            lit,
            "PartDraw",
            name="ambient_dither",
            x=0,
            y=0,
            width=dot_size,
            height=dot_size,
        )
        for line_y, start, end, thickness, phase in ambient_dither_rows(dot_size):
            line = element(pattern, "Line", startX=start, startY=line_y, endX=end, endY=line_y)
            element(
                line,
                "Stroke",
                color=color,
                thickness=thickness,
                dashIntervals=(
                    f"{thickness * AMBIENT_DITHER_DASH_MULTIPLIER} "
                    f"{AMBIENT_DITHER_GAP}"
                ),
                dashPhase=phase,
                cap="BUTT",
            )

    add_ambient_color_condition(
        parent,
        name=f"{name}_ambient",
        color=COLOR_DOT_AMBIENT,
        monochrome=COLOR_AMBIENT_MONO,
        builder=build_ambient,
    )


def add_binary_dot(
    parent: ET.Element,
    *,
    name: str,
    x: int,
    y: int,
    dot_size: int,
    source: str,
    bit: int,
) -> None:
    outline = element(parent, "PartDraw", x=x, y=y, width=dot_size, height=dot_size)
    add_variant(outline, "alpha", 0)
    outline_ellipse = element(outline, "Ellipse", x=1, y=1, width=dot_size - 2, height=dot_size - 2)
    element(outline_ellipse, "Stroke", color=COLOR_DOT_INACTIVE, thickness=max(2, round(dot_size / 12)))

    active = element(parent, "Group", name=f"{name}_active_lit", x=x, y=y, width=dot_size, height=dot_size)
    element(active, "Transform", target="alpha", value=f"floor(({source}) / {bit}) % 2 == 1 ? 255 : 0")
    add_active_dot_effect(active, name=name, dot_size=dot_size)
    add_ambient_dot(
        parent,
        name=name,
        x=x,
        y=y,
        dot_size=dot_size,
        source=source,
        bit=bit,
    )


def add_decimal_backdrop_text(
    parent: ET.Element,
    *,
    name: str,
    source: str,
    y: int,
    color: str,
    ambient: bool,
) -> None:
    add_text(
        parent,
        name=name,
        x=0,
        y=y,
        width=WATCH_SIZE,
        height=WATCH_SIZE // 2,
        size=DECIMAL_BACKDROP_SIZE,
        color=COLOR_BLACK if ambient else color,
        template="%02d",
        parameters=(source,),
        weight="EXTRA_BOLD",
        ellipsis=False,
        outline_color=color if ambient else None,
        outline_width=2,
    )


def add_decimal_backdrop_layer(
    parent: ET.Element,
    *,
    name: str,
    hour_source: str,
    color: str,
    ambient: bool,
) -> None:
    layer = element(
        parent,
        "Group",
        name=f"{name}_style",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
        pivotX=0.5,
        pivotY=0.5,
    )
    element(
        layer,
        "Transform",
        target="alpha",
        value=configuration_value_expression(
            BACKDROP_OPACITY_ID,
            BACKDROP_OPACITY_VALUES,
            DEFAULT_BACKDROP_OPACITY_ID,
        ),
    )
    size_expression = configuration_value_expression(
        BACKDROP_LAYOUT_ID,
        BACKDROP_LAYOUT_SCALE_VALUES,
        DEFAULT_BACKDROP_LAYOUT_ID,
    )
    element(layer, "Transform", target="scaleX", value=size_expression)
    element(layer, "Transform", target="scaleY", value=size_expression)
    element(
        layer,
        "Transform",
        target="y",
        value=configuration_value_expression(
            BACKDROP_LAYOUT_ID,
            BACKDROP_LAYOUT_Y_VALUES,
            DEFAULT_BACKDROP_LAYOUT_ID,
        ),
    )
    add_decimal_backdrop_text(
        layer,
        name="hour_decimal_backdrop_ambient" if ambient else "hour_decimal_backdrop_active",
        source=hour_source,
        y=0,
        color=color,
        ambient=ambient,
    )
    add_decimal_backdrop_text(
        layer,
        name="minute_decimal_backdrop_ambient" if ambient else "minute_decimal_backdrop_active",
        source="[MINUTE]",
        y=WATCH_SIZE // 2,
        color=color,
        ambient=ambient,
    )


def add_decimal_backdrops(parent: ET.Element, *, name: str, hour_source: str) -> None:
    active = element(
        parent,
        "Group",
        name=f"{name}_active_backdrops",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
    )
    add_variant(active, "alpha", 0)
    active_visibility = element(
        active,
        "Group",
        name=f"{name}_active_backdrops_visibility",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
    )
    element(
        active_visibility,
        "Transform",
        target="alpha",
        value=(
            f"({configuration_matches_expression(BACKDROP_VISIBILITY_ID, BACKDROP_ACTIVE_OPTION_IDS)}) "
            "? 255 : 0"
        ),
    )
    add_decimal_backdrop_layer(
        active_visibility,
        name=f"{name}_active_backdrops",
        hour_source=hour_source,
        color=COLOR_BACKDROP,
        ambient=False,
    )

    def build_ambient(option: ET.Element, color: str, suffix: str) -> None:
        ambient = element(
            option,
            "Group",
            name=f"{name}_ambient_backdrops_{suffix}",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
            alpha=0,
        )
        add_variant(ambient, "alpha", ambient_brightness_expression())
        ambient_visibility = element(
            ambient,
            "Group",
            name=f"{name}_ambient_backdrops_{suffix}_visibility",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        element(
            ambient_visibility,
            "Transform",
            target="alpha",
            value=(
                f"({configuration_matches_expression(BACKDROP_VISIBILITY_ID, BACKDROP_AMBIENT_OPTION_IDS)}) "
                "? 255 : 0"
            ),
        )
        add_decimal_backdrop_layer(
            ambient_visibility,
            name=f"{name}_ambient_backdrops_{suffix}",
            hour_source=hour_source,
            color=color,
            ambient=True,
        )

    add_ambient_color_condition(
        parent,
        name=f"{name}_ambient_backdrops",
        color=COLOR_BACKDROP,
        monochrome=COLOR_AMBIENT_BACKDROP,
        builder=build_ambient,
    )


def add_binary_row(
    parent: ET.Element,
    *,
    name: str,
    source: str,
    weights: Sequence[int],
    y: int,
) -> None:
    base_size = next(
        choice for choice in SIZE_CHOICES if choice.option_id == BASE_SIZE_ID
    )
    dot_size, positions = bit_geometry(len(weights), base_size)
    row_center_y = (y + dot_size / 2) / WATCH_SIZE
    group = element(
        parent,
        "Group",
        name=f"{name}_scaled",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
        pivotX=0.5,
        pivotY=round(row_center_y, 6),
    )
    size_expression = configuration_value_expression(
        SIZE_ID,
        DISPLAY_SIZE_VALUES,
        DEFAULT_SIZE_ID,
    )
    element(group, "Transform", target="scaleX", value=size_expression)
    element(group, "Transform", target="scaleY", value=size_expression)

    def build_weights(weights_parent: ET.Element) -> None:
        active = element(
            weights_parent,
            "Group",
            name=f"{name}_weights_active",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        add_variant(active, "alpha", 0)
        for x, bit in zip(positions, weights):
            add_text(
                active,
                x=x - 7,
                y=y - 23,
                width=dot_size + 14,
                height=18,
                size=13,
                color=COLOR_TEXT_ACTIVE,
                template=str(bit),
                alpha=210,
            )

        def build_ambient(ambient_option: ET.Element, color: str, suffix: str) -> None:
            ambient = element(
                ambient_option,
                "Group",
                name=f"{name}_weights_ambient_{suffix}",
                x=0,
                y=0,
                width=WATCH_SIZE,
                height=WATCH_SIZE,
                alpha=0,
            )
            add_variant(ambient, "alpha", ambient_brightness_expression())
            for x, bit in zip(positions, weights):
                add_text(
                    ambient,
                    x=x - 7,
                    y=y - 23,
                    width=dot_size + 14,
                    height=18,
                    size=13,
                    color=color,
                    template=str(bit),
                )

        add_ambient_color_condition(
            weights_parent,
            name=f"{name}_weights_ambient",
            color=COLOR_TEXT_AMBIENT,
            monochrome=COLOR_AMBIENT_MONO,
            builder=build_ambient,
        )

    add_enabled_group(group, SHOW_WEIGHTS_ID, f"{name}_bit_weights", build_weights)

    for x, bit in zip(positions, weights):
        add_binary_dot(
            group,
            name=f"{name}_{bit}",
            x=x,
            y=y,
            dot_size=dot_size,
            source=source,
            bit=bit,
        )


def add_clock_layout(
    parent: ET.Element,
    *,
    name: str,
    hour_source: str,
    hour_weights: Sequence[int],
    include_seconds: bool,
    row_positions: Sequence[int],
) -> None:
    group = element(parent, "Group", name=name, x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_decimal_backdrops(group, name=name, hour_source=hour_source)

    if include_seconds:
        row_sources = (("hour", hour_source, hour_weights), ("minute", "[MINUTE]", SIX_BIT_WEIGHTS), ("second", "[SECOND]", SIX_BIT_WEIGHTS))
        add_screen_reader(group, "Time is %d:%02d:%02d", (hour_source, "[MINUTE]", "[SECOND]"))
    else:
        row_sources = (("hour", hour_source, hour_weights), ("minute", "[MINUTE]", SIX_BIT_WEIGHTS))
        add_screen_reader(group, "Time is %d:%02d", (hour_source, "[MINUTE]"))

    if len(row_sources) != len(row_positions):
        raise ValueError("Clock row positions do not match the selected layout")

    for (row_name, source, weights), y in zip(row_sources, row_positions):
        row = element(group, "Group", name=f"{name}_{row_name}_row", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
        if row_name == "second":
            add_variant(row, "alpha", 0)
        add_binary_row(
            row,
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
    row_layouts: dict[bool, tuple[int, ...]],
) -> None:
    seconds = element(parent, "ListConfiguration", id=SHOW_SECONDS_ID)
    on = element(seconds, "ListOption", id="TRUE")
    add_clock_layout(
        on,
        name=f"{name}_with_seconds",
        hour_source=hour_source,
        hour_weights=hour_weights,
        include_seconds=True,
        row_positions=row_layouts[True],
    )
    off = element(seconds, "ListOption", id="FALSE")
    add_clock_layout(
        off,
        name=f"{name}_without_seconds",
        hour_source=hour_source,
        hour_weights=hour_weights,
        include_seconds=False,
        row_positions=row_layouts[False],
    )


def add_clock_modes(
    parent: ET.Element,
    *,
    name: str,
    row_layouts: dict[bool, tuple[int, ...]],
) -> None:
    clock_mode = element(parent, "ListConfiguration", id=CLOCK_MODE_ID)
    for option_id, hour_source, hour_weights in (
        ("12", "[HOUR_1_12]", HOUR_12_WEIGHTS),
        ("24", "[HOUR_0_23]", HOUR_24_WEIGHTS),
    ):
        option = element(clock_mode, "ListOption", id=option_id)
        group = element(
            option,
            "Group",
            name=f"{name}_{option_id}_hour",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        add_clock_variant(
            group,
            name=f"{name}_{option_id}_hour_clock",
            hour_source=hour_source,
            hour_weights=hour_weights,
            row_layouts=row_layouts,
        )


def add_clock(scene: ET.Element) -> None:
    add_clock_modes(scene, name="clock", row_layouts=CLOCK_ROW_LAYOUT)


def add_configurable_date_text(
    parent: ET.Element,
    *,
    name: str,
    specification: DateFormatSpec,
    color: str,
    weekday_configuration_id: str | None,
) -> None:
    def add_date_value_text(
        text_parent: ET.Element,
        *,
        uppercase: bool,
        uppercase_suffix: str,
        include_weekday: bool,
        weekday_suffix: str,
    ) -> None:
        template = (
            f"%s {specification.template}"
            if include_weekday
            else specification.template
        )
        parameters = (
            ("[DAY_OF_WEEK_S]", *specification.parameters)
            if include_weekday
            else specification.parameters
        )
        text = add_text(
            text_parent,
            name=f"{name}_{uppercase_suffix}_{weekday_suffix}",
            x=70,
            y=36,
            width=310,
            height=30,
            size=specification.size,
            color=color,
            template=template,
            parameters=parameters,
            uppercase=uppercase,
        )
        add_screen_reader(text, template, parameters)

    uppercase_configuration = element(parent, "ListConfiguration", id=UPPERCASE_DATE_ID)
    for uppercase_id, uppercase, uppercase_suffix in (
        ("TRUE", True, "uppercase"),
        ("FALSE", False, "mixed_case"),
    ):
        uppercase_option = element(uppercase_configuration, "ListOption", id=uppercase_id)
        uppercase_group = element(
            uppercase_option,
            "Group",
            name=f"{name}_{uppercase_suffix}",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        if weekday_configuration_id is not None:
            weekday_configuration = element(
                uppercase_group,
                "ListConfiguration",
                id=weekday_configuration_id,
            )
            for weekday_id, include_weekday, weekday_suffix in (
                ("TRUE", True, "weekday"),
                ("FALSE", False, "date_only"),
            ):
                weekday_option = element(
                    weekday_configuration,
                    "ListOption",
                    id=weekday_id,
                )
                add_date_value_text(
                    weekday_option,
                    uppercase=uppercase,
                    uppercase_suffix=uppercase_suffix,
                    include_weekday=include_weekday,
                    weekday_suffix=weekday_suffix,
                )
            continue

        condition = element(uppercase_group, "Condition")
        expressions = element(condition, "Expressions")
        weekday_expression = element(
            expressions,
            "Expression",
            name="ambient_info_has_weekday",
        )
        weekday_expression.text = configuration_matches_expression(
            AMBIENT_INFO_ID,
            AMBIENT_WEEKDAY_OPTION_IDS,
        )
        date_expression = element(
            expressions,
            "Expression",
            name="ambient_info_has_date",
        )
        date_expression.text = configuration_matches_expression(
            AMBIENT_INFO_ID,
            AMBIENT_DATE_OPTION_IDS,
        )

        weekday_compare = element(
            condition,
            "Compare",
            expression="ambient_info_has_weekday",
        )
        add_date_value_text(
            weekday_compare,
            uppercase=uppercase,
            uppercase_suffix=uppercase_suffix,
            include_weekday=True,
            weekday_suffix="weekday",
        )
        date_compare = element(
            condition,
            "Compare",
            expression="ambient_info_has_date",
        )
        add_date_value_text(
            date_compare,
            uppercase=uppercase,
            uppercase_suffix=uppercase_suffix,
            include_weekday=False,
            weekday_suffix="date_only",
        )
        default = element(condition, "Default")
        add_empty_group(default, f"{name}_{uppercase_suffix}_hidden")


def add_date(scene: ET.Element) -> None:
    date = element(scene, "ListConfiguration", id=DATE_FORMAT_ID)

    for specification in DATE_FORMATS:
        option = element(date, "ListOption", id=specification.option_id)
        option_group = element(
            option,
            "Group",
            name=f"date_{specification.option_id}",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        active = element(
            option_group,
            "Group",
            name=f"date_{specification.option_id}_active",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        add_variant(active, "alpha", 0)
        add_configurable_date_text(
            active,
            name=f"date_{specification.option_id}_active",
            specification=specification,
            color=COLOR_TEXT_ACTIVE,
            weekday_configuration_id=SHOW_WEEKDAY_ID,
        )

        def build_ambient(ambient_parent: ET.Element, date_specification: DateFormatSpec = specification) -> None:
            def build_color(color_option: ET.Element, color: str, suffix: str) -> None:
                ambient = element(
                    color_option,
                    "Group",
                    name=f"date_{date_specification.option_id}_ambient_{suffix}",
                    x=0,
                    y=0,
                    width=WATCH_SIZE,
                    height=WATCH_SIZE,
                    alpha=0,
                )
                add_variant(ambient, "alpha", ambient_brightness_expression())
                add_configurable_date_text(
                    ambient,
                    name=f"date_{date_specification.option_id}_ambient_{suffix}",
                    specification=date_specification,
                    color=color,
                    weekday_configuration_id=None,
                )

            add_ambient_color_condition(
                ambient_parent,
                name=f"date_{date_specification.option_id}_ambient",
                color=COLOR_TEXT_AMBIENT,
                monochrome=COLOR_AMBIENT_MONO,
                builder=build_color,
            )

        build_ambient(option_group)

    off = element(date, "ListOption", id="off")
    add_empty_group(off, "date_hidden")


def add_battery_readout(
    parent: ET.Element,
    *,
    name: str,
    template: str,
    parameters: Sequence[str],
) -> None:
    active = element(parent, "Group", name=f"{name}_active", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_variant(active, "alpha", 0)
    active_text = add_text(
        active,
        name=f"{name}_active_text",
        x=135,
        y=BATTERY_READOUT_Y,
        width=180,
        height=28,
        size=20,
        color=COLOR_TEXT_ACTIVE,
        template=template,
        parameters=parameters,
    )
    add_screen_reader(active_text, "Battery %d percent", ("[BATTERY_PERCENT]",))

    def build_ambient(color_option: ET.Element, color: str, suffix: str) -> None:
        ambient = element(
            color_option,
            "Group",
            name=f"{name}_ambient_{suffix}",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
            alpha=0,
        )
        add_variant(ambient, "alpha", ambient_brightness_expression())
        visibility = element(
            ambient,
            "Group",
            name=f"{name}_ambient_{suffix}_visibility",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        element(
            visibility,
            "Transform",
            target="alpha",
            value=(
                f"({configuration_matches_expression(AMBIENT_INFO_ID, AMBIENT_BATTERY_OPTION_IDS)}) "
                "? 255 : 0"
            ),
        )
        add_text(
            visibility,
            name=f"{name}_ambient_{suffix}_text",
            x=135,
            y=BATTERY_READOUT_Y,
            width=180,
            height=28,
            size=20,
            color=color,
            template=template,
            parameters=parameters,
        )

    add_ambient_color_condition(
        parent,
        name=f"{name}_ambient",
        color=COLOR_TEXT_AMBIENT,
        monochrome=COLOR_AMBIENT_MONO,
        builder=build_ambient,
    )


def add_battery(scene: ET.Element) -> None:
    battery = element(scene, "ListConfiguration", id=BATTERY_DISPLAY_ID)

    decimal = element(battery, "ListOption", id="decimal")
    decimal_group = element(decimal, "Group", name="battery_decimal", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    add_battery_readout(
        decimal_group,
        name="battery_decimal",
        template="%d%%",
        parameters=("[BATTERY_PERCENT]",),
    )

    hexadecimal = element(battery, "ListOption", id="hex")
    hexadecimal_group = element(
        hexadecimal,
        "Group",
        name="battery_hex",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
    )
    add_battery_readout(
        hexadecimal_group,
        name="battery_hex",
        template="0x%x",
        parameters=("[BATTERY_PERCENT]",),
    )

    binary = element(battery, "ListOption", id="binary")
    binary_group = element(binary, "Group", name="battery_binary", x=0, y=0, width=WATCH_SIZE, height=WATCH_SIZE)
    condition = element(binary_group, "Condition")
    expressions = element(condition, "Expressions")
    for bit_count in range(7, 1, -1):
        threshold = 2 ** (bit_count - 1)
        expression = element(expressions, "Expression", name=f"battery_uses_{bit_count}_bits")
        expression.text = f"[BATTERY_PERCENT] >= {threshold}"
    for bit_count in range(7, 1, -1):
        compare = element(condition, "Compare", expression=f"battery_uses_{bit_count}_bits")
        compare_group = element(
            compare,
            "Group",
            name=f"battery_binary_{bit_count}_bits",
            x=0,
            y=0,
            width=WATCH_SIZE,
            height=WATCH_SIZE,
        )
        bits = tuple(2**power for power in range(bit_count - 1, -1, -1))
        add_battery_readout(
            compare_group,
            name=f"battery_binary_{bit_count}_bits",
            template="0b" + "%d" * bit_count,
            parameters=tuple(f"floor([BATTERY_PERCENT] / {bit}) % 2" for bit in bits),
        )
    default = element(condition, "Default")
    default_group = element(
        default,
        "Group",
        name="battery_binary_1_bit",
        x=0,
        y=0,
        width=WATCH_SIZE,
        height=WATCH_SIZE,
    )
    add_battery_readout(
        default_group,
        name="battery_binary_1_bit",
        template="0b%d",
        parameters=("[BATTERY_PERCENT] % 2",),
    )

    off = element(battery, "ListOption", id="off")
    add_empty_group(off, "battery_hidden")


def add_complication_shell(parent: ET.Element, size: int) -> None:
    background_draw = element(parent, "PartDraw", x=0, y=0, width=size, height=size)
    add_variant(background_draw, "alpha", 0)
    background = element(background_draw, "Ellipse", x=2, y=2, width=size - 4, height=size - 4)
    element(background, "Fill", color=COLOR_COMPLICATION_BACKGROUND)

    outline_draw = element(parent, "PartDraw", x=0, y=0, width=size, height=size)
    add_variant(outline_draw, "alpha", 150)
    outline = element(outline_draw, "Ellipse", x=2, y=2, width=size - 4, height=size - 4)
    element(outline, "Stroke", color=COLOR_TEXT_INACTIVE, thickness=2)


def add_short_text_complication(slot: ET.Element, size: int) -> None:
    complication = element(slot, "Complication", type="SHORT_TEXT")
    add_complication_shell(complication, size)

    horizontal_padding = round(size * 0.09)
    icon_size = round(size * 0.32)
    icon_x = (size - icon_size) // 2
    icon_y = round(size * 0.13)
    icon_text_y = round(size * 0.51)
    icon_text_height = round(size * 0.32)
    icon_text_size = round(size * 0.22)
    text_y = round(size * 0.33)
    text_height = round(size * 0.37)
    text_size = round(size * 0.26)

    condition = element(complication, "Condition")
    expressions = element(condition, "Expressions")
    has_icon = element(expressions, "Expression", name="short_text_has_icon")
    has_icon.text = "[COMPLICATION.MONOCHROMATIC_IMAGE] != null"

    compare = element(condition, "Compare", expression="short_text_has_icon")
    with_icon = element(compare, "Group", name="short_text_with_icon", x=0, y=0, width=size, height=size)
    icon = element(
        with_icon,
        "PartImage",
        x=icon_x,
        y=icon_y,
        width=icon_size,
        height=icon_size,
        tintColor=COLOR_DOT_ACTIVE,
    )
    element(icon, "Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")
    add_text(
        with_icon,
        x=horizontal_padding,
        y=icon_text_y,
        width=size - 2 * horizontal_padding,
        height=icon_text_height,
        size=icon_text_size,
        color=COLOR_TEXT_ACTIVE,
        template="%s",
        parameters=("[COMPLICATION.TEXT]",),
    )

    default = element(condition, "Default")
    add_text(
        default,
        x=horizontal_padding,
        y=text_y,
        width=size - 2 * horizontal_padding,
        height=text_height,
        size=text_size,
        color=COLOR_TEXT_ACTIVE,
        template="%s",
        parameters=("[COMPLICATION.TEXT]",),
    )


def add_image_complications(slot: ET.Element, size: int, name: str) -> None:
    small_padding = round(size * 0.18)
    monochromatic_padding = round(size * 0.24)

    small = element(slot, "Complication", type="SMALL_IMAGE")
    active = element(
        small,
        "Group",
        name=f"{name}_small_image_active",
        x=0,
        y=0,
        width=size,
        height=size,
    )
    add_variant(active, "alpha", 0)
    add_complication_shell(active, size)
    small_image = element(
        active,
        "PartImage",
        name=f"{name}_small_image_active_part",
        x=small_padding,
        y=small_padding,
        width=size - 2 * small_padding,
        height=size - 2 * small_padding,
    )
    element(small_image, "Image", resource="[COMPLICATION.SMALL_IMAGE]")

    condition = element(small, "Condition")
    expressions = element(condition, "Expressions")
    ambient_expression_name = f"{name}_small_image_has_ambient"
    has_ambient_image = element(expressions, "Expression", name=ambient_expression_name)
    has_ambient_image.text = "[COMPLICATION.SMALL_IMAGE_AMBIENT] != null"

    compare = element(condition, "Compare", expression=ambient_expression_name)
    ambient = element(
        compare,
        "Group",
        name=f"{name}_small_image_ambient",
        x=0,
        y=0,
        width=size,
        height=size,
        alpha=0,
    )
    add_variant(ambient, "alpha", 255)
    add_complication_shell(ambient, size)
    ambient_image = element(
        ambient,
        "PartImage",
        name=f"{name}_small_image_ambient_part",
        x=small_padding,
        y=small_padding,
        width=size - 2 * small_padding,
        height=size - 2 * small_padding,
    )
    element(ambient_image, "Image", resource="[COMPLICATION.SMALL_IMAGE_AMBIENT]")

    default = element(condition, "Default")
    element(
        default,
        "Group",
        name=f"{name}_small_image_ambient_missing",
        x=0,
        y=0,
        width=size,
        height=size,
        alpha=0,
    )

    monochromatic = element(slot, "Complication", type="MONOCHROMATIC_IMAGE")
    add_complication_shell(monochromatic, size)
    monochromatic_image = element(
        monochromatic,
        "PartImage",
        x=monochromatic_padding,
        y=monochromatic_padding,
        width=size - 2 * monochromatic_padding,
        height=size - 2 * monochromatic_padding,
        tintColor=COLOR_TEXT_ACTIVE,
    )
    element(monochromatic_image, "Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")


def add_ranged_value_complication(slot: ET.Element, size: int) -> None:
    complication = element(slot, "Complication", type="RANGED_VALUE")
    add_complication_shell(complication, size)

    arc_inset = round(size * 0.16)
    arc_stroke = max(4, round(size * 0.05))
    text_padding = round(size * 0.13)
    text_y = round(size * 0.33)
    text_height = round(size * 0.36)
    text_size = round(size * 0.24)

    draw = element(complication, "PartDraw", x=0, y=0, width=size, height=size)
    background = element(
        draw,
        "Arc",
        centerX=size / 2,
        centerY=size / 2,
        width=size - arc_inset,
        height=size - arc_inset,
        startAngle=-150,
        endAngle=150,
    )
    element(background, "Stroke", color=COLOR_DOT_INACTIVE, thickness=arc_stroke, cap="ROUND")
    progress = element(
        draw,
        "Arc",
        centerX=size / 2,
        centerY=size / 2,
        width=size - arc_inset,
        height=size - arc_inset,
        startAngle=-150,
        endAngle=150,
    )
    element(progress, "Stroke", color=COLOR_DOT_ACTIVE, thickness=arc_stroke, cap="ROUND")
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
        x=text_padding,
        y=text_y,
        width=size - 2 * text_padding,
        height=text_height,
        size=text_size,
        color=COLOR_TEXT_ACTIVE,
        template="%s",
        parameters=("[COMPLICATION.TEXT]",),
    )
    default = element(condition, "Default")
    add_text(
        default,
        x=text_padding,
        y=text_y,
        width=size - 2 * text_padding,
        height=text_height,
        size=text_size,
        color=COLOR_TEXT_ACTIVE,
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
        add_variant(slot, "alpha", ambient_brightness_expression())
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
        add_image_complications(slot, specification.size, specification.name)
        add_ranged_value_complication(slot, specification.size)
        element(slot, "Complication", type="EMPTY")


def build_watchface() -> ET.Element:
    root = ET.Element("WatchFace", {"width": str(WATCH_SIZE), "height": str(WATCH_SIZE), "clipShape": "CIRCLE"})
    root.append(ET.Comment(f" Generated by tools/generate_watchface.py for WFF {WFF_VERSION} "))
    element(root, "Metadata", key="CLOCK_TYPE", value="DIGITAL")
    element(root, "Metadata", key="PREVIEW_TIME", value="15:23:37")
    add_user_configurations(root)

    scene = element(root, "Scene", backgroundColor=COLOR_BACKGROUND)
    add_variant(scene, "backgroundColor", COLOR_BLACK)
    add_clock(scene)
    add_tick_ring(scene)
    add_date(scene)
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
