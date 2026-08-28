from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PROJECT_ROOT / "tools/generate_watchface.py"
MODULE_SPEC = importlib.util.spec_from_file_location("generate_watchface", GENERATOR_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
GENERATOR = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = GENERATOR
MODULE_SPEC.loader.exec_module(GENERATOR)


class WatchFaceGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.xml = GENERATOR.render_watchface()
        self.root = ET.fromstring(self.xml)

    def user_configuration(self, configuration_id: str) -> ET.Element:
        configurations = self.root.find("UserConfigurations")
        self.assertIsNotNone(configurations)
        assert configurations is not None
        for configuration in configurations:
            if configuration.get("id") == configuration_id:
                return configuration
        self.fail(f"Missing user configuration: {configuration_id}")

    def test_terminal_green_is_the_default_theme(self) -> None:
        themes = self.user_configuration(GENERATOR.THEME_ID)
        self.assertEqual(themes.get("defaultValue"), "terminal")
        terminal = themes.find("ColorOption[@id='terminal']")
        self.assertIsNotNone(terminal)
        assert terminal is not None
        self.assertEqual(terminal.get("colors").split()[0], "#39FF88")

    def test_true_binary_rows_cover_12_and_24_hour_time(self) -> None:
        self.assertEqual(GENERATOR.HOUR_12_WEIGHTS, (8, 4, 2, 1))
        self.assertEqual(GENERATOR.HOUR_24_WEIGHTS, (16, 8, 4, 2, 1))
        self.assertEqual(GENERATOR.SIX_BIT_WEIGHTS, (32, 16, 8, 4, 2, 1))
        self.assertIn("[HOUR_1_12]", self.xml)
        self.assertIn("[HOUR_0_23]", self.xml)
        self.assertIn("[IS_24_HOUR_MODE]", self.xml)
        self.assertIn("floor(([HOUR_0_23]) / 16) % 2 == 1 ? 255 : 0", self.xml)
        self.assertIn("floor(([MINUTE]) / 32) % 2 == 1 ? 255 : 0", self.xml)

    def test_complication_count_options_enable_exact_layouts(self) -> None:
        configuration = self.user_configuration(GENERATOR.COMPLICATION_COUNT_ID)
        options = {
            option.get("id"): tuple(int(value) for value in option.get("complicationSlotIds", "").split())
            for option in configuration.findall("ListOption")
        }
        self.assertEqual(options, GENERATOR.COMPLICATION_LAYOUTS)

        declared = {
            int(slot.get("slotId", "-1"))
            for slot in self.root.findall("./Scene/ComplicationSlot")
        }
        enabled = {slot_id for layout in options.values() for slot_id in layout}
        self.assertEqual(enabled, declared)

    def test_every_complication_supports_the_promised_types(self) -> None:
        expected = {"SHORT_TEXT", "MONOCHROMATIC_IMAGE", "SMALL_IMAGE", "RANGED_VALUE", "EMPTY"}
        for slot in self.root.findall("./Scene/ComplicationSlot"):
            self.assertEqual(set(slot.get("supportedTypes", "").split()), expected)
            rendered = {complication.get("type") for complication in slot.findall("Complication")}
            self.assertEqual(rendered, expected)

    def test_face_has_no_custom_launch_actions(self) -> None:
        self.assertEqual(self.root.findall(".//Launch"), [])

    def test_ambient_mode_suppresses_high_activity_elements(self) -> None:
        ambient_variants = self.root.findall(".//Variant[@mode='AMBIENT'][@target='alpha'][@value='0']")
        self.assertGreater(len(ambient_variants), 0)
        for slot in self.root.findall("./Scene/ComplicationSlot"):
            self.assertIsNotNone(slot.find("Variant[@mode='AMBIENT'][@target='alpha'][@value='0']"))

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
