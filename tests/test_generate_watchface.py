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
MODULE_SPEC = importlib.util.spec_from_file_location("generate_watchface", GENERATOR_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
GENERATOR = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = GENERATOR
MODULE_SPEC.loader.exec_module(GENERATOR)


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

    def test_bit_weights_can_be_limited_to_active_mode(self) -> None:
        setting = self.user_configuration(GENERATOR.SHOW_WEIGHTS_ID)
        self.assertEqual(
            [option.get("id") for option in setting.findall("ListOption")],
            [
                GENERATOR.WEIGHTS_SHOWN_ID,
                GENERATOR.WEIGHTS_ACTIVE_ONLY_ID,
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
                f"CONFIGURATION.{GENERATOR.SHOW_WEIGHTS_ID}" in (expression.text or "")
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
            ambient = weights.find(
                f"ListConfiguration[@id='{GENERATOR.SHOW_WEIGHTS_ID}']"
            )
            self.assertIsNotNone(ambient)
            assert ambient is not None
            self.assertEqual(
                [option.get("id") for option in ambient.findall("ListOption")],
                [GENERATOR.WEIGHTS_SHOWN_ID],
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
        self.assertLessEqual(complication_top - no_seconds_bottom, 42)
        self.assertLessEqual(complication_top - seconds_bottom, 34)

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
            ["decimal", "hex", "binary", "off"],
        )

        scene_configuration = self.root.find(
            f"./Scene/ListConfiguration[@id='{GENERATOR.BATTERY_DISPLAY_ID}']"
        )
        self.assertIsNotNone(scene_configuration)
        assert scene_configuration is not None
        hex_template = scene_configuration.find("./ListOption[@id='hex']/.//Template")
        self.assertIsNotNone(hex_template)
        assert hex_template is not None
        self.assertEqual(hex_template.text, "0x%x")
        binary_templates = {
            template.text
            for template in scene_configuration.findall("./ListOption[@id='binary']/.//Template")
        }
        self.assertIn("0b%d", binary_templates)
        self.assertIn("0b%d%d%d%d%d%d%d", binary_templates)
        battery_text = scene_configuration.findall(".//PartText")
        self.assertTrue(battery_text)
        self.assertTrue(
            all(text.get("y") == str(GENERATOR.BATTERY_READOUT_Y) for text in battery_text)
        )
        lower_bottom = max(
            slot.y + slot.size for slot in GENERATOR.COMPLICATION_SLOTS[:2]
        )
        self.assertGreaterEqual(GENERATOR.BATTERY_READOUT_Y - lower_bottom, 7)

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

    def test_ambient_information_presets_control_date_weekday_and_watch_battery(self) -> None:
        ambient_info = self.user_configuration(GENERATOR.AMBIENT_INFO_ID)
        self.assertEqual(
            [option.get("id") for option in ambient_info.findall("ListOption")],
            [option_id for option_id, _ in GENERATOR.AMBIENT_INFO_OPTIONS],
        )

        date = self.root.find(
            f"./Scene/ListConfiguration[@id='{GENERATOR.DATE_FORMAT_ID}']"
        )
        battery = self.root.find(
            f"./Scene/ListConfiguration[@id='{GENERATOR.BATTERY_DISPLAY_ID}']"
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

    def test_complication_count_options_enable_exact_layouts(self) -> None:
        configuration = self.user_configuration(GENERATOR.COMPLICATION_COUNT_ID)
        options = {
            option.get("id"): tuple(int(value) for value in option.get("complicationSlotIds", "").split())
            for option in configuration.findall("ListOption")
        }
        self.assertEqual(options, GENERATOR.COMPLICATION_LAYOUTS)
        self.assertEqual(options, {"2": (0, 1), "3": (0, 1, 2), "4": (0, 1, 3, 4)})

        declared = {
            int(slot.get("slotId", "-1"))
            for slot in self.root.findall("./Scene/ComplicationSlot")
        }
        enabled = {slot_id for layout in options.values() for slot_id in layout}
        self.assertEqual(enabled, declared)

    def test_complication_layout_preserves_large_lower_pair(self) -> None:
        slots = {
            int(slot.get("slotId", "-1")): slot
            for slot in self.root.findall("./Scene/ComplicationSlot")
        }
        self.assertEqual(
            tuple(slots[0].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("lower_left", "87", "277", "106", "106"),
        )
        self.assertEqual(
            tuple(slots[1].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("lower_right", "257", "277", "106", "106"),
        )
        self.assertEqual(
            tuple(slots[2].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("lower_center", "190", "264", "70", "70"),
        )
        self.assertEqual(
            tuple(slots[3].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("middle_left", "16", "191", "68", "68"),
        )
        self.assertEqual(
            tuple(slots[4].get(attribute) for attribute in ("name", "x", "y", "width", "height")),
            ("middle_right", "366", "191", "68", "68"),
        )

    def test_side_complications_leave_outer_ticks_visible(self) -> None:
        tick_configuration = self.root.find(
            f"./Scene/ListConfiguration[@id='{GENERATOR.TICK_STYLE_ID}']"
        )
        self.assertIsNotNone(tick_configuration)
        assert tick_configuration is not None
        tick_outer_insets = [
            float(marker.get("y", "0"))
            for marker in tick_configuration.findall(".//RoundRectangle")
        ]
        self.assertTrue(tick_outer_insets)

        side_left, side_right = GENERATOR.COMPLICATION_SLOTS[3:5]
        outer_margins = (
            side_left.x,
            GENERATOR.WATCH_SIZE - side_right.x - side_right.size,
        )
        self.assertTrue(
            all(margin > max(tick_outer_insets) for margin in outer_margins)
        )

    def test_complication_slots_clear_the_largest_clock_and_each_other(self) -> None:
        largest = max(GENERATOR.SIZE_CHOICES, key=lambda size: size.scale)
        base = next(
            size for size in GENERATOR.SIZE_CHOICES if size.option_id == GENERATOR.BASE_SIZE_ID
        )
        dot_size, positions = GENERATOR.bit_geometry(len(GENERATOR.HOUR_24_WEIGHTS), base)
        weight_width = dot_size + 14
        left_weight = positions[0] - 7
        right_weight = positions[-1] - 7 + weight_width
        clock_center = GENERATOR.WATCH_SIZE / 2
        scaled_left = clock_center + largest.scale * (left_weight - clock_center)
        scaled_right = clock_center + largest.scale * (right_weight - clock_center)
        side_left, side_right = GENERATOR.COMPLICATION_SLOTS[3:5]
        self.assertLess(side_left.x + side_left.size, scaled_left)
        self.assertGreater(side_right.x, scaled_right)
        for side_slot in (side_left, side_right):
            slot_center_x = side_slot.x + side_slot.size / 2
            slot_center_y = side_slot.y + side_slot.size / 2
            self.assertEqual(slot_center_y, clock_center)
            distance_from_dial_center = math.hypot(
                slot_center_x - clock_center,
                slot_center_y - clock_center,
            )
            self.assertLessEqual(
                distance_from_dial_center + side_slot.size / 2,
                clock_center,
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
        backdrop_templates = {
            template.text
            for part in self.root.iter("PartText")
            if "_decimal_backdrop_" in part.get("name", "")
            for template in part.findall(".//Template")
        }
        self.assertEqual(backdrop_templates, {"%02d"})

        style = next(
            group
            for group in self.root.iter("Group")
            if group.get("name", "").endswith("_active_backdrops_style")
        )
        self.assertEqual(
            tuple(style.get(attribute) for attribute in ("pivotX", "pivotY")),
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
        self.assertEqual(transforms["scaleX"], size_expression)
        self.assertEqual(transforms["scaleY"], size_expression)
        self.assertEqual(
            transforms["y"],
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
