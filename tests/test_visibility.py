from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_visibility as check
from tools import generate_watchface as face
from tools import visibility as v


def invoke(main, arguments):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            status = main(arguments)
        except SystemExit as error:
            status = error.code
    return status, stdout.getvalue(), stderr.getvalue()


class VisibilityMathTest(unittest.TestCase):
    def test_standard_srgb_reference_values_and_gamma_boundary(self):
        self.assertEqual(v.luminance(v.rgb("#000000")), 0)
        self.assertEqual(v.luminance(v.rgb("#FFFFFF")), 1)
        self.assertEqual(v.contrast(v.rgb("#000000"), v.rgb("#FFFFFF")), 21)
        self.assertAlmostEqual(v.luminance(v.rgb("#FF0000")), 0.2126)
        self.assertAlmostEqual(v.luminance(v.rgb("#808080")), 0.2158605001)
        self.assertAlmostEqual(v.luminance((10, 10, 10)), 10 / 255 / 12.92)
        self.assertAlmostEqual(v.luminance((11, 11, 11)), ((11 / 255 + 0.055) / 1.055) ** 2.4)

    def test_half_opacity_is_not_half_contrast_weight(self):
        white, black = v.rgb("#FFFFFF"), v.rgb("#000000")
        self.assertEqual(v.composite(white, black, 0.5), (127.5, 127.5, 127.5))
        weight = (v.contrast(v.composite(white, black, 0.5), black) - 1) / 20
        self.assertAlmostEqual(weight, 0.21404114)
        self.assertGreater(v.solve_alpha(0.5, white, black), 180)

    def test_solver_accounts_for_both_alpha_layers_and_quantization(self):
        model = v.load_model()
        for preset in v.GRAPH_PRESETS:
            target = v.target_contrast(model.presets[preset]["trace_visibility"], *model.reference)
            actual = v.contrast_at(*model.reference, model.role_alpha("trace"), model.face_alpha(preset))
            self.assertAlmostEqual(actual, target, delta=0.006)
            if preset != "clear":
                wrong = v.solve_alpha(model.presets[preset]["trace_visibility"], *model.reference)
                self.assertLess(v.contrast_at(*model.reference, model.role_alpha("trace"), wrong), actual)
        self.assertEqual(v.solve_alpha(0, *model.reference), 0)
        self.assertEqual(v.solve_alpha(1, *model.reference), 255)
        self.assertEqual(v.solve_alpha(1, *model.reference, source_alpha=50), 255)

    def test_solver_handles_light_background_and_invalid_values(self):
        dark, light = v.rgb("#424242"), v.rgb("#F4F4F4")
        for weight in (0, 0.1, 0.5, 1):
            alpha = v.solve_alpha(weight, dark, light)
            self.assertAlmostEqual(v.contrast_at(dark, light, alpha), v.target_contrast(weight, dark, light), delta=0.08)
        for value in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                v.solve_alpha(value, dark, light)
        with self.assertRaises(ValueError):
            v.solve_alpha(0.5, dark, light, source_alpha=256)


class VisibilityContractTest(unittest.TestCase):
    def test_initial_calibration_preserves_the_released_rendering(self):
        model = v.load_model()
        self.assertEqual([model.role_alpha(role) for role in v.GRAPH_ROLES], [145, 168, 232, 245, 12, 14])
        self.assertEqual([model.face_alpha(preset) for preset in v.GRAPH_PRESETS], [82, 142, 255])
        self.assertEqual([model.ambient_alpha(preset) for preset in ("dim", "normal", "bright")], [128, 192, 255])
        self.assertEqual([model.weight_alpha(role) for role in ("uniform", "lit", "unlit")], [210, 255, 90])
        model.require_calibration()

    def test_invalid_model_data_is_rejected_before_generating(self):
        original = v.load_model().data
        for path, value in (
            (("schema_version",), 2), (("ambient",), []), (("reference", "foreground"), "green"),
            (("graph", "geometry", "trace_width"), float("nan")),
            (("graph", "geometry", "trace_width"), 0), (("bit_weights", "uniform"), True),
            (("graph", "roles", "trace", "visibility"), 1.5),
            (("graph", "presets", "faint", "trace_visibility"), 0.8),
            (("ambient", "graph_visibility"), 0.5),
        ):
            data = copy.deepcopy(original)
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "visibility.json"
                source.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    v.load_model(source)

    def test_regressions_fail_contrast_geometry_and_overlap_contracts(self):
        for name in ("contrast", "thin", "overlap"):
            data = copy.deepcopy(v.load_model().data)
            if name == "contrast":
                data["graph"]["presets"]["subtle"]["trace_visibility"] = 0.04
            elif name == "thin":
                data["graph"]["geometry"]["trace_width"] = 1
            else:
                data["graph"]["roles"]["marks"]["visibility"] = 0.8
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Visibility calibration failed"):
                v.VisibilityModel(data).require_calibration()

    def test_generated_java_is_checked_and_explicit_xml_output_is_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            java = Path(directory) / "GraphVisibility.java"
            java.write_text("stale")
            with patch.object(v, "JAVA_OUTPUT", java):
                status, stdout, stderr = invoke(face.main, ["--check"])
                self.assertEqual(status, 1)
                self.assertIn(str(java), stderr)
                xml = Path(directory) / "face.xml"
                self.assertEqual(invoke(face.main, ["--output", str(xml)])[0], 0)
                self.assertEqual(java.read_text(), "stale")
                java.write_text(face.VISIBILITY.render_java())
                self.assertEqual(invoke(face.main, ["--check"])[0], 0)

    def test_palette_report_exposes_limits_instead_of_claiming_global_compliance(self):
        result = check.report(v.load_model())
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["palettes"]), len(face.COLOR_CHOICES) * len(face.APPEARANCES))
        white_on_light = next(row for row in result["palettes"] if row["color"] == "white" and row["appearance"] == "light")
        self.assertIn("trace", white_on_light["presets"]["clear"]["foreground_below_floor"])
        self.assertIn("trace", white_on_light["presets"]["clear"]["below_reference_floor"])
        self.assertEqual(result["backdrop_opacity"]["7_5"], 19)
        self.assertEqual(result["ambient_graph_alpha"], 0)

    def test_cli_formats_exit_statuses_and_option_forms(self):
        for arguments in (["-f", "json"], ["--format=json", "--"]):
            status, stdout, stderr = invoke(check.main, arguments)
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            self.assertTrue(json.loads(stdout)["passed"])
        status, stdout, stderr = invoke(check.main, ["-h"])
        self.assertEqual((status, stderr), (0, ""))
        self.assertIn("Exit status", stdout)
        status, stdout, stderr = invoke(check.main, ["-f", "html"])
        self.assertEqual((status, stderr), (0, ""))
        self.assertNotIn("__VISIBILITY_DATA__", stdout)
        self.assertIn('type="application/json"', stdout)
        for arguments in (["--invalid"], ["--format", "csv"], ["--format"], ["-m", "/missing.json"]):
            status, stdout, stderr = invoke(check.main, arguments)
            self.assertEqual(status, 2)
            self.assertEqual(stdout, "")
            self.assertTrue(stderr)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dim.json"
            data = copy.deepcopy(v.load_model().data)
            data["graph"]["presets"]["subtle"]["trace_visibility"] = 0.04
            source.write_text(json.dumps(data))
            status, stdout, stderr = invoke(check.main, ["--model", str(source), "-f", "json"])
            self.assertEqual((status, stderr), (1, ""))
            self.assertFalse(json.loads(stdout)["passed"])
        script = Path(check.__file__)
        result = subprocess.run([sys.executable, str(script), "--format", "json"], cwd=tempfile.gettempdir(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
