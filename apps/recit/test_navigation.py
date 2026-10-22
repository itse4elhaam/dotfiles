"""Native preview ownership checks. Never initialize OBS or capture devices."""
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

import app
from engine import Engine

qt = QApplication.instance() or QApplication([])


class NavigationTests(unittest.TestCase):
    def test_repeated_navigation_detaches_before_switch_and_restores_after_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / 'silent.mp4'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10', '-t', '1',
                '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(clip)], check=True)
            with (patch.object(app.Window, 'initialize'),
                  patch.object(app.Hotkeys, 'start'),
                  patch.object(app, 'cameras', return_value=[]),
                  patch.object(app, 'microphones', return_value=[]),
                  patch.object(app, 'VIDEOS', root), patch.object(app, 'STATE', root),
                  patch.object(app, 'QSettings', return_value=QSettings(
                      str(root / 'prefs.ini'), QSettings.IniFormat))):
                window = app.Window()
                engine = window.engine = MagicMock()
                window.show()
                qt.processEvents()
                try:
                    self.assertTrue(window.preview.testAttribute(Qt.WA_DontCreateNativeAncestors))
                    for _ in range(3):
                        engine.reset_mock()
                        engine.detach_preview.side_effect = lambda: self.assertFalse(window.in_library())
                        window.open_recordings(clip)
                        window.recordings.player.setAudioOutput(None)
                        self.assertEqual(window.recordings.player.source().toLocalFile(), str(clip))
                        self.assertFalse(window.recordings.video.isHidden())
                        self.assertTrue(window.preview.isHidden())
                        engine.detach_preview.assert_called_once()
                        engine.attach_preview.assert_not_called()
                        window.recordings.back.click()
                        self.assertTrue(window.recordings.player.source().isEmpty())
                        self.assertTrue(window.recordings.video.isHidden())
                        engine.attach_preview.assert_not_called()
                        engine.attach_preview.side_effect = lambda *args: self.assertTrue(window.preview.isVisible())
                        qt.processEvents()
                        engine.attach_preview.assert_called_once_with(
                            int(window.preview.winId()),
                            round(window.preview.width() * window.preview.devicePixelRatioF()),
                            round(window.preview.height() * window.preview.devicePixelRatioF()))
                    window.open_recordings()
                    window.back_to_recorder()
                    engine.attach_preview.reset_mock()
                    window.open_recordings()
                    qt.processEvents()
                    engine.attach_preview.assert_not_called()
                finally:
                    window.close()
                    qt.processEvents()

    def test_obs_display_detach_is_synchronized_and_idempotent(self):
        engine = Engine.__new__(Engine)
        engine._display = 123
        engine._draw_callback = object()
        engine._obs = MagicMock()
        engine.detach_preview()
        engine.detach_preview()
        self.assertIsNone(engine._display)
        self.assertEqual(engine._obs.mock_calls, [
            call.obs_display_set_enabled(123, False),
            call.obs_display_remove_draw_callback(123, engine._draw_callback, None),
            call.obs_display_destroy(123)])

    def test_obs_reattach_sizes_before_enabling_and_replaces_old_display(self):
        engine = Engine.__new__(Engine)
        engine._closed = False
        engine._display = 123
        engine._xdisplay = None
        engine._draw_callback = object()
        engine._obs = MagicMock()
        engine._obs.obs_display_create.return_value = 456
        engine.attach_preview(42, 640, 360)
        calls = engine._obs.mock_calls
        self.assertEqual(calls[:3], [
            call.obs_display_set_enabled(123, False),
            call.obs_display_remove_draw_callback(123, engine._draw_callback, None),
            call.obs_display_destroy(123)])
        self.assertEqual(calls[4:], [
            call.obs_display_set_enabled(456, False),
            call.obs_display_resize(456, 640, 360),
            call.obs_display_add_draw_callback(456, engine._draw_callback, None),
            call.obs_display_set_enabled(456, True)])
