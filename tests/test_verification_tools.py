from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools import capture_watch as CAPTURE
from tools import check_layout as LAYOUT


RUNTIME = """
Resource only package name dev.j256.binarywatchface
privIsVisible=true
currentUserStyleRepository.userStyle=UserStyle[displaySize -> huge, complicationCount -> 4]
isAmbient=true
drawMode=AMBIENT
ComplicationSlot 11:
    enabled=true
    dataSource=ComponentInfo{example.provider/.Steps}
ComplicationSlot 13:
    enabled=false
## no_name / dev.j256.binarywatchface 0.4.0 (4)
"""
WALLPAPER = b"System wallpaper state:\n mWallpaperComponent=ComponentInfo{example.runtime/.Face}\nLock wallpaper state:\nFallback wallpaper state:\n mWallpaperComponent=ComponentInfo{example.default/.Fallback}\n"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBuoAAAAASUVORK5CYII=")


def invoke(main, arguments):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            status = main(arguments)
        except SystemExit as error:
            status = error.code
    return status, stdout.getvalue(), stderr.getvalue()


class LayoutCheckTest(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(LAYOUT.DEFAULT_XML).getroot()

    def test_generated_layout_passes_and_reports_minimum_clearances(self):
        status, stdout, stderr = invoke(LAYOUT.main, [])
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("PASS system-pill:", stdout)
        self.assertIn("minimum 4", stdout)

    def test_taller_pill_guard_catches_center_shift_missed_by_old_rectangle(self):
        center = self.root.find("./Scene/ComplicationSlot[@slotId='2']")
        center.set("y", str(float(center.get("y")) + 1))
        checks = LAYOUT.layout_clearances(self.root)
        self.assertTrue(all(check.passed for check in checks if check.category == "system-rectangle"))
        failures = [check for check in checks if not check.passed]
        self.assertEqual([(check.category, check.elements) for check in failures], [("system-pill", "lower_center")])

    def test_native_readout_cannot_return_to_system_overlay(self):
        for text in self.root.findall(".//PartText"):
            if text.get("name", "").startswith(("battery_", "heart_rate_")):
                text.set("y", "382")
        failures = [check for check in LAYOUT.layout_clearances(self.root) if not check.passed]
        self.assertTrue(any(check.category == "system-pill" and check.elements == "battery" for check in failures))

    def test_complications_cannot_collide(self):
        center = self.root.find("./Scene/ComplicationSlot[@slotId='2']")
        center.set("x", "73")
        self.assertTrue(any(check.category == "complication-pair" and not check.passed for check in LAYOUT.layout_clearances(self.root)))

    def test_invalid_geometry_fails_closed(self):
        for change in ("missing-slot", "non-circle", "non-finite"):
            root = copy.deepcopy(self.root)
            slot = root.find("./Scene/ComplicationSlot[BoundingOval]")
            if change == "missing-slot":
                root.find("Scene").remove(slot)
            elif change == "non-circle":
                slot.find("BoundingOval").set("height", "10")
            else:
                slot.set("x", "nan")
            with self.subTest(change=change), self.assertRaises(ValueError):
                LAYOUT.layout_clearances(root)

    def test_cli_reports_failed_geometry_and_supports_option_forms(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "face.xml"
            self.root.find("./Scene/ComplicationSlot[@slotId='2']").set("y", "291")
            ET.ElementTree(self.root).write(path)
            for arguments in (["-j", str(path)], [str(path), "--json"], ["--json", "--", str(path)]):
                status, stdout, stderr = invoke(LAYOUT.main, arguments)
                self.assertEqual(status, 1)
                self.assertFalse(json.loads(stdout)["passed"])
                self.assertEqual(stderr, "")
        self.assertEqual(invoke(LAYOUT.main, ["/missing/watchface.xml"])[0], 2)

    def test_history_background_must_remain_below_native_and_provider_content(self):
        scene = self.root.find("Scene")
        history = scene.find("ComplicationSlot[@name='heart_history']")
        scene.remove(history)
        scene.append(history)
        with self.assertRaisesRegex(ValueError, "render below"):
            LAYOUT.layout_clearances(self.root)

    def test_history_background_cannot_extend_into_system_activity_area(self):
        history = self.root.find("./Scene/ComplicationSlot[@name='heart_history']")
        history.set("y", "110")
        failures = [check for check in LAYOUT.layout_clearances(self.root) if not check.passed]
        self.assertTrue(any(check.category == "system-pill" and check.elements == "heart_history" for check in failures))


class WatchCaptureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "capture"
        self.args = argparse.Namespace(serial="watch-test", package=CAPTURE.PACKAGE, mode="ambient", expected_version="0.4.0", output=self.output)

    def run_capture(self, runtime_after=RUNTIME, png=PNG, baseline=None):
        outputs = [WALLPAPER, RUNTIME.encode(), png, WALLPAPER, runtime_after.encode()]
        responses = [subprocess.CompletedProcess([], 0, stdout=value) for value in outputs]
        with patch.object(CAPTURE.subprocess, "run", side_effect=responses) as run:
            result = CAPTURE.capture(self.args, "/fake/adb", baseline)
        return result, [call.args[0] for call in run.call_args_list]

    def test_capture_preserves_provenance_and_only_uses_read_commands(self):
        result, commands = self.run_capture()
        self.assertEqual(result["version"], "0.4.0")
        self.assertEqual(result["mode"], "ambient")
        self.assertEqual(result["unverified_provider_slots"], [])
        self.assertEqual(json.loads((self.output / "snapshot.json").read_text()), result)
        self.assertEqual((self.output / "watch.png").read_bytes(), PNG)
        self.assertTrue(all(command[:3] == ["/fake/adb", "-s", "watch-test"] for command in commands))
        allowed = (["shell", "dumpsys", "wallpaper"], ["shell", "dumpsys", "activity", "service", "example.runtime/.Face"], ["exec-out", "screencap", "-p"])
        self.assertTrue(all(command[3:] in allowed for command in commands))

    def test_fallback_wallpaper_cannot_supply_capture_identity(self):
        self.assertEqual(CAPTURE.wallpaper_component(WALLPAPER.decode()), "example.runtime/.Face")
        with self.assertRaises(CAPTURE.PreconditionError):
            CAPTURE.wallpaper_component("Fallback wallpaper state:\n mWallpaperComponent=ComponentInfo{example.default/.Fallback}")

    def test_wrong_identity_mode_or_visibility_is_rejected(self):
        cases = (
            RUNTIME.replace("0.4.0 (4)", "0.2.0 (2)"),
            RUNTIME.replace(CAPTURE.PACKAGE, "example.other"),
            RUNTIME.replace("privIsVisible=true", "privIsVisible=false"),
            RUNTIME.replace("isAmbient=true", "isAmbient=false"),
            RUNTIME.replace("drawMode=AMBIENT", "drawMode=INTERACTIVE"),
        )
        for runtime in cases:
            with self.subTest(runtime=runtime), self.assertRaises(CAPTURE.PreconditionError):
                CAPTURE.parse_runtime(runtime, CAPTURE.PACKAGE, "ambient", "0.4.0")

    def test_transition_during_capture_does_not_save_mislabeled_evidence(self):
        changed = RUNTIME.replace("displaySize -> huge", "displaySize -> small")
        with self.assertRaisesRegex(RuntimeError, "changed during capture"):
            self.run_capture(runtime_after=changed)
        self.assertFalse(self.output.exists())

    def test_invalid_image_does_not_save_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "invalid PNG"):
            self.run_capture(png=b"device disconnected")
        self.assertFalse(self.output.exists())

    def test_comparison_distinguishes_update_from_lost_preferences(self):
        before = CAPTURE.parse_runtime(RUNTIME, CAPTURE.PACKAGE, "ambient", "0.4.0")
        after = copy.deepcopy(before)
        after.update(version="0.5.0", version_code=5, mode="active")
        self.assertEqual(CAPTURE.selection_changes(before, after), [])
        after["style"]["displaySize"] = "small"
        after["providers"]["11"]["data_source"] = "example.provider/.Weather"
        self.assertEqual(CAPTURE.selection_changes(before, after), ["style.displaySize", "providers.11"])

    def test_unknown_enabled_provider_is_not_treated_as_verified(self):
        unknown = RUNTIME.replace("dataSource=ComponentInfo{example.provider/.Steps}", "data=NoDataComplicationData()")
        snapshot = CAPTURE.parse_runtime(unknown, CAPTURE.PACKAGE, "ambient", "0.4.0")
        self.assertEqual(CAPTURE.unknown_providers(snapshot), ["11"])
        with self.assertRaises(CAPTURE.PreconditionError):
            CAPTURE.parse_runtime(RUNTIME.replace("ComplicationSlot 13:", "dataSource=ComponentInfo{example.provider/.Other}\nComplicationSlot 13:"), CAPTURE.PACKAGE, "ambient", "0.4.0")

    def test_cli_validation_and_dependency_errors(self):
        common = ["-swatch-test", "-mambient", "-e0.4.0", "-o", str(self.output)]
        with patch.object(CAPTURE, "find_adb", side_effect=FileNotFoundError("missing adb")):
            status, stdout, stderr = invoke(CAPTURE.main, common)
        self.assertEqual((status, stdout), (3, ""))
        self.assertIn("missing adb", stderr)
        self.output.mkdir()
        self.assertEqual(invoke(CAPTURE.main, common)[0], 2)
        for arguments in (["--serial="], ["--unknown"], ["-s"], []):
            self.assertEqual(invoke(CAPTURE.main, arguments)[0], 2)

    def test_long_option_values_and_comparison_failures(self):
        baseline, _ = self.run_capture()
        baseline_path = self.output / "snapshot.json"
        next_output = Path(self.temporary.name) / "next"
        common = ["--serial=watch-test", "--mode=ambient", "--expected-version=0.4.0", "--output=" + str(next_output), "--compare-with=" + str(baseline_path), "--"]
        with patch.object(CAPTURE, "find_adb", return_value="/fake/adb"), patch.object(CAPTURE, "capture", return_value={**baseline, "selection_changes": ["style.displaySize"]}):
            status, stdout, stderr = invoke(CAPTURE.main, common)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(stdout)["selection_changes"], ["style.displaySize"])
        self.assertIn("style.displaySize", stderr)
        with patch.object(CAPTURE, "find_adb", return_value="/fake/adb"), patch.object(CAPTURE, "capture", return_value={**baseline, "selection_changes": [], "unverified_provider_slots": ["11"]}):
            self.assertEqual(invoke(CAPTURE.main, common)[0], 1)

    def test_bad_comparison_schema_fails_before_using_adb(self):
        path = Path(self.temporary.name) / "bad.json"
        path.write_text('{"schema_version": 999}')
        with self.assertRaises(CAPTURE.PreconditionError):
            CAPTURE.read_baseline(path)


class HelpTest(unittest.TestCase):
    def test_help_needs_no_device_dependencies(self):
        for main in (LAYOUT.main, CAPTURE.main):
            for flag in ("-h", "--help"):
                with self.subTest(main=main, flag=flag), patch.object(CAPTURE, "find_adb", side_effect=AssertionError("help must not resolve adb")):
                    status, stdout, stderr = invoke(main, [flag])
                self.assertEqual((status, stderr), (0, ""))
                self.assertIn("Exit status:", " ".join(stdout.split()))


if __name__ == "__main__":
    unittest.main()
