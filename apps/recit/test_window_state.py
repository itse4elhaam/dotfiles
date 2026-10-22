"""Window lifecycle regressions with no OBS, devices, or desktop access."""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
import app

qt = QApplication.instance() or QApplication([])


class WindowStateTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for target, name, value in [
            (app.Window, 'initialize', None), (app.Hotkeys, 'start', None),
            (app, 'cameras', []), (app, 'microphones', []),
        ]:
            self.stack.enter_context(patch.object(target, name, return_value=value))
        for name, value in [('VIDEOS', root), ('STATE', root),
                            ('QSettings', lambda *args: QSettings(str(root / 'prefs.ini'), QSettings.IniFormat))]:
            self.stack.enter_context(patch.object(app, name, value))
        self.window = app.Window()
        self.addCleanup(self.cleanup_window)
        self.window.engine = MagicMock()
        self.window.engine.errors = []
        self.window.engine.recording = False
        self.window.configuration_valid = True
        self.window.showMaximized()
        qt.processEvents()

    def cleanup_window(self):
        self.window.recording = self.window.counting = self.window.busy = False
        self.window.close()
        qt.processEvents()

    def assert_maximized(self):
        self.assertTrue(self.window.windowState() & Qt.WindowMaximized)
        self.assertFalse(self.window.windowState() & Qt.WindowMinimized)
        self.assertTrue(self.window.isVisible())

    def countdown(self, mode):
        self.window.mode = mode
        self.window.record_button.setEnabled(True)
        self.window.toggle_record()
        self.window.countdown = 1
        self.window.countdown_tick()
        self.window.start_timer.stop()

    def test_explicit_reveal_keeps_maximized_and_unminimizes(self):
        self.window.reveal()
        self.assert_maximized()
        self.window.showMinimized()
        self.window.reveal()
        self.assert_maximized()

    def test_cancel_preserves_camera_and_screen_window_state(self):
        for mode in ('camera', 'screen'):
            with self.subTest(mode=mode):
                self.countdown(mode)
                self.assertEqual(self.window.isVisible(), mode == 'camera')
                self.window.cancel_countdown()
                self.assert_maximized()

    def test_failed_preparation_restores_only_capture_hidden_window(self):
        for mode in ('camera', 'screen'):
            with self.subTest(mode=mode), patch.object(self.window, 'raise_') as raised, patch.object(self.window, 'activateWindow') as activated:
                self.countdown(mode)
                self.window.counting = False
                self.window.audio_prepared(None, 'synthetic failure')
                self.assert_maximized()
                raised.assert_not_called()
                activated.assert_not_called()

    def test_camera_completion_respects_user_minimization(self):
        self.window.mode = 'camera'
        self.window.showMinimized()
        self.window.stopped('', 'synthetic save failure')
        self.assertTrue(self.window.windowState() & Qt.WindowMinimized)
        self.assertTrue(self.window.windowState() & Qt.WindowMaximized)

    def test_screen_completion_restores_normal_or_maximized_without_focus(self):
        for maximized in (False, True):
            with self.subTest(maximized=maximized), patch.object(self.window, 'raise_') as raised, patch.object(self.window, 'activateWindow') as activated:
                self.window.showMaximized() if maximized else self.window.showNormal()
                self.countdown('screen')
                self.window.counting = False
                self.window.stopped('', 'synthetic save failure')
                self.assertTrue(self.window.isVisible())
                self.assertEqual(bool(self.window.windowState() & Qt.WindowMaximized), maximized)
                self.assertFalse(self.window.windowState() & Qt.WindowMinimized)
                raised.assert_not_called()
                activated.assert_not_called()

    def test_library_back_and_stale_preview_do_not_change_window_state(self):
        self.window.open_recordings()
        self.assert_maximized()
        self.window.back_to_recorder()
        qt.processEvents()
        self.assert_maximized()
        self.window.open_recordings()
        self.window.back_to_recorder()
        self.window.showMinimized()
        qt.processEvents()
        self.assertTrue(self.window.windowState() & Qt.WindowMinimized)
        self.assertTrue(self.window.windowState() & Qt.WindowMaximized)

    def test_engine_start_failure_restores_capture_window(self):
        self.countdown('screen')
        self.window.counting = False
        self.window.engine.start.side_effect = RuntimeError('synthetic start failure')
        with patch.object(self.window, 'configure'), patch.object(app.shutil, 'disk_usage', return_value=MagicMock(free=2 ** 40)):
            self.window.audio_prepared(None, '')
        self.assert_maximized()
        self.assertIn('synthetic start failure', self.window.status.text())

    def test_explicit_reveal_supersedes_delayed_capture_restoration(self):
        self.countdown('screen')
        self.window.counting = False
        self.window.reveal()
        self.window.showNormal()
        self.window.showMinimized()
        self.window.audio_prepared(None, 'delayed failure')
        self.assertTrue(self.window.windowState() & Qt.WindowMinimized)
        self.assertFalse(self.window.windowState() & Qt.WindowMaximized)

    def test_mode_and_camera_focus_toggles_preserve_maximization(self):
        with patch.object(self.window, 'configure'):
            for mode in ('screen', 'camera', 'screen', 'camera'):
                self.window.set_mode(mode)
                qt.processEvents()
                self.assert_maximized()
            self.window.focus_button.click()
            qt.processEvents()
            self.assert_maximized()
            self.window.focus_button.click()
            qt.processEvents()
            self.assert_maximized()

    def test_close_invalidates_deferred_preview_restoration(self):
        self.window.open_recordings()
        self.window.back_to_recorder()
        engine = self.window.engine
        self.window.close()
        qt.processEvents()
        engine.attach_preview.assert_not_called()

    def test_successful_stop_restores_before_remux_and_save_keeps_state(self):
        self.countdown('screen')
        self.window.counting = False
        source = app.VIDEOS / 'synthetic.mkv'
        source.write_bytes(b'synthetic engine output')
        with patch.object(self.window, 'remux') as remux:
            self.window.stopped(str(source), '')
            remux.assert_called_once_with(source)
        self.assert_maximized()
        self.window.finish_save(source, '')
        self.assert_maximized()

    def test_pause_failure_does_not_unminimize_camera_window(self):
        self.window.mode = 'camera'
        self.window.recording = True
        self.window.engine.pause.side_effect = RuntimeError('synthetic pause failure')
        self.window.showMinimized()
        self.window.toggle_pause()
        self.assertTrue(self.window.windowState() & Qt.WindowMinimized)
        self.assertTrue(self.window.windowState() & Qt.WindowMaximized)
