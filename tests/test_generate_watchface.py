from __future__ import annotations

import contextlib
import importlib.util
import io
import math
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PROJECT_ROOT / "tools/generate_watchface.py"
STRINGS_PATH = PROJECT_ROOT / "watchface/src/main/res/values/strings.xml"
WATCH_FACE_INFO_PATH = PROJECT_ROOT / "watchface/src/main/res/xml/watch_face_info.xml"
USER_CONFIGURATION_TAGS = {"BooleanConfiguration", "ColorConfiguration", "ListConfiguration"}
MIN_VISIBLE_TICK_LENGTH = 8
MODULE_SPEC = importlib.util.spec_from_file_location("generate_watchface", GENERATOR_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
GENERATOR = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = GENERATOR
MODULE_SPEC.loader.exec_module(GENERATOR)
LAYOUT_SPEC = importlib.util.spec_from_file_location("check_layout", PROJECT_ROOT / "tools/check_layout.py")
assert LAYOUT_SPEC is not None and LAYOUT_SPEC.loader is not None
LAYOUT = importlib.util.module_from_spec(LAYOUT_SPEC)
sys.modules[LAYOUT_SPEC.name] = LAYOUT
LAYOUT_SPEC.loader.exec_module(LAYOUT)
MIN_CONTENT_GAP = LAYOUT.MIN_CONTENT_GAP


class WatchFaceGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xml = GENERATOR.render_watchface()
        cls.root = ET.fromstring(cls.xml)
        cls.strings = {
            string.get("name"): string.text
            for string in ET.parse(STRINGS_PATH).getroot().findall("string")
        }
        cls.watch_face_info = ET.parse(WATCH_FACE_INFO_PATH).getroot()

    def user_configurations(self) -> tuple[ET.Element, ...]:
        configurations = self.root.find("UserConfigurations")
        self.assertIsNotNone(configurations)
        assert configurations is not None
        return tuple(
            configuration
            for configuration in configurations
            if configuration.tag in USER_CONFIGURATION_TAGS
        )

    def user_configuration(self, configuration_id: str) -> ET.Element:
        for configuration in self.user_configurations():
            if configuration.get("id") == configuration_id:
                return configuration
        self.fail(f"Missing user configuration: {configuration_id}")

    def test_reference_setting_catalog_is_available_without_touch_shortcuts(self) -> None:
        expected = {
            GENERATOR.DOT_COLOR_ID,
            GENERATOR.TEXT_COLOR_ID,
            GENERATOR.APPEARANCE_ID,
            GENERATOR.BACKDROP_COLOR_ID,
            GENERATOR.BACKDROP_OPACITY_ID,
            GENERATOR.BACKDROP_LAYOUT_ID,
            GENERATOR.BACKDROP_VISIBILITY_ID,
            GENERATOR.SIZE_ID,
            GENERATOR.CLOCK_MODE_ID,
            GENERATOR.DOT_EFFECT_ID,
            GENERATOR.TICK_STYLE_ID,
            GENERATOR.SHOW_SECONDS_ID,
            GENERATOR.SHOW_WEIGHTS_ID,
            GENERATOR.SHOW_WEEKDAY_ID,
            GENERATOR.AMBIENT_INFO_ID,
            GENERATOR.AMBIENT_COLOR_ID,
            GENERATOR.DATE_FORMAT_ID,
            GENERATOR.BATTERY_DISPLAY_ID,
            GENERATOR.COMPLICATION_COUNT_ID,
        }
        configurations = self.user_configurations()
        actual = {configuration.get("id") for configuration in configurations}
        self.assertEqual(actual, expected)
        self.assertEqual(len(configurations), 19)
        configurations_container = self.root.find("UserConfigurations")
        self.assertIsNotNone(configurations_container)
        assert configurations_container is not None
        self.assertLessEqual(len(configurations_container), 20)
        self.assertFalse(any("touch" in str(configuration_id).lower() for configuration_id in actual))

    def test_flavors_cover_every_setting_and_match_the_default(self) -> None:
        configurations = self.user_configurations()
        configurations_by_id = {
            configuration.get("id"): configuration
            for configuration in configurations
        }
        flavors = self.root.find("./UserConfigurations/Flavors")
        self.assertIsNotNone(flavors)
        assert flavors is not None
        self.assertEqual(flavors.get("defaultValue"), GENERATOR.DEFAULT_FLAVOR_ID)
        self.assertEqual(
            [flavor.get("id") for flavor in flavors.findall("Flavor")],
            [choice.option_id for choice in GENERATOR.FLAVOR_CHOICES],
        )

        for choice, flavor in zip(GENERATOR.FLAVOR_CHOICES, flavors.findall("Flavor")):
            with self.subTest(flavor=choice.option_id):
                self.assertEqual(flavor.get("displayName"), choice.label)
                self.assertEqual(flavor.get("screenReaderText"), choice.label)
                self.assertIn(choice.label, self.strings)
                selected = tuple(
                    (configuration.get("id"), configuration.get("optionId"))
                    for configuration in flavor.findall("Configuration")
                )
                self.assertEqual(selected, choice.configurations)
                self.assertEqual(
                    {configuration_id for configuration_id, _ in selected},
                    set(configurations_by_id),
                )
                for configuration_id, option_id in selected:
                    configuration = configurations_by_id[configuration_id]
                    valid_option_ids = {
                        option.get("id")
                        for option in configuration
                        if option.tag.endswith("Option")
                    }
                    self.assertIn(option_id, valid_option_ids)

                complication_count = dict(selected)[GENERATOR.COMPLICATION_COUNT_ID]
                flavor_slots = flavor.findall("ComplicationSlot")
                self.assertEqual(
                    [int(slot.get("slotId", "-1")) for slot in flavor_slots],
                    list(GENERATOR.COMPLICATION_LAYOUTS[complication_count]),
                )
                slots_by_id = {
                    slot.slot_id: slot for slot in GENERATOR.COMPLICATION_SLOTS
                }
                for flavor_slot in flavor_slots:
                    slot = slots_by_id[int(flavor_slot.get("slotId", "-1"))]
                    policy = flavor_slot.find("DefaultProviderPolicy")
                    self.assertIsNotNone(policy)
                    assert policy is not None
                    self.assertEqual(policy.get("defaultSystemProvider"), slot.provider)
                    self.assertEqual(policy.get("defaultSystemProviderType"), slot.provider_type)

        defaults = tuple(
            (configuration.get("id"), configuration.get("defaultValue"))
            for configuration in configurations
        )
        terminal = next(
            choice
            for choice in GENERATOR.FLAVOR_CHOICES
            if choice.option_id == GENERATOR.DEFAULT_FLAVOR_ID
        )
        self.assertEqual(terminal.configurations, defaults)
        self.assertIsNotNone(
            self.watch_face_info.find("FlavorsSupported[@value='true']")
        )

    def test_terminal_green_is_the_default_dot_and_text_color(self) -> None:
        expected_options = [choice.option_id for choice in GENERATOR.COLOR_CHOICES]
        for configuration_id in (GENERATOR.DOT_COLOR_ID, GENERATOR.TEXT_COLOR_ID):
            with self.subTest(configuration_id=configuration_id):
                colors = self.user_configuration(configuration_id)
                self.assertEqual(colors.get("defaultValue"), "terminal")
                options = colors.findall("ColorOption")
                self.assertEqual([option.get("id") for option in options], expected_options)
                terminal = colors.find("ColorOption[@id='terminal']")
                self.assertIsNotNone(terminal)
                assert terminal is not None
                terminal_colors = terminal.get("colors", "").split()
                self.assertEqual(terminal_colors, ["#28FE14", "#0C4A06", "#28FE14"])
                self.assertEqual(terminal_colors[2], terminal_colors[0])

    def test_backdrop_has_color_opacity_layout_and_visibility_controls(self) -> None:
        color = self.user_configuration(GENERATOR.BACKDROP_COLOR_ID)
        self.assertEqual(color.get("defaultValue"), GENERATOR.DEFAULT_BACKDROP_COLOR_ID)
        self.assertEqual(
            [option.get("id") for option in color.findall("ColorOption")],
            [choice.option_id for choice in GENERATOR.COLOR_CHOICES],
        )
        medium_gray = color.find("ColorOption[@id='medium_gray']")
        self.assertIsNotNone(medium_gray)
        assert medium_gray is not None
        self.assertEqual(medium_gray.get("colors"), "#757575")
        self.assertEqual(
            GENERATOR.COLOR_BACKDROP,
            f"[CONFIGURATION.{GENERATOR.BACKDROP_COLOR_ID}.0]",
        )
        self.assertEqual(
            [(choice.option_id, choice.value) for choice in GENERATOR.BACKDROP_OPACITY_CHOICES],
            [
                ("5", 13),
                ("10", 26),
                ("15", 38),
                ("30", 77),
                ("50", 128),
                ("75", 191),
                ("100", 255),
            ],
        )

        for configuration_id, default, option_ids in (
            (
                GENERATOR.BACKDROP_OPACITY_ID,
                GENERATOR.DEFAULT_BACKDROP_OPACITY_ID,
                [choice.option_id for choice in GENERATOR.BACKDROP_OPACITY_CHOICES],
            ),
            (
                GENERATOR.BACKDROP_LAYOUT_ID,
                GENERATOR.DEFAULT_BACKDROP_LAYOUT_ID,
                [choice.option_id for choice in GENERATOR.BACKDROP_LAYOUT_CHOICES],
            ),
            (
                GENERATOR.BACKDROP_VISIBILITY_ID,
                GENERATOR.DEFAULT_BACKDROP_VISIBILITY_ID,
                [option_id for option_id, _ in GENERATOR.BACKDROP_VISIBILITY_OPTIONS],
            ),
        ):
            with self.subTest(configuration_id=configuration_id):
                configuration = self.user_configuration(configuration_id)
                self.assertEqual(configuration.get("defaultValue"), default)
                self.assertEqual(
                    [option.get("id") for option in configuration.findall("ListOption")],
                    option_ids,
                )

    def test_editor_values_identify_the_setting_they_change(self) -> None:
        for configuration in self.user_configurations():
            for option in configuration:
                with self.subTest(configuration=configuration.get("id"), option=option.get("id")):
                    label_id = option.get("displayName")
                    self.assertIn(label_id, self.strings)
                    self.assertIn(":", self.strings[label_id])

    def test_editor_labels_escape_android_format_characters(self) -> None:
        for configuration in self.user_configurations():
            for option in configuration:
                label_id = option.get("displayName")
                label = self.strings[label_id]
                with self.subTest(
                    configuration=configuration.get("id"),
                    option=option.get("id"),
                ):
                    self.assertNotIn("%", label.replace("%%", ""))

    def test_every_editor_setting_has_an_existing_highlight(self) -> None:
        configurations = self.user_configurations()
        self.assertEqual(
            {configuration.get("id") for configuration in configurations},
            set(GENERATOR.CONFIGURATION_HIGHLIGHTS),
        )
        for configuration in configurations:
            with self.subTest(configuration=configuration.get("id")):
                highlight = configuration.get("highlight", "")
                self.assertTrue(highlight.startswith("@drawable/"))
                drawable_name = highlight.removeprefix("@drawable/")
                drawable = PROJECT_ROOT / f"watchface/src/main/res/drawable/{drawable_name}.xml"
                self.assertTrue(drawable.is_file())

    def test_simple_settings_are_visible_list_configurations(self) -> None:
        for setting_id, _, default, options in GENERATOR.SIMPLE_LIST_SETTINGS:
            with self.subTest(setting_id=setting_id):
                setting = self.user_configuration(setting_id)
                self.assertEqual(setting.tag, "ListConfiguration")
                self.assertEqual(setting.get("defaultValue"), default)
                self.assertEqual(
                    [option.get("id") for option in setting.findall("ListOption")],
                    [option_id for option_id, _ in options],
                )
        self.assertNotIn("BooleanConfiguration", self.xml)
        self.assertNotIn("BooleanOption", self.xml)

    def test_bit_weights_support_optional_lit_emphasis_and_active_only_modes(self) -> None:
        setting = self.user_configuration(GENERATOR.SHOW_WEIGHTS_ID)
        self.assertEqual(
            [option.get("id") for option in setting.findall("ListOption")],
            [
                GENERATOR.WEIGHTS_SHOWN_ID,
                GENERATOR.WEIGHTS_ACTIVE_ONLY_ID,
                GENERATOR.WEIGHTS_EMPHASIZED_ID,
                GENERATOR.WEIGHTS_ACTIVE_EMPHASIZED_ID,
                GENERATOR.WEIGHTS_HIDDEN_ID,
            ],
        )

        expected_visibility = GENERATOR.configuration_matches_expression(
            GENERATOR.SHOW_WEIGHTS_ID,
            GENERATOR.WEIGHT_VISIBLE_OPTION_IDS,
        )
        conditions = [
            condition
            for condition in self.root.findall("./Scene//Condition")
            if any(
                expression.get("name", "").endswith("_bit_weights_visible")
                for expression in condition.findall("./Expressions/Expression")
            )
        ]
        self.assertTrue(conditions)
        for condition in conditions:
            expressions = condition.findall("./Expressions/Expression")
            self.assertEqual(len(expressions), 1)
            self.assertEqual(expressions[0].text, expected_visibility)

            weights = condition.find("Compare/Group")
            self.assertIsNotNone(weights)
            assert weights is not None
            active = next(
                group
                for group in weights.findall("Group")
                if group.get("name", "").endswith("_weights_active")
            )
            self.assertIsNotNone(
                active.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='0']")
            )
            ambient = next(
                condition
                for condition in weights.findall("Condition")
                if any(
                    f"CONFIGURATION.{GENERATOR.SHOW_WEIGHTS_ID}"
                    in (expression.text or "")
                    for expression in condition.findall("./Expressions/Expression")
                )
            )
            self.assertIsNotNone(ambient)
            assert ambient is not None
            self.assertEqual(
                ambient.find("./Expressions/Expression").text,
                GENERATOR.configuration_matches_expression(
                    GENERATOR.SHOW_WEIGHTS_ID,
                    GENERATOR.WEIGHT_AMBIENT_OPTION_IDS,
                ),
            )
            active_weight_groups = [
                group
                for group in active.findall("Group")
                if "_weight_" in group.get("name", "")
            ]
            self.assertTrue(active_weight_groups)
            for weight_group in active_weight_groups:
                transform = weight_group.find("Transform[@target='alpha']")
                self.assertIsNotNone(transform)
                assert transform is not None
                self.assertIn(
                    f"CONFIGURATION.{GENERATOR.SHOW_WEIGHTS_ID}",
                    transform.get("value", ""),
                )
                self.assertIn(
                    f"? {GENERATOR.WEIGHT_LIT_ALPHA} : {GENERATOR.WEIGHT_UNLIT_ALPHA}",
                    transform.get("value", ""),
                )
            self.assertTrue(
                any(
                    f'CONFIGURATION.{GENERATOR.SHOW_WEIGHTS_ID}'
                    in transform.get("value", "")
                    and
                    f"? {GENERATOR.WEIGHT_LIT_ALPHA} : {GENERATOR.WEIGHT_UNLIT_ALPHA}"
                    in transform.get("value", "")
                    for transform in ambient.findall(
                        ".//Transform[@target='alpha']"
                    )
                )
            )
            self.assertIsNotNone(condition.find("Default/Group"))

    def test_reference_appearance_size_effect_and_tick_options_are_available(self) -> None:
        expected = (
            (GENERATOR.APPEARANCE_ID, "dark", ["dark", "light"]),
            (GENERATOR.SIZE_ID, "large", ["tiny", "small", "normal", "large", "huge"]),
            (GENERATOR.CLOCK_MODE_ID, "24", ["12", "24"]),
            (GENERATOR.DOT_EFFECT_ID, "glow", ["none", "glow", "bezel"]),
            (GENERATOR.TICK_STYLE_ID, "all", ["none", "single", "wave", "boost", "all"]),
        )
        for configuration_id, default, option_ids in expected:
            with self.subTest(configuration_id=configuration_id):
                configuration = self.user_configuration(configuration_id)
                self.assertEqual(configuration.get("defaultValue"), default)
                self.assertEqual([option.get("id") for option in configuration], option_ids)

    def test_bezel_effect_draws_a_visible_ring_and_core(self) -> None:
        bezel = next(
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_bezel")
        )
        ellipses = bezel.findall("./PartDraw/Ellipse")
        self.assertEqual(len(ellipses), 3)
        self.assertEqual(
            [ellipse.find("Fill").get("color") for ellipse in ellipses],
            [
                GENERATOR.COLOR_DOT_ACTIVE,
                GENERATOR.COLOR_BACKGROUND,
                GENERATOR.COLOR_DOT_ACTIVE,
            ],
        )

    def test_true_binary_rows_cover_12_and_24_hour_time(self) -> None:
        self.assertEqual(GENERATOR.HOUR_12_WEIGHTS, (8, 4, 2, 1))
        self.assertEqual(GENERATOR.HOUR_24_WEIGHTS, (16, 8, 4, 2, 1))
        self.assertEqual(GENERATOR.SIX_BIT_WEIGHTS, (32, 16, 8, 4, 2, 1))
        self.assertIn("[HOUR_1_12]", self.xml)
        self.assertIn("[HOUR_0_23]", self.xml)
        self.assertNotIn("[IS_24_HOUR_MODE]", self.xml)
        self.assertIn("floor(([HOUR_0_23]) / 16) % 2 == 1 ? 255 : 0", self.xml)
        self.assertIn("floor(([MINUTE]) / 32) % 2 == 1 ? 255 : 0", self.xml)

    def test_clock_tree_is_shared_across_complication_layouts(self) -> None:
        clock_modes = self.root.findall(
            f"./Scene/ListConfiguration[@id='{GENERATOR.CLOCK_MODE_ID}']"
        )
        self.assertEqual(len(clock_modes), 1)
        self.assertEqual(
            [option.get("id") for option in clock_modes[0].findall("ListOption")],
            ["12", "24"],
        )
        self.assertEqual(
            self.root.findall(
                f"./Scene/ListConfiguration[@id='{GENERATOR.COMPLICATION_COUNT_ID}']"
            ),
            [],
        )

    def test_clock_rows_use_the_available_space_when_seconds_are_hidden(self) -> None:
        self.assertEqual(GENERATOR.CLOCK_ROW_LAYOUT[False], (150, 210))
        self.assertEqual(GENERATOR.CLOCK_ROW_LAYOUT[True], (106, 162, 218))
        large_size = next(
            size for size in GENERATOR.SIZE_CHOICES if size.option_id == "large"
        )
        large_dot_size = round(GENERATOR.REFERENCE_DOT_SIZE * large_size.scale)
        no_seconds_bottom = GENERATOR.CLOCK_ROW_LAYOUT[False][-1] + large_dot_size
        seconds_bottom = GENERATOR.CLOCK_ROW_LAYOUT[True][-1] + large_dot_size
        complication_top = min(slot.y for slot in GENERATOR.COMPLICATION_SLOTS[:2])
        self.assertLessEqual(complication_top - no_seconds_bottom, 52)
        self.assertLessEqual(complication_top - seconds_bottom, 44)

    def test_ticks_render_above_the_clock_and_below_complications(self) -> None:
        scene = self.root.find("Scene")
        self.assertIsNotNone(scene)
        assert scene is not None
        children = list(scene)
        clock_index = next(
            index
            for index, child in enumerate(children)
            if child.tag == "ListConfiguration" and child.get("id") == GENERATOR.CLOCK_MODE_ID
        )
        tick_index = next(
            index
            for index, child in enumerate(children)
            if child.tag == "ListConfiguration" and child.get("id") == GENERATOR.TICK_STYLE_ID
        )
        complication_indexes = [
            index for index, child in enumerate(children) if child.tag == "ComplicationSlot"
        ]
        self.assertLess(clock_index, tick_index)
        self.assertTrue(complication_indexes)
        self.assertLess(tick_index, min(complication_indexes))

    def test_binary_rows_share_endpoints_and_distribute_their_bits(self) -> None:
        for size in GENERATOR.SIZE_CHOICES:
            with self.subTest(size=size.option_id):
                geometries = {bit_count: GENERATOR.bit_geometry(bit_count, size) for bit_count in (4, 5, 6)}
                endpoints = {(positions[0], positions[-1]) for _, positions in geometries.values()}
                self.assertEqual(len(endpoints), 1)
                for bit_count, (dot_size, positions) in geometries.items():
                    self.assertEqual(len(positions), bit_count)
                    self.assertEqual(tuple(sorted(positions)), positions)
                    self.assertEqual(dot_size, round(GENERATOR.REFERENCE_DOT_SIZE * size.scale))

        large = next(size for size in GENERATOR.SIZE_CHOICES if size.option_id == "large")
        self.assertEqual(GENERATOR.bit_geometry(4, large), (25, (110, 178, 248, 316)))
        self.assertEqual(GENERATOR.bit_geometry(5, large), (25, (110, 160, 212, 264, 316)))
        self.assertEqual(GENERATOR.bit_geometry(6, large), (25, (110, 150, 192, 234, 274, 316)))

    def test_display_size_scales_one_shared_row_tree(self) -> None:
        self.assertEqual(
            self.root.findall(
                f"./Scene//ListConfiguration[@id='{GENERATOR.SIZE_ID}']"
            ),
            [],
        )
        expected_expression = GENERATOR.configuration_value_expression(
            GENERATOR.SIZE_ID,
            GENERATOR.DISPLAY_SIZE_VALUES,
            GENERATOR.DEFAULT_SIZE_ID,
        )
        scaled_rows = [
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_scaled")
        ]
        self.assertTrue(scaled_rows)
        for row in scaled_rows:
            with self.subTest(row=row.get("name")):
                transforms = {
                    transform.get("target"): transform.get("value")
                    for transform in row.findall("Transform")
                }
                self.assertEqual(
                    transforms,
                    {
                        "scaleX": expected_expression,
                        "scaleY": expected_expression,
                    },
                )
                self.assertEqual(
                    len(
                        [
                            group
                            for group in row.iter("Group")
                            if group.get("name", "").endswith("_scaled")
                        ]
                    ),
                    1,
                )

    def test_battery_readout_defaults_to_decimal_and_supports_other_bases(self) -> None:
        configuration = self.user_configuration(GENERATOR.BATTERY_DISPLAY_ID)
        self.assertEqual(configuration.get("defaultValue"), "decimal")
        self.assertEqual(
            [option.get("id") for option in configuration.findall("ListOption")],
            [option_id for option_id, _ in GENERATOR.BATTERY_DISPLAY_OPTIONS],
        )

        scene_configuration = next(
            condition
            for condition in self.root.findall("./Scene/Condition")
            if condition.find("./Expressions/Expression[@name='battery_decimal_visible']")
            is not None
        )
        self.assertIsNotNone(scene_configuration)
        assert scene_configuration is not None
        battery_expressions = {
            expression.get("name"): expression.text
            for expression in scene_configuration.findall("./Expressions/Expression")
        }
        self.assertEqual(
            battery_expressions,
            {
                "battery_decimal_visible": GENERATOR.configuration_matches_expression(
                    GENERATOR.BATTERY_DISPLAY_ID,
                    GENERATOR.BATTERY_DECIMAL_OPTION_IDS,
                ),
                "battery_hex_visible": GENERATOR.configuration_matches_expression(
                    GENERATOR.BATTERY_DISPLAY_ID,
                    GENERATOR.BATTERY_HEX_OPTION_IDS,
                ),
                "battery_binary_visible": GENERATOR.configuration_matches_expression(
                    GENERATOR.BATTERY_DISPLAY_ID,
                    GENERATOR.BATTERY_BINARY_OPTION_IDS,
                ),
            },
        )
        hex_template = scene_configuration.find("./Compare[@expression='battery_hex_visible']/.//Template")
        self.assertIsNotNone(hex_template)
        assert hex_template is not None
        self.assertEqual(hex_template.text, "0x%x")
        binary_templates = {
            template.text
            for template in scene_configuration.findall("./Compare[@expression='battery_binary_visible']/.//Template")
        }
        self.assertIn("0b%d", binary_templates)
        self.assertIn("0b%d%d%d%d%d%d%d", binary_templates)
        battery_text = scene_configuration.findall(".//PartText")
        self.assertTrue(battery_text)
        self.assertTrue(
            all(text.get("x") == str(GENERATOR.BATTERY_READOUT_X) for text in battery_text)
        )
        self.assertTrue(
            all(text.get("y") == str(GENERATOR.NATIVE_READOUT_Y) for text in battery_text)
        )

    def test_native_heart_rate_balances_battery_above_complications(self) -> None:
        scene_configuration = next(
            condition
            for condition in self.root.findall("./Scene/Condition")
            if condition.find("./Expressions/Expression[@name='heart_rate_active_visible']")
            is not None
        )
        self.assertIsNotNone(scene_configuration)
        assert scene_configuration is not None
        self.assertEqual(
            scene_configuration.find(
                "./Expressions/Expression[@name='heart_rate_active_visible']"
            ).text,
            GENERATOR.configuration_matches_expression(
                GENERATOR.BATTERY_DISPLAY_ID,
                GENERATOR.HEART_RATE_ACTIVE_OPTION_IDS,
            ),
        )
        self.assertEqual(
            scene_configuration.find(
                ".//Expression[@name='heart_rate_ambient_visible']"
            ).text,
            GENERATOR.configuration_matches_expression(
                GENERATOR.BATTERY_DISPLAY_ID,
                GENERATOR.HEART_RATE_AMBIENT_OPTION_IDS,
            ),
        )
        active = scene_configuration.find(".//Group[@name='heart_rate_active']")
        self.assertIsNotNone(active)
        assert active is not None

        available = active.find(".//Expression[@name='heart_rate_active_available']")
        self.assertIsNotNone(available)
        assert available is not None
        self.assertEqual(available.text, "round([HEART_RATE]) > 0")

        value = active.find(".//PartText[@name='heart_rate_active_value']")
        unavailable = active.find(".//PartText[@name='heart_rate_active_unavailable']")
        self.assertIsNotNone(value)
        self.assertIsNotNone(unavailable)
        assert value is not None and unavailable is not None
        for text in (value, unavailable):
            self.assertEqual(text.get("x"), str(GENERATOR.HEART_RATE_READOUT_X))
            self.assertEqual(text.get("y"), str(GENERATOR.NATIVE_READOUT_Y))
            self.assertEqual(text.get("width"), str(GENERATOR.NATIVE_READOUT_WIDTH))

        value_template = value.find(".//Template")
        self.assertIsNotNone(value_template)
        assert value_template is not None
        self.assertEqual(
            value_template.text,
            f"%d{GENERATOR.HEART_RATE_ACTIVE_GLYPH}",
        )
        self.assertEqual(
            [parameter.get("expression") for parameter in value_template.findall("Parameter")],
            ["round([HEART_RATE])"],
        )
        unavailable_font = unavailable.find(".//Font")
        self.assertIsNotNone(unavailable_font)
        assert unavailable_font is not None
        self.assertEqual(
            unavailable_font.text,
            f"--{GENERATOR.HEART_RATE_ACTIVE_GLYPH}",
        )

        ambient_values = [
            text
            for text in self.root.findall(".//PartText")
            if text.get("name", "").startswith("heart_rate_ambient_")
            and text.get("name", "").endswith("_value")
        ]
        ambient_unavailable = [
            text
            for text in self.root.findall(".//PartText")
            if text.get("name", "").startswith("heart_rate_ambient_")
            and text.get("name", "").endswith("_unavailable")
        ]
        self.assertTrue(ambient_values)
        self.assertTrue(ambient_unavailable)
        self.assertTrue(
            scene_configuration.findall(
                ".//Compare[@expression='heart_rate_ambient_visible']/.//PartText"
            )
        )
        self.assertIsNotNone(
            scene_configuration.find("./Default/Group[@name='heart_rate_hidden']")
        )
        self.assertTrue(
            all(
                text.find(".//Template").text
                == f"%d{GENERATOR.HEART_RATE_AMBIENT_GLYPH}"
                for text in ambient_values
            )
        )
        self.assertTrue(
            all(
                text.find(".//Font").text
                == f"--{GENERATOR.HEART_RATE_AMBIENT_GLYPH}"
                for text in ambient_unavailable
            )
        )

        battery_center = GENERATOR.BATTERY_READOUT_X + GENERATOR.NATIVE_READOUT_WIDTH / 2
        heart_rate_center = (
            GENERATOR.HEART_RATE_READOUT_X + GENERATOR.NATIVE_READOUT_WIDTH / 2
        )
        self.assertEqual(battery_center + heart_rate_center, GENERATOR.WATCH_SIZE)
        self.assertEqual(
            GENERATOR.HEART_RATE_READOUT_X
            + GENERATOR.NATIVE_READOUT_WIDTH
            - GENERATOR.BATTERY_READOUT_X,
            GENERATOR.NATIVE_READOUT_HORIZONTAL_OVERLAP,
        )

    def test_date_controls_cover_reference_formats_and_ambient_options(self) -> None:
        date = self.user_configuration(GENERATOR.DATE_FORMAT_ID)
        self.assertEqual(date.get("defaultValue"), "iso")
        self.assertEqual(
            [option.get("id") for option in date.findall("ListOption")],
            [specification.option_id for specification in GENERATOR.DATE_FORMATS] + ["off"],
        )
        defaults = {
            GENERATOR.SHOW_WEEKDAY_ID: "TRUE",
            GENERATOR.AMBIENT_INFO_ID: "off",
            GENERATOR.AMBIENT_COLOR_ID: "TRUE",
        }
        for configuration_id, default in defaults.items():
            self.assertEqual(self.user_configuration(configuration_id).get("defaultValue"), default)
        date_style = self.user_configuration(GENERATOR.SHOW_WEEKDAY_ID)
        self.assertEqual(
            [option.get("id") for option in date_style.findall("ListOption")],
            [choice.option_id for choice in GENERATOR.DATE_STYLE_CHOICES],
        )

    def test_ambient_information_presets_control_date_weekday_and_bottom_readouts(self) -> None:
        ambient_info = self.user_configuration(GENERATOR.AMBIENT_INFO_ID)
        self.assertEqual(
            [option.get("id") for option in ambient_info.findall("ListOption")],
            [option_id for option_id, _ in GENERATOR.AMBIENT_INFO_OPTIONS],
        )

        date = self.root.find(
            f"./Scene/ListConfiguration[@id='{GENERATOR.DATE_FORMAT_ID}']"
        )
        battery = next(
            condition
            for condition in self.root.findall("./Scene/Condition")
            if condition.find("./Expressions/Expression[@name='battery_decimal_visible']")
            is not None
        )
        self.assertIsNotNone(date)
        self.assertIsNotNone(battery)
        assert date is not None and battery is not None
        date_expressions = {
            expression.get("name"): expression.text
            for expression in date.findall(".//Expression")
            if expression.get("name", "").startswith("ambient_info_")
        }
        self.assertEqual(
            set(date_expressions.values()),
            {
                GENERATOR.configuration_matches_expression(
                    GENERATOR.AMBIENT_INFO_ID,
                    GENERATOR.AMBIENT_DATE_OPTION_IDS,
                ),
                GENERATOR.configuration_matches_expression(
                    GENERATOR.AMBIENT_INFO_ID,
                    GENERATOR.AMBIENT_WEEKDAY_OPTION_IDS,
                ),
            },
        )
        expected_battery_visibility = (
            f"({GENERATOR.configuration_matches_expression(GENERATOR.AMBIENT_INFO_ID, GENERATOR.AMBIENT_BATTERY_OPTION_IDS)}) "
            "? 255 : 0"
        )
        battery_visibility = [
            transform.get("value")
            for transform in battery.findall(".//Transform[@target='alpha']")
            if "CONFIGURATION.ambientInfo" in transform.get("value", "")
        ]
        self.assertTrue(battery_visibility)
        self.assertTrue(
            all(value == expected_battery_visibility for value in battery_visibility)
        )
        heart_rate = next(
            condition
            for condition in self.root.findall("./Scene/Condition")
            if condition.find("./Expressions/Expression[@name='heart_rate_active_visible']")
            is not None
        )
        self.assertIsNotNone(heart_rate)
        assert heart_rate is not None
        self.assertFalse(
            any(
                "CONFIGURATION.ambientInfo" in transform.get("value", "")
                for transform in heart_rate.findall(".//Transform")
            )
        )

    def test_complication_count_options_enable_exact_layouts(self) -> None:
        configuration = self.user_configuration(GENERATOR.COMPLICATION_COUNT_ID)
        options = {
            option.get("id"): tuple(int(value) for value in option.get("complicationSlotIds", "").split())
            for option in configuration.findall("ListOption")
        }
        self.assertEqual(options, GENERATOR.COMPLICATION_LAYOUTS)
        self.assertEqual(
            options,
            {"0": (), "2": (0, 1), "3": (0, 1, 2), "4": (0, 1, 3, 4)},
        )
        zero = configuration.find("ListOption[@id='0']")
        self.assertIsNotNone(zero)
        assert zero is not None
        self.assertNotIn("complicationSlotIds", zero.attrib)

        declared = {
            int(slot.get("slotId", "-1"))
            for slot in self.root.findall("./Scene/ComplicationSlot")
        }
        enabled = {slot_id for layout in options.values() for slot_id in layout}
        self.assertEqual(enabled, declared)

    def test_minimal_flavor_hides_every_non_clock_element(self) -> None:
        minimal = next(
            choice
            for choice in GENERATOR.FLAVOR_CHOICES
            if choice.option_id == "minimal"
        )
        selected = dict(minimal.configurations)
        self.assertEqual(selected[GENERATOR.BACKDROP_VISIBILITY_ID], "off")
        self.assertEqual(selected[GENERATOR.DOT_EFFECT_ID], "none")
        self.assertEqual(selected[GENERATOR.TICK_STYLE_ID], "none")
        self.assertEqual(selected[GENERATOR.SHOW_SECONDS_ID], "FALSE")
        self.assertEqual(selected[GENERATOR.SHOW_WEIGHTS_ID], GENERATOR.WEIGHTS_HIDDEN_ID)
        self.assertEqual(selected[GENERATOR.DATE_FORMAT_ID], "off")
        self.assertEqual(selected[GENERATOR.BATTERY_DISPLAY_ID], "off_heart_off")
        self.assertEqual(selected[GENERATOR.COMPLICATION_COUNT_ID], "0")
        flavor = self.root.find("./UserConfigurations/Flavors/Flavor[@id='minimal']")
        self.assertIsNotNone(flavor)
        assert flavor is not None
        self.assertEqual(flavor.findall("ComplicationSlot"), [])

    def test_complication_layout_preserves_prioritized_lower_pair(self) -> None:
        slots = {
            int(slot.get("slotId", "-1")): slot
            for slot in self.root.findall("./Scene/ComplicationSlot")
        }
        self.assertEqual(
            tuple(slots[0].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("lower_left", "73", "286", "92", "92"),
        )
        self.assertEqual(
            tuple(slots[1].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("lower_right", "285", "286", "92", "92"),
        )
        self.assertEqual(
            tuple(slots[2].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("lower_center", "190", "290", "70", "70"),
        )
        self.assertEqual(
            tuple(slots[3].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("middle_left", "24", "218", "76", "76"),
        )
        self.assertEqual(
            tuple(slots[4].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("middle_right", "350", "218", "76", "76"),
        )

        lower_left, lower_right, lower_center, side_left, side_right = (
            GENERATOR.COMPLICATION_SLOTS
        )
        self.assertGreater(lower_left.size, side_left.size)
        self.assertGreater(side_left.size, lower_center.size)
        self.assertEqual(lower_left.size, lower_right.size)
        self.assertEqual(side_left.size, side_right.size)
        self.assertEqual(lower_left.x, GENERATOR.WATCH_SIZE - lower_right.x - lower_right.size)
        self.assertEqual(side_left.x, GENERATOR.WATCH_SIZE - side_right.x - side_right.size)
        self.assertEqual(
            lower_right.x - lower_left.x - lower_left.size,
            GENERATOR.LOWER_COMPLICATION_PAIR_GAP,
        )

    complication_circle = staticmethod(LAYOUT.complication_circle)
    circle_rectangle_gap = staticmethod(LAYOUT.circle_rectangle_gap)

    def native_readout_bounds(self) -> list[tuple[float, float, float, float]]:
        return list(LAYOUT.native_readouts(self.root))

    def test_native_readouts_clear_the_largest_clock_and_every_complication(self) -> None:
        largest = max(GENERATOR.SIZE_CHOICES, key=lambda size: size.scale)
        base = next(size for size in GENERATOR.SIZE_CHOICES if size.option_id == GENERATOR.BASE_SIZE_ID)
        dot_size, _ = GENERATOR.bit_geometry(len(GENERATOR.SIX_BIT_WEIGHTS), base)
        clock_bottom = max(max(rows) for rows in GENERATOR.CLOCK_ROW_LAYOUT.values()) + dot_size / 2 * (1 + largest.scale)
        slots = self.root.findall("./Scene/ComplicationSlot")
        for bounds in self.native_readout_bounds():
            with self.subTest(bounds=bounds):
                self.assertGreaterEqual(bounds[1] - clock_bottom, MIN_CONTENT_GAP)
                for slot in slots:
                    self.assertGreaterEqual(
                        self.circle_rectangle_gap(slot, bounds),
                        MIN_CONTENT_GAP,
                        slot.get("name"),
                    )

    def test_system_indicator_region_clears_readouts_and_complication_outlines(self) -> None:
        margin = GENERATOR.SYSTEM_INDICATOR_CLEARANCE
        regions = (
            (GENERATOR.SYSTEM_INDICATOR_BOUNDS, 0),
            (GENERATOR.SYSTEM_ACTIVITY_PILL_BOUNDS, GENERATOR.SYSTEM_ACTIVITY_PILL_CORNER_RADIUS),
        )
        for bounds, corner_radius in regions:
            left, top, right, bottom = bounds
            with self.subTest(bounds=bounds, corner_radius=corner_radius):
                self.assertEqual(left + right, GENERATOR.WATCH_SIZE)
                self.assertEqual(bottom, GENERATOR.WATCH_SIZE)
                self.assertGreater(right - left, GENERATOR.NATIVE_READOUT_WIDTH)
                self.assertLessEqual(2 * corner_radius, min(right - left, bottom - top))
                for readout_left, readout_top, readout_right, readout_bottom in self.native_readout_bounds():
                    self.assertTrue(
                        readout_right <= left - margin
                        or readout_left >= right + margin
                        or readout_bottom <= top - margin
                        or readout_top >= bottom + margin
                    )
                inset_bounds = (
                    left + corner_radius,
                    top + corner_radius,
                    right - corner_radius,
                    bottom - corner_radius,
                )
                for slot in self.root.findall("./Scene/ComplicationSlot"):
                    with self.subTest(slot=slot.get("name")):
                        gap = self.circle_rectangle_gap(slot, inset_bounds) - corner_radius
                        self.assertGreaterEqual(gap, margin)

    def test_enabled_complications_keep_space_between_their_outlines(self) -> None:
        slots = {
            int(slot.get("slotId", "-1")): slot
            for slot in self.root.findall("./Scene/ComplicationSlot")
        }
        for count, ids in GENERATOR.COMPLICATION_LAYOUTS.items():
            for index, slot_id in enumerate(ids):
                center_x, center_y, radius = self.complication_circle(slots[slot_id])
                for other_id in ids[index + 1:]:
                    other_x, other_y, other_radius = self.complication_circle(slots[other_id])
                    gap = math.hypot(center_x - other_x, center_y - other_y) - radius - other_radius
                    with self.subTest(count=count, slots=(slot_id, other_id)):
                        self.assertGreaterEqual(gap, MIN_CONTENT_GAP)

    def test_every_tick_position_remains_visible_beyond_complications(self) -> None:
        tick_configuration = self.root.find(
            f"./Scene/ListConfiguration[@id='{GENERATOR.TICK_STYLE_ID}']"
        )
        self.assertIsNotNone(tick_configuration)
        assert tick_configuration is not None
        dial_center = GENERATOR.WATCH_SIZE / 2
        tick_markers = tick_configuration.findall(".//PartDraw/RoundRectangle")
        self.assertTrue(tick_markers)
        for marker in tick_markers:
            marker_x = float(marker.get("x", "0"))
            marker_width = float(marker.get("width", "0"))
            self.assertAlmostEqual(marker_x + marker_width / 2, dial_center)

        minimum_tick_outer_radius = min(
            dial_center - float(marker.get("y", "0")) for marker in tick_markers
        )
        complication_outer_radii = []
        for slot in self.root.findall("./Scene/ComplicationSlot"):
            bounding_oval = slot.find("BoundingOval")
            self.assertIsNotNone(bounding_oval)
            assert bounding_oval is not None
            oval_width = float(bounding_oval.get("width", "0"))
            oval_height = float(bounding_oval.get("height", "0"))
            self.assertEqual(oval_width, oval_height)
            oval_center_x = (
                float(slot.get("x", "0"))
                + float(bounding_oval.get("x", "0"))
                + oval_width / 2
            )
            oval_center_y = (
                float(slot.get("y", "0"))
                + float(bounding_oval.get("y", "0"))
                + oval_height / 2
            )
            complication_outer_radii.append(
                math.hypot(
                    oval_center_x - dial_center,
                    oval_center_y - dial_center,
                )
                + oval_width / 2
            )
        self.assertTrue(complication_outer_radii)

        visible_annulus_width = (
            minimum_tick_outer_radius - max(complication_outer_radii)
        )
        self.assertGreaterEqual(visible_annulus_width, MIN_VISIBLE_TICK_LENGTH)

    def test_complication_slots_clear_the_largest_clock_and_each_other(self) -> None:
        largest = max(GENERATOR.SIZE_CHOICES, key=lambda size: size.scale)
        base = next(
            size for size in GENERATOR.SIZE_CHOICES if size.option_id == GENERATOR.BASE_SIZE_ID
        )
        clock_center = GENERATOR.WATCH_SIZE / 2
        side_left, side_right = GENERATOR.COMPLICATION_SLOTS[3:5]
        for side_slot in (side_left, side_right):
            slot_center_x = side_slot.x + side_slot.size / 2
            slot_center_y = side_slot.y + side_slot.size / 2
            distance_from_dial_center = math.hypot(
                slot_center_x - clock_center,
                slot_center_y - clock_center,
            )
            self.assertLessEqual(
                distance_from_dial_center + side_slot.size / 2,
                clock_center,
            )

        dot_size, positions = GENERATOR.bit_geometry(len(GENERATOR.SIX_BIT_WEIGHTS), base)
        scaled_dot_radius = dot_size * largest.scale / 2
        for row_positions in GENERATOR.CLOCK_ROW_LAYOUT.values():
            for row_y in row_positions:
                row_center_y = row_y + dot_size / 2
                scaled_weight_bottom = row_center_y + largest.scale * (
                    row_y - 23 + 18 - row_center_y
                )
                for side_slot in (side_left, side_right):
                    self.assertGreaterEqual(side_slot.y, scaled_weight_bottom)
                    side_center_x = side_slot.x + side_slot.size / 2
                    side_center_y = side_slot.y + side_slot.size / 2
                    for dot_x in positions:
                        dot_center_x = clock_center + largest.scale * (
                            dot_x + dot_size / 2 - clock_center
                        )
                        center_distance = math.hypot(
                            side_center_x - dot_center_x,
                            side_center_y - row_center_y,
                        )
                        self.assertGreaterEqual(
                            center_distance,
                            side_slot.size / 2 + scaled_dot_radius,
                        )

        base_dot_size, _ = GENERATOR.bit_geometry(len(GENERATOR.SIX_BIT_WEIGHTS), base)
        lowest_row = GENERATOR.CLOCK_ROW_LAYOUT[True][-1]
        row_center = lowest_row + base_dot_size / 2
        scaled_dot_bottom = row_center + largest.scale * (
            lowest_row + base_dot_size - row_center
        )
        center_slot = GENERATOR.COMPLICATION_SLOTS[2]
        self.assertGreaterEqual(center_slot.y - scaled_dot_bottom, 20)

        center_x = center_slot.x + center_slot.size / 2
        center_y = center_slot.y + center_slot.size / 2
        for side_slot, lower_slot in zip(
            (side_left, side_right), GENERATOR.COMPLICATION_SLOTS[:2]
        ):
            side_x = side_slot.x + side_slot.size / 2
            side_y = side_slot.y + side_slot.size / 2
            lower_x = lower_slot.x + lower_slot.size / 2
            lower_y = lower_slot.y + lower_slot.size / 2
            center_distance = math.hypot(side_x - lower_x, side_y - lower_y)
            radius_sum = (side_slot.size + lower_slot.size) / 2
            self.assertGreater(center_distance, radius_sum)
        for lower_slot in GENERATOR.COMPLICATION_SLOTS[:2]:
            lower_x = lower_slot.x + lower_slot.size / 2
            lower_y = lower_slot.y + lower_slot.size / 2
            center_distance = math.hypot(center_x - lower_x, center_y - lower_y)
            radius_sum = (center_slot.size + lower_slot.size) / 2
            self.assertGreater(center_distance, radius_sum)

    def test_every_complication_supports_the_promised_types(self) -> None:
        expected = {"SHORT_TEXT", "MONOCHROMATIC_IMAGE", "SMALL_IMAGE", "RANGED_VALUE", "EMPTY"}
        for slot in self.root.findall("./Scene/ComplicationSlot"):
            self.assertEqual(set(slot.get("supportedTypes", "").split()), expected)
            rendered = {complication.get("type") for complication in slot.findall("Complication")}
            self.assertEqual(rendered, expected)

    def test_default_complications_are_distinct_from_face_readouts(self) -> None:
        policies = self.root.findall("./Scene/ComplicationSlot/DefaultProviderPolicy")
        providers = [policy.get("defaultSystemProvider") for policy in policies]
        self.assertEqual(
            providers,
            [specification.provider for specification in GENERATOR.COMPLICATION_SLOTS],
        )
        self.assertEqual(len(providers), len(set(providers)))
        self.assertNotIn("WATCH_BATTERY", providers)
        self.assertNotIn("DATE", providers)
        self.assertNotIn("HEART_RATE", providers)
        self.assertEqual(
            [(slot.provider, slot.provider_type) for slot in GENERATOR.COMPLICATION_SLOTS[:3]],
            [
                ("STEP_COUNT", "SHORT_TEXT"),
                ("UNREAD_NOTIFICATION_COUNT", "SHORT_TEXT"),
                ("NEXT_EVENT", "SHORT_TEXT"),
            ],
        )

    def test_face_has_no_custom_launch_actions(self) -> None:
        self.assertEqual(self.root.findall(".//Launch"), [])

    def test_ambient_mode_uses_dense_patterned_dots_and_suppresses_high_activity_elements(self) -> None:
        self.assertEqual(GENERATOR.COLOR_AMBIENT_MONO, "#FFFFFF")

        brightness = self.user_configuration(GENERATOR.AMBIENT_COLOR_ID)
        self.assertEqual(
            brightness.get("defaultValue"),
            GENERATOR.DEFAULT_AMBIENT_APPEARANCE_ID,
        )
        self.assertEqual(
            [option.get("id") for option in brightness.findall("ListOption")],
            [choice.option_id for choice in GENERATOR.AMBIENT_APPEARANCE_CHOICES],
        )
        self.assertEqual(
            [
                (choice.option_id, choice.alpha, choice.uses_color)
                for choice in GENERATOR.AMBIENT_APPEARANCE_CHOICES
            ],
            [
                ("dim_color", 128, True),
                ("TRUE", 192, True),
                ("bright_color", 255, True),
                ("dim_mono", 128, False),
                ("FALSE", 192, False),
                ("bright_mono", 255, False),
            ],
        )
        self.assertEqual(
            GENERATOR.AMBIENT_COLOR_OPTION_IDS,
            ("dim_color", "TRUE", "bright_color"),
        )
        brightness_expression = GENERATOR.ambient_brightness_expression()
        self.assertEqual(
            brightness_expression,
            GENERATOR.configuration_value_expression(
                GENERATOR.AMBIENT_COLOR_ID,
                GENERATOR.AMBIENT_BRIGHTNESS_VALUES,
                GENERATOR.DEFAULT_AMBIENT_APPEARANCE_ID,
            ),
        )

        scene = self.root.find("Scene")
        self.assertIsNotNone(scene)
        assert scene is not None
        self.assertEqual(
            scene.findall(
                f".//ListConfiguration[@id='{GENERATOR.AMBIENT_COLOR_ID}']"
            ),
            [],
        )
        expected_color_expression = GENERATOR.configuration_matches_expression(
            GENERATOR.AMBIENT_COLOR_ID,
            GENERATOR.AMBIENT_COLOR_OPTION_IDS,
        )
        ambient_color_conditions = [
            condition
            for condition in scene.iter("Condition")
            if any(
                f"CONFIGURATION.{GENERATOR.AMBIENT_COLOR_ID}" in (expression.text or "")
                for expression in condition.findall("./Expressions/Expression")
            )
        ]
        self.assertTrue(ambient_color_conditions)
        for condition in ambient_color_conditions:
            expressions = condition.findall("./Expressions/Expression")
            self.assertEqual(len(expressions), 1)
            self.assertEqual(expressions[0].text, expected_color_expression)
            self.assertIsNotNone(condition.find("Compare/Group"))
            self.assertIsNotNone(condition.find("Default/Group"))
        self.assertEqual(scene.get("backgroundColor"), GENERATOR.COLOR_BLACK)
        active_background = scene.find("Group[@name='active_background']")
        self.assertIsNotNone(active_background)
        assert active_background is not None
        self.assertIsNotNone(
            active_background.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='0']")
        )
        self.assertEqual(
            active_background.find("PartDraw/Rectangle/Fill").get("color"),
            GENERATOR.COLOR_BACKGROUND,
        )

        pattern = self.root.find(".//PartDraw[@name='ambient_dither']")
        self.assertIsNotNone(pattern)
        assert pattern is not None
        lines = pattern.findall("Line")
        self.assertEqual(len(lines), GENERATOR.AMBIENT_DITHER_ROW_COUNT)
        first_stroke = lines[0].find("Stroke")
        self.assertIsNotNone(first_stroke)
        assert first_stroke is not None
        expected_intervals = (
            f"{int(first_stroke.get('thickness', '0')) * GENERATOR.AMBIENT_DITHER_DASH_MULTIPLIER} "
            f"{GENERATOR.AMBIENT_DITHER_GAP}"
        )
        self.assertTrue(
            all(
                stroke is not None and stroke.get("dashIntervals") == expected_intervals
                for stroke in (line.find("Stroke") for line in lines)
            )
        )

        seconds_rows = [
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_second_row")
        ]
        self.assertGreater(len(seconds_rows), 0)
        self.assertTrue(
            all(row.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='0']") is not None for row in seconds_rows)
        )

        tick_groups = [
            group
            for group in self.root.iter("Group")
            if group.get("name", "").startswith("ticks_") and group.get("name") != "ticks_none"
        ]
        self.assertTrue(
            all(group.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='0']") is not None for group in tick_groups)
        )

        for slot in self.root.findall("./Scene/ComplicationSlot"):
            self.assertIsNotNone(
                slot.find(
                    f"Variant[@mode='AMBIENT'][@target='alpha'][@value='{brightness_expression}']"
                )
            )

        ambient_face_groups = [
            group
            for group in self.root.iter("Group")
            if "ambient" in group.get("name", "")
            and not group.get("name", "").endswith("_small_image_ambient")
            and group.find("Variant[@mode='AMBIENT'][@target='alpha']") is not None
        ]
        self.assertTrue(ambient_face_groups)
        self.assertTrue(
            all(
                group.find("Variant[@mode='AMBIENT'][@target='alpha']").get("value")
                == brightness_expression
                for group in ambient_face_groups
            )
        )
        for complication in self.root.findall(".//Complication[@type='SMALL_IMAGE']"):
            active = next(
                group
                for group in complication.findall("Group")
                if group.get("name", "").endswith("_small_image_active")
            )
            self.assertIsNotNone(
                active.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='0']")
            )
            self.assertEqual(
                active.find("./PartImage/Image").get("resource"),
                "[COMPLICATION.SMALL_IMAGE]",
            )

            condition = complication.find("Condition")
            self.assertIsNotNone(condition)
            assert condition is not None
            expression = condition.find("./Expressions/Expression")
            self.assertIsNotNone(expression)
            assert expression is not None
            self.assertEqual(
                expression.text,
                "[COMPLICATION.SMALL_IMAGE_AMBIENT] != null",
            )
            compare = condition.find("Compare")
            self.assertIsNotNone(compare)
            assert compare is not None
            ambient = compare.find("Group")
            self.assertIsNotNone(ambient)
            assert ambient is not None
            self.assertIsNotNone(
                ambient.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='255']")
            )
            self.assertEqual(
                ambient.find("./PartImage/Image").get("resource"),
                "[COMPLICATION.SMALL_IMAGE_AMBIENT]",
            )
            missing = condition.find("./Default/Group")
            self.assertIsNotNone(missing)
            assert missing is not None
            self.assertEqual(missing.get("alpha"), "0")
            self.assertEqual(missing.findall(".//PartDraw"), [])

    def test_decimal_background_spans_the_full_dial(self) -> None:
        active = self.root.find(".//PartText[@name='hour_decimal_backdrop_active']")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(
            tuple(active.get(attribute) for attribute in ("x", "y", "width", "height")),
            ("0", "0", "450", "225"),
        )
        font = active.find("./Text/Font")
        self.assertIsNotNone(font)
        assert font is not None
        self.assertEqual(font.get("size"), "240")
        self.assertEqual(font.findtext("Template"), "%02d")

        ambient = self.root.find(".//PartText[@name='hour_decimal_backdrop_ambient']")
        self.assertIsNotNone(ambient)
        assert ambient is not None
        self.assertIsNotNone(ambient.find("./Text/Font/Outline"))
        self.assertEqual(ambient.findtext("./Text/Font/Outline/Template"), "%02d")
        full_backdrop_templates = {
            template.text
            for part in self.root.iter("PartText")
            if part.get("name", "").startswith(
                ("hour_decimal_backdrop_", "minute_decimal_backdrop_")
            )
            for template in part.findall(".//Template")
        }
        self.assertEqual(full_backdrop_templates, {"%02d"})

        compact = self.root.find(
            ".//PartText[@name='compact_decimal_backdrop_active']"
        )
        self.assertIsNotNone(compact)
        assert compact is not None
        self.assertEqual(
            tuple(
                compact.get(attribute)
                for attribute in ("x", "y", "width", "height")
            ),
            (
                str(GENERATOR.COMPACT_BACKDROP_X),
                str(GENERATOR.COMPACT_BACKDROP_Y),
                str(GENERATOR.COMPACT_BACKDROP_WIDTH),
                str(GENERATOR.COMPACT_BACKDROP_HEIGHT),
            ),
        )
        compact_template = compact.find(".//Template")
        self.assertIsNotNone(compact_template)
        assert compact_template is not None
        self.assertEqual(compact_template.text, "%02d:%02d")
        self.assertEqual(
            [
                parameter.get("expression")
                for parameter in compact_template.findall("Parameter")
            ][1],
            "[MINUTE]",
        )

        style = next(
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_active_backdrops_style")
        )
        full = style.find("Group")
        self.assertIsNotNone(full)
        assert full is not None
        self.assertEqual(
            tuple(full.get(attribute) for attribute in ("pivotX", "pivotY")),
            ("0.5", "0.5"),
        )
        transforms = {
            transform.get("target"): transform.get("value")
            for transform in style.findall("Transform")
        }
        self.assertEqual(
            transforms["alpha"],
            GENERATOR.configuration_value_expression(
                GENERATOR.BACKDROP_OPACITY_ID,
                GENERATOR.BACKDROP_OPACITY_VALUES,
                GENERATOR.DEFAULT_BACKDROP_OPACITY_ID,
            ),
        )
        size_expression = GENERATOR.configuration_value_expression(
            GENERATOR.BACKDROP_LAYOUT_ID,
            GENERATOR.BACKDROP_LAYOUT_SCALE_VALUES,
            GENERATOR.DEFAULT_BACKDROP_LAYOUT_ID,
        )
        full_transforms = {
            transform.get("target"): transform.get("value")
            for transform in full.findall("Transform")
        }
        self.assertEqual(full_transforms["scaleX"], size_expression)
        self.assertEqual(full_transforms["scaleY"], size_expression)
        self.assertEqual(
            full_transforms["y"],
            GENERATOR.configuration_value_expression(
                GENERATOR.BACKDROP_LAYOUT_ID,
                GENERATOR.BACKDROP_LAYOUT_Y_VALUES,
                GENERATOR.DEFAULT_BACKDROP_LAYOUT_ID,
            ),
        )

    def test_active_and_ambient_decimal_backgrounds_are_independently_configurable(self) -> None:
        expected_active_visibility = (
            f"({GENERATOR.configuration_matches_expression(GENERATOR.BACKDROP_VISIBILITY_ID, GENERATOR.BACKDROP_ACTIVE_OPTION_IDS)}) "
            "? 255 : 0"
        )
        expected_ambient_visibility = (
            f"({GENERATOR.configuration_matches_expression(GENERATOR.BACKDROP_VISIBILITY_ID, GENERATOR.BACKDROP_AMBIENT_OPTION_IDS)}) "
            "? 255 : 0"
        )
        active_visibility = [
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_active_backdrops_visibility")
        ]
        ambient_visibility = [
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_ambient_backdrops_color_visibility")
        ]
        self.assertTrue(active_visibility)
        self.assertEqual(len(active_visibility), len(ambient_visibility))
        self.assertTrue(
            all(
                group.find("Transform[@target='alpha']").get("value")
                == expected_active_visibility
                for group in active_visibility
            )
        )
        self.assertTrue(
            all(
                group.find("Transform[@target='alpha']").get("value")
                == expected_ambient_visibility
                for group in ambient_visibility
            )
        )

        active_group = next(
            (
                group
                for group in self.root.iter("Group")
                if group.get("name", "").endswith("without_seconds_active_backdrops")
            ),
            None,
        )
        ambient_group = next(
            (
                group
                for group in self.root.iter("Group")
                if group.get("name", "").endswith("without_seconds_ambient_backdrops_color")
            ),
            None,
        )
        self.assertIsNotNone(active_group)
        self.assertIsNotNone(ambient_group)
        assert active_group is not None and ambient_group is not None
        self.assertIsNotNone(
            active_group.find(".//Variant[@mode='AMBIENT'][@target='alpha'][@value='0']")
        )
        self.assertEqual(ambient_group.get("alpha"), "0")
        self.assertIsNotNone(
            ambient_group.find(
                f"Variant[@mode='AMBIENT'][@target='alpha'][@value='{GENERATOR.ambient_brightness_expression()}']"
            )
        )

    def test_output_is_deterministic(self) -> None:
        self.assertEqual(self.xml, GENERATOR.render_watchface())

    def test_screenshot_output_uses_fixed_heart_rate(self) -> None:
        root = ET.fromstring(
            GENERATOR.render_watchface(heart_rate=GENERATOR.SCREENSHOT_HEART_RATE)
        )
        expressions = [
            expression.text
            for expression in root.findall(".//Expression")
            if expression.get("name", "").startswith("heart_rate_")
            and expression.get("name", "").endswith("_available")
        ]
        parameters = [
            parameter.get("expression")
            for parameter in root.findall(".//Parameter")
            if parameter.get("expression") == str(GENERATOR.SCREENSHOT_HEART_RATE)
        ]
        self.assertTrue(expressions)
        self.assertTrue(
            all(
                expression == f"{GENERATOR.SCREENSHOT_HEART_RATE} > 0"
                for expression in expressions
            )
        )
        self.assertTrue(parameters)
        self.assertNotIn("[HEART_RATE]", ET.tostring(root, encoding="unicode"))

    def test_check_mode_detects_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "watchface.xml"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(GENERATOR.main(["--output", str(output)]), 0)
                self.assertEqual(GENERATOR.main(["--check", "--output", str(output)]), 0)
                output.write_text("stale\n", encoding="utf-8")
                self.assertEqual(GENERATOR.main(["--check", "--output", str(output)]), 1)

    def test_cli_rejects_unknown_arguments(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--unknown"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_cli_help_flags_write_to_stdout(self) -> None:
        for help_flag in ("-h", "--help"):
            with self.subTest(help_flag=help_flag):
                result = subprocess.run(
                    [sys.executable, str(GENERATOR_PATH), help_flag],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn("usage:", result.stdout)
                self.assertEqual(result.stderr, "")

    def test_cli_accepts_short_and_equals_option_forms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            short_output = Path(temporary_directory) / "short.xml"
            long_output = Path(temporary_directory) / "long.xml"
            short_result = subprocess.run(
                [sys.executable, str(GENERATOR_PATH), "-o", str(short_output)],
                check=False,
                capture_output=True,
                text=True,
            )
            long_result = subprocess.run(
                [sys.executable, str(GENERATOR_PATH), f"--output={long_output}"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(short_result.returncode, 0)
            self.assertEqual(long_result.returncode, 0)
            self.assertEqual(short_output.read_text(encoding="utf-8"), self.xml)
            self.assertEqual(long_output.read_text(encoding="utf-8"), self.xml)

    def test_cli_accepts_fixed_heart_rate_option_forms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            short_output = Path(temporary_directory) / "short.xml"
            long_output = Path(temporary_directory) / "long.xml"
            short_result = subprocess.run(
                [sys.executable, str(GENERATOR_PATH), "-o", str(short_output), "-r72"],
                check=False,
                capture_output=True,
                text=True,
            )
            long_result = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR_PATH),
                    f"--output={long_output}",
                    "--heart-rate=72",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(short_result.returncode, 0)
            self.assertEqual(long_result.returncode, 0)
            self.assertEqual(
                short_output.read_text(encoding="utf-8"),
                GENERATOR.render_watchface(heart_rate=72),
            )
            self.assertEqual(
                long_output.read_text(encoding="utf-8"),
                GENERATOR.render_watchface(heart_rate=72),
            )

    def test_cli_requires_output_for_fixed_heart_rate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--heart-rate=72"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--heart-rate requires --output", result.stderr)

    def test_cli_reports_stale_output_on_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "watchface.xml"
            output.write_text("stale\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(GENERATOR_PATH), "-c", "-o", str(output), "--"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("differs", result.stderr)

    def test_cli_rejects_missing_output_value(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--output"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("expected one argument", result.stderr)


if __name__ == "__main__":
    unittest.main()
