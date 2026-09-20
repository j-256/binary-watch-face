from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from tools import release as RELEASE


class ReleaseGuardsTest(unittest.TestCase):
    def manifest(self, **attributes):
        root = ET.Element("manifest", {"package": RELEASE.PACKAGE, RELEASE.ANDROID + "versionName": "0.4.0", RELEASE.ANDROID + "versionCode": "4"})
        ET.SubElement(root, "application", {RELEASE.ANDROID + "hasCode": "false", **attributes})
        return root

    def test_manifest_rejects_debug_code_and_wrong_identity(self):
        RELEASE.verify_manifest(self.manifest(), "0.4.0", 4)
        for attribute, value in (("debuggable", "true"), ("hasCode", "true")):
            with self.subTest(attribute=attribute), self.assertRaises(ValueError):
                RELEASE.verify_manifest(self.manifest(**{RELEASE.ANDROID + attribute: value}), "0.4.0", 4)
        for attribute, value in (("package", "other.app"), (RELEASE.ANDROID + "versionCode", "5"), (RELEASE.ANDROID + "versionName", "0.5.0")):
            root = self.manifest()
            root.set(attribute, value)
            with self.subTest(attribute=attribute), self.assertRaises(ValueError):
                RELEASE.verify_manifest(root, "0.4.0", 4)

    def test_archive_rejects_different_wff_and_executable_code(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(RELEASE, "run", return_value=b"<WatchFace/>"):
            for contents, dex in ((b"<WatchFace/>", False), (b"<Wrong/>", False), (b"<WatchFace/>", True)):
                path = Path(directory) / "bundle.aab"
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("base/res/raw/watchface.xml", contents)
                    if dex:
                        archive.writestr("base/dex/classes.dex", b"code")
                if contents == b"<WatchFace/>" and not dex:
                    RELEASE.verify_archive(path, "v0.4.0", "base/")
                else:
                    with self.assertRaises(ValueError):
                        RELEASE.verify_archive(path, "v0.4.0", "base/")

    def test_remote_tag_must_match_annotation_not_only_commit(self):
        with patch.object(RELEASE, "run", side_effect=[b"local-tag\n", b"other-tag\trefs/tags/v0.4.0\n"]):
            with self.assertRaisesRegex(ValueError, "exact annotated"):
                RELEASE.verify_remote_tag("v0.4.0")

    def test_tag_refuses_dirty_worktree_before_mutation(self):
        args = argparse.Namespace(version="0.4.0", dry_run=False)
        with patch.object(RELEASE, "run", return_value=b" M README.md\n") as run:
            with self.assertRaisesRegex(ValueError, "Commit all changes"):
                RELEASE.tag_release(args)
            self.assertEqual(run.call_count, 1)

    def test_missing_or_wrong_github_assets_are_rejected(self):
        expected = {"binary-watch-face.apk": "sha256:expected"}
        for assets in ([], [{"name": "binary-watch-face.apk", "digest": "sha256:wrong"}]):
            with self.assertRaises(ValueError):
                RELEASE.verify_assets({"isDraft": True, "isPrerelease": True, "assets": assets}, expected, True)

    def test_incomplete_github_draft_is_never_published(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "play.apk"
            notes = Path(directory) / "notes.md"
            apk.write_bytes(b"verified APK fixture")
            notes.write_text("Release notes")
            args = argparse.Namespace(version="0.4.0", apk=apk, notes=notes, dry_run=False)
            calls = []

            def run(arguments):
                calls.append(arguments)
                if arguments[1:3] == ["release", "list"]:
                    return b"[]"
                if arguments[1:3] == ["release", "view"]:
                    return json.dumps({"isDraft": True, "isPrerelease": True, "assets": []}).encode()
                return b""

            with patch.object(RELEASE, "dependency"), patch.object(RELEASE, "release_tag", return_value=("v0.4.0", 4)), patch.object(RELEASE, "verify_apk"), patch.object(RELEASE, "verify_remote_tag"), patch.object(RELEASE, "run", side_effect=run):
                with self.assertRaisesRegex(ValueError, "checksums"):
                    RELEASE.publish_github(args)
            self.assertTrue(any(call[1:3] == ["release", "create"] and "--draft" in call for call in calls))
            self.assertFalse(any(call[1:3] == ["release", "edit"] for call in calls))

    def test_cli_help_option_forms_and_invalid_inputs(self):
        parser = RELEASE.parser()
        for arguments in (["tag", "-n", "0.4.0"], ["tag", "--dry-run", "--", "0.4.0"], ["tag", "0.4.0", "-n"]):
            parsed = parser.parse_args(arguments)
            self.assertEqual(parsed.version, "0.4.0")
            self.assertTrue(parsed.dry_run)
        certificate = "ab" * 32
        for arguments in (
            ["prepare-play", "0.4.0", "-nc" + certificate, "-bbundle.aab", "-jtool.jar", "-oarchive"],
            ["prepare-play", "--bundle=bundle.aab", "0.4.0", "--bundletool=tool.jar", "--output=archive", "--certificate-sha256=" + certificate, "--dry-run"],
            ["prepare-play", "-n", "-b", "bundle.aab", "-j", "tool.jar", "-o", "archive", "-c", certificate, "--", "0.4.0"],
        ):
            parsed = parser.parse_args(arguments)
            self.assertEqual(parsed.certificate_sha256, certificate)
            self.assertEqual(parsed.bundle.name, "bundle.aab")
            self.assertTrue(parsed.dry_run)
        for arguments in (["-h"], ["--help"], ["tag", "-h"], ["prepare-play", "--help"], ["github", "-h"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
                parser.parse_args(arguments)
            self.assertEqual(result.exception.code, 0)
            self.assertIn("usage:", output.getvalue())
        for arguments in (["tag", ""], ["tag"], ["tag", "bad"], ["tag", "0.4.0", "--unknown"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                parser.parse_args(arguments)
            self.assertEqual(result.exception.code, 2)
        with self.assertRaises(argparse.ArgumentTypeError):
            RELEASE.fingerprint("debug")
        with self.assertRaises(argparse.ArgumentTypeError):
            RELEASE.path_argument("")

    def test_dependency_and_precondition_exit_statuses(self):
        for error, status in ((FileNotFoundError("git"), 3), (ValueError("dirty worktree"), 2), (RuntimeError("remote unavailable"), 1)):
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(RELEASE, "dependency", side_effect=error), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(RELEASE.main(["tag", "0.4.0", "-n"]), status)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn(str(error), stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
