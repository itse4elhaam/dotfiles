"""UI and recovery checks without touching the camera or microphone.
Run: QT_QPA_PLATFORM=offscreen ~/.local/share/glint/venv/bin/python apps/recit/test_app.py
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings, QTimer, QProcess
import app as glint

qt = QApplication.instance() or QApplication([])


class AppChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(glint.Window, 'initialize'), patch.object(glint.Hotkeys, 'start'),
            patch.object(glint, 'cameras', return_value=[('Test camera', '/dev/video-test')]),
            patch.object(glint, 'microphones', return_value=[]), patch.object(glint, 'VIDEOS', self.root),
            patch.object(glint, 'STATE', self.root), patch.object(glint, 'QSettings', return_value=QSettings(str(self.root/'prefs.ini'), QSettings.IniFormat))]
        for p in self.patches:
            p.start()
        self.window = glint.Window()
        self.window.engine = MagicMock()
        self.window.engine.recording = False
        self.window.engine.errors = []
        self.window.configure()

    def tearDown(self):
        self.window.recording = self.window.busy = self.window.counting = False
        self.window.close()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_modes_configure_expected_scene(self):
        self.window.set_mode('camera')
        self.window.configure_timer.stop()
        self.window.configure()
        self.assertEqual(self.window.engine.configure.call_args.kwargs['mode'], 'camera')
        self.assertFalse(self.window.widget_panel.isVisible())
        self.window.camera.setCurrentIndex(0)
        self.window.configure()
        self.assertFalse(self.window.record_button.isEnabled())
        self.assertIn('Choose a camera', self.window.status.text())

    def test_countdown_cancel_never_records(self):
        self.window.toggle_record()
        self.assertTrue(self.window.counting)
        self.window.cancel_countdown()
        self.assertFalse(self.window.counting)
        self.window.engine.start.assert_not_called()
        self.assertTrue(self.window.record_button.isEnabled())

    def test_stop_failure_keeps_recording_locked(self):
        self.window.recording = self.window.busy = True
        self.window.engine.recording = True
        self.window.lock_controls(True)
        self.window.stopped(str(self.root/'test.mkv'), 'timed out')
        self.assertTrue(self.window.recording)
        self.assertFalse(self.window.busy)
        self.assertFalse(self.window.camera.isEnabled())
        self.assertTrue(self.window.record_button.isEnabled())

    def test_failed_remux_preserves_original(self):
        source, target = self.root/'test.mkv', self.root/'test.mp4'
        source.write_bytes(b'recoverable original')
        target.write_bytes(b'partial export')
        self.window.process = MagicMock()
        self.window.process.readAllStandardError.return_value = b'failed'
        self.window.remux_done(source, target, 1)
        self.assertEqual(source.read_bytes(), b'recoverable original')
        self.assertFalse(target.exists())
        self.assertEqual(self.window.last_file, source)
        self.assertIn('safe', self.window.status.text())

    def test_success_remux_offers_mp4(self):
        source, target = self.root/'test.mkv', self.root/'test.mp4'
        source.write_bytes(b'original')
        target.write_bytes(b'finished mp4')
        self.window.remux_done(source, target, 0)
        self.assertFalse(source.exists())
        self.assertEqual(self.window.last_file, target)

    def test_copy_path_does_not_claim_public_link(self):
        path = self.root/'video.mp4'
        path.write_bytes(b'video')
        self.window.set_last(path)
        self.window.copy_path()
        self.assertEqual(qt.clipboard().text(), str(path))
        self.assertIn('local file', self.window.status.text())

    def test_upload_failure_does_not_remove_local_recording(self):
        path = self.root/'video.mp4'
        path.write_bytes(b'video')
        self.window.set_last(path)
        self.window.process = MagicMock()
        self.window.process.readAllStandardOutput.return_value = b''
        self.window.process.readAllStandardError.return_value = b'account needs login'
        self.window.upload_done(1, QProcess.NormalExit)
        self.assertTrue(path.exists())
        self.assertFalse(self.window.busy)
        self.assertIn('local recording is safe', self.window.status.text())

    def test_upload_completion_cannot_enable_invalid_camera_setup(self):
        self.window.camera.setCurrentIndex(0)
        self.window.set_mode('camera')
        self.window.configure_timer.stop()
        self.window.configure()
        self.assertFalse(self.window.configuration_valid)
        self.window.upload_end('Upload complete')
        self.assertFalse(self.window.record_button.isEnabled())

    def test_cancel_stops_pending_start_timer(self):
        self.window.toggle_record()
        self.window.countdown = 1
        self.window.countdown_tick()
        self.assertTrue(self.window.start_timer.isActive())
        self.window.cancel_countdown()
        self.assertFalse(self.window.start_timer.isActive())
        self.window.toggle_record()
        self.assertEqual(self.window.countdown, 3)
        self.window.engine.start.assert_not_called()
        self.window.cancel_countdown()

    def test_recovered_mkv_offers_preparation(self):
        path = self.root/'RecIt-interrupted.mkv'
        path.write_bytes(b'recoverable')
        self.window.set_last(path)
        self.assertEqual(self.window.upload_button.text(), 'Prepare MP4')
        with patch.object(self.window, 'remux') as remux:
            self.window.upload()
            remux.assert_called_once_with(path)
            self.assertTrue(self.window.busy)

    def test_failed_stop_restores_pointer_zoom(self):
        self.window.recording = self.window.busy = True
        self.window.engine.recording = True
        self.window.zoom_motion.enabled = True
        self.window.zoom_button.setEnabled(False)
        self.window.tray_zoom.setEnabled(False)
        self.window.stopped(str(self.root/'test.mkv'), 'timed out')
        self.assertTrue(self.window.zoom_button.isEnabled())
        self.assertTrue(self.window.tray_zoom.isEnabled())
        self.assertTrue(self.window.zoom_timer.isActive())

    def test_recording_error_blocks_automatic_upload(self):
        path = self.root/'RecIt-error.mp4'
        path.write_bytes(b'partial recording')
        self.window.prefs.setValue('auto_upload', True)
        self.window.recording_error = 'Recording ended with an error. Review before sharing.'
        with patch.object(self.window, 'upload') as upload:
            self.window.finish_save(path, self.window.recording_error)
            upload.assert_not_called()
        self.assertIn('error', self.window.status.text())

    def window_target(self):
        self.window.window_catalog = MagicMock()
        self.window.window_catalog.list.return_value = [('Test browser', 123)]
        self.window.window_catalog.geometry.return_value = (100, 200, 500, 400)
        self.window.capture_kind.setCurrentIndex(1)
        self.window.configure_timer.stop()
        self.window.configure()

    def test_window_selection_uses_only_selected_window_with_composited_camera(self):
        self.window_target()
        options = self.window.engine.configure.call_args.kwargs
        self.assertEqual(options['window_id'], 123)
        self.assertFalse(options['floating_camera'])
        self.assertTrue(self.window.configuration_valid)

    def test_closed_window_stops_and_preserves_warning(self):
        self.window_target()
        self.window.recording = True
        self.window.window_catalog.geometry.return_value = None
        with patch.object(self.window, 'stop') as stop:
            self.window.tick()
            stop.assert_called_once()
        self.assertIn('closed or was minimized', self.window.recording_error)

    def test_window_zoom_uses_window_relative_pointer(self):
        import time
        self.window_target()
        self.window.recording = True
        self.window.zoom_motion.enabled = True
        self.window.zoom_motion.last_time = time.monotonic() - .05
        self.window.window_catalog.pointer.return_value = (350, 300)
        self.window.animate_zoom()
        args = self.window.engine.set_screen_zoom.call_args.args
        self.assertAlmostEqual(args[1], .5)
        self.assertAlmostEqual(args[2], .25)


if __name__ == '__main__':
    unittest.main()
