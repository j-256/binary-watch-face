from types import SimpleNamespace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from tools import capture_cover as COVER


class EmulatorStartupTest(unittest.TestCase):
    def test_initializes_adb_before_the_emulator_reads_its_identity(self):
        class LaunchObserved(Exception):
            pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk"
            image = sdk / "system-images/android-37.0/android-wear-signed/arm64-v8a"
            image.mkdir(parents=True)
            (image / "package.xml").write_text("<package/>")
            xml = root / "watchface.xml"
            xml.write_bytes(b"<WatchFace/>")
            apk = root / "watchface.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("res/raw/watchface.xml", xml.read_bytes())
            identity_ready = False

            def run(arguments, **kwargs):
                nonlocal identity_ready
                if arguments[0] == str(sdk / "cmdline-tools/latest/bin/avdmanager"):
                    device = Path(arguments[arguments.index("--path") + 1])
                    device.mkdir()
                    (device / "config.ini").write_text("hw.ramSize=1536\n")
                elif arguments == [str(sdk / "platform-tools/adb"), "start-server"]:
                    identity_ready = True
                else:
                    self.fail(f"Unexpected startup command: {arguments}")

            def launch(*args, **kwargs):
                self.assertTrue(identity_ready, "Emulator read the ADB identity before initialization")
                raise LaunchObserved()

            with patch.object(COVER, "SCREENSHOT_XML", xml), \
                    patch.object(COVER.platform, "machine", return_value="arm64"), \
                    patch.object(COVER, "run", side_effect=run), \
                    patch.object(COVER.subprocess, "Popen", side_effect=launch):
                with self.assertRaises(LaunchObserved):
                    COVER.capture(sdk, apk, root / "cover.png")

    def test_boot_timeout_reports_the_adb_authorization_failure(self):
        shell = Mock(return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="adb: device unauthorized.\n"
        ))
        emulator = Mock()
        emulator.poll.return_value = None
        with patch.object(COVER.time, "monotonic", side_effect=[0, COVER.TIMEOUT + 1]):
            with self.assertRaisesRegex(RuntimeError, "device unauthorized"):
                COVER.wait_for_boot(shell, emulator)

    def test_boot_completion_does_not_require_another_poll(self):
        shell = Mock(return_value=SimpleNamespace(returncode=0, stdout="1\n", stderr=""))
        emulator = Mock()
        with patch.object(COVER.time, "sleep") as pause:
            COVER.wait_for_boot(shell, emulator)
        pause.assert_not_called()


class FavoriteRegistrationTest(unittest.TestCase):
    def test_accepts_success_with_broadcast_data(self):
        shell = Mock(return_value=SimpleNamespace(
            stdout='Broadcast completed: result=1, data="Favorite Id=[4] Runtime=[2]"\n'
        ))
        pause = Mock()
        COVER.register_favorite(shell, pause)
        shell.assert_called_once()
        pause.assert_not_called()

    def test_waits_for_the_receiver_to_register_the_installed_face(self):
        shell = Mock(side_effect=[
            SimpleNamespace(stdout="Broadcast completed: result=0\n"),
            SimpleNamespace(stdout="Broadcast completed: result=1\n"),
        ])
        pause = Mock()
        COVER.register_favorite(shell, pause)
        self.assertEqual(shell.call_count, 2)
        pause.assert_called_once_with(COVER.FAVORITE_REGISTRATION_RETRY_SECONDS)
        self.assertEqual(shell.call_args_list[0], shell.call_args_list[1])
        self.assertIn(COVER.PACKAGE, shell.call_args.args)

    def test_receiver_not_ready_is_bounded(self):
        shell = Mock(return_value=SimpleNamespace(stdout="Broadcast completed: result=0\n"))
        pause = Mock()
        with self.assertRaisesRegex(RuntimeError, "after 15 attempts"):
            COVER.register_favorite(shell, pause)
        self.assertEqual(shell.call_count, COVER.FAVORITE_REGISTRATION_ATTEMPTS)
        self.assertEqual(pause.call_count, COVER.FAVORITE_REGISTRATION_ATTEMPTS - 1)

    def test_rejects_unknown_results_without_retrying(self):
        for output in ["Broadcast completed: result=10\n", "Broadcast completed: result=-1\n", "No result"]:
            with self.subTest(output=output):
                shell = Mock(return_value=SimpleNamespace(stdout=output))
                pause = Mock()
                with self.assertRaises(RuntimeError):
                    COVER.register_favorite(shell, pause)
                shell.assert_called_once()
                pause.assert_not_called()

    def test_transport_failure_is_not_retried(self):
        shell = Mock(side_effect=subprocess.CalledProcessError(1, "adb"))
        pause = Mock()
        with self.assertRaises(subprocess.CalledProcessError):
            COVER.register_favorite(shell, pause)
        shell.assert_called_once()
        pause.assert_not_called()
