from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import Mock

from tools import capture_cover as COVER


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
