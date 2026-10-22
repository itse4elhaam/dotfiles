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
        devices = MagicMock()
        devices.lease = None
        devices.prepare.return_value = 'test-microphone'
        self.patches = [patch.object(glint, 'AudioDevices', return_value=devices),
            patch.object(glint.Window, 'initialize'), patch.object(glint.Hotkeys, 'start'),
            patch.object(glint, 'cameras', return_value=[('Test camera', '/dev/video-test')]),
            patch.object(glint, 'microphones', return_value=[]), patch.object(glint, 'VIDEOS', self.root),
            patch.object(glint, 'STATE', self.root), patch.object(glint, 'QSettings', return_value=QSettings(str(self.root/'prefs.ini'), QSettings.IniFormat))]
        for p in self.patches:
            p.start()
        self.window = glint.Window()
        self.window.engine = MagicMock()
        self.window.engine.verify_audio_route.side_effect = lambda **_: self.window.audio_devices.resolve(self.window.selected_source)
        self.window.engine.recording = False
        self.window.engine.errors = []
        self.window.configure()

    def tearDown(self):
        self.window.recording = self.window.busy = self.window.counting = False
        self.window.close()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_sharing_offers_loom_connect_without_manual_credentials(self):
        def inspect_dialog(dialog):
            buttons = dialog.findChildren(glint.QPushButton)
            self.assertEqual([button.text() for button in buttons], [
                'Connect Loom account ↗', 'Open Loom connection instructions ↗', 'Done',
            ])
            self.assertEqual(dialog.findChildren(glint.QLineEdit), [])
            text = ' '.join(item.text() for item in dialog.findChildren(glint.QLabel)).lower()
            self.assertIn('browser oauth', text)
            for rejected in ('google', 'drive', 'api key', 'cloud console', 'client json', 'token'):
                self.assertNotIn(rejected, text)
            buttons[0].click()
            dialog.findChildren(glint.QCheckBox)[0].setChecked(True)
            dialog.findChildren(glint.QComboBox)[0].setCurrentIndex(1)
            return glint.QDialog.Accepted

        with patch.object(self.window, 'find_cli', return_value='/fake/twg'), \
                patch.object(self.window, 'connect_loom') as connect, \
                patch.object(glint.QDialog, 'exec', new=inspect_dialog):
            self.window.sharing_settings()
        connect.assert_called_once_with()
        self.assertTrue(self.window.prefs.value('auto_upload', False, type=bool))
        self.assertEqual(self.window.prefs.value('visibility'), 'workspace')

    def test_loom_connect_uses_same_cli_and_never_authenticates_in_process(self):
        with patch.object(self.window, 'find_cli', return_value='/fake/twg'), patch.object(glint.shutil, 'which', return_value='/fake/terminal'), patch.object(glint.subprocess, 'Popen') as launch:
            self.window.connect_loom()
        self.assertEqual(launch.call_args.args[0][-1], '/fake/twg')
        self.assertIn('No video is uploaded', self.window.status.text())

    def test_loom_rejects_missing_and_empty_files_without_process(self):
        self.window.last_file = self.root / 'missing.mp4'
        with patch.object(self.window, 'find_cli', return_value='/fake/twg'), patch.object(glint, 'QProcess') as process:
            self.window.upload()
            self.assertIn('missing', self.window.status.text())
            self.window.last_file.touch()
            self.window.upload()
            self.assertIn('empty', self.window.status.text())
            process.assert_not_called()

    def test_loom_help_and_upload_snapshot_and_visibility_failure(self):
        path = self.root / 'local video.mp4'
        path.write_bytes(b'private video')
        self.window.set_last(path)
        self.window.prefs.setValue('visibility', 'owner')
        qt.clipboard().setText('unchanged')
        with patch.object(self.window, 'find_cli', return_value='/fake/twg'), patch.object(glint, 'QProcess') as process_type:
            process_type.NormalExit = QProcess.NormalExit
            process = process_type.return_value
            self.window.upload()
            self.assertEqual(process.setArguments.call_args.args[0], ['loom', 'video', 'upload', '--help'])
            process.readAllStandardOutput.return_value = b'Usage: twg loom video upload [options] <file>'
            process.readAllStandardError.return_value = b''
            self.window.upload_help(0, QProcess.NormalExit)
            self.assertEqual(process.setArguments.call_args.args[0], ['loom', 'video', 'upload', str(path), '-o', 'json'])
            self.window.prefs.setValue('visibility', 'public')
            process.readAllStandardOutput.return_value = b'{"url":"https://www.loom.com/share/abc123"}'
            self.window.upload_done(0, QProcess.NormalExit)
            self.assertEqual(process.setArguments.call_args.args[0][-4:], ['--visibility', 'owner', '-o', 'json'])
            self.assertEqual(qt.clipboard().text(), 'unchanged')
            self.window.visibility_done(1, QProcess.NormalExit)
            self.assertEqual(qt.clipboard().text(), 'unchanged')
            self.assertFalse(self.window.busy)
            self.assertEqual(path.read_bytes(), b'private video')

    def test_loom_unknown_help_and_failed_start_unlock_controls(self):
        self.window.busy = True
        self.window.process = MagicMock()
        self.window.process.readAllStandardOutput.return_value = b'Usage: unsupported grammar'
        self.window.process.readAllStandardError.return_value = b''
        self.window.upload_help(0, QProcess.NormalExit)
        self.assertFalse(self.window.busy)
        self.assertIn('syntax could not be verified', self.window.status.text())
        self.window.busy = True
        self.window._upload_url = 'https://www.loom.com/share/abc123'
        self.window.upload_process_error(QProcess.FailedToStart)
        self.assertFalse(self.window.busy)
        self.assertIn('sharing command could not start', self.window.status.text())

    def test_loom_visibility_success_copies_only_after_confirmation(self):
        self.window._upload_url = 'https://www.loom.com/share/abc123'
        self.window.visibility_done(0, QProcess.NormalExit)
        self.assertEqual(qt.clipboard().text(), self.window._upload_url)

    def test_loom_error_does_not_expose_cli_secrets(self):
        self.window.process = MagicMock()
        self.window.process.readAllStandardOutput.return_value = b''
        self.window.process.readAllStandardError.return_value = b'OAuth token secret-private-value expired'
        self.window.upload_done(1, QProcess.NormalExit)
        self.assertNotIn('secret-private-value', self.window.status.text())
        self.assertIn('connect your Loom account', self.window.status.text())

    def test_library_navigation_blocks_hotkeys_and_delayed_capture(self):
        path = self.root / 'latest.mp4'
        path.touch()
        self.window.set_last(path)
        self.window.open_recordings(path)
        page = self.window.recordings
        page.player.setAudioOutput(None)
        self.assertIs(self.window.pages.currentWidget(), page)
        self.assertEqual(page.player.source().toLocalFile(), str(path))
        self.assertFalse(self.window.tray_record.isEnabled())
        self.window.toggle_record()
        self.assertFalse(self.window.counting)
        self.window.counting = True  # Even a stale queued start cannot capture.
        self.window.start()
        self.window.counting = False
        self.window.engine.start.assert_not_called()
        self.window.engine.configure.reset_mock()
        self.window.configure()
        self.window.engine.configure.assert_not_called()
        page.back.click()
        self.assertIs(self.window.pages.currentWidget(), self.window.recorder_page)
        self.assertTrue(page.player.source().isEmpty())
        self.assertTrue(self.window.tray_record.isEnabled())
        self.window.toggle_record()
        self.assertTrue(self.window.counting)
        self.window.open_recordings(path)
        self.assertFalse(self.window.in_library())
        self.window.cancel_countdown()
        self.window.open_recordings()
        self.assertIs(self.window.recordings, page)
        self.window.busy = True
        self.window.lock_controls(True)
        self.assertFalse(self.window.in_library())
        self.assertTrue(page.player.source().isEmpty())

    def test_camera_is_default_and_can_expand_without_hiding_record_controls(self):
        self.assertEqual(self.window.mode, 'camera')
        self.assertTrue(self.window.capture_kind.isHidden())
        self.assertTrue(self.window.zoom_button.isHidden())
        self.window.focus_button.setChecked(True)
        self.assertTrue(self.window.controls_panel.isHidden())
        self.assertFalse(self.window.record_button.isHidden())
        self.window.focus_button.setChecked(False)
        self.assertFalse(self.window.controls_panel.isHidden())
        self.window.focus_button.setChecked(True)
        self.window.set_mode('screen')
        self.assertFalse(self.window.controls_panel.isHidden())
        self.assertFalse(self.window.capture_kind.isHidden())
        self.assertTrue(self.window.focus_button.isHidden())
        self.window.set_mode('camera')
        self.window.capture_kind.setCurrentIndex(1)
        self.assertTrue(self.window.screen.isHidden())
        self.assertTrue(self.window.window_row.isHidden())

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
        self.window.open_recordings(path)
        self.window.recordings.copy.click()
        self.assertEqual(qt.clipboard().text(), str(path))
        self.assertIn('on your computer', self.window.recordings.message.text())

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
        self.window.open_recordings(path)
        self.assertEqual(self.window.recordings.upload.text(), 'Prepare MP4')
        self.window.prefs.setValue('auto_upload', True)
        with patch.object(self.window, 'remux') as remux, patch.object(glint, 'QProcess') as process:
            self.window.recordings.upload.click()
            remux.assert_called_once_with(path)
            self.assertTrue(self.window.busy)
            self.assertFalse(self.window.in_library())
            self.assertFalse(self.window.recordings.upload.isEnabled())
            target = path.with_suffix('.mp4')
            target.write_bytes(b'recovered MP4')
            self.window.remux_done(path, target, 0)
            process.assert_not_called()  # Recovery never automatically uploads.
        self.assertEqual(self.window.last_file, target)
        self.assertIn('Play it back', self.window.status.text())

    def test_library_upload_uses_selected_file_and_blocks_busy_actions(self):
        latest = self.root / 'latest.mp4'
        selected = self.root / 'selected.mp4'
        for path in (latest, selected):
            path.write_bytes(b'synthetic recording')
        self.window.set_last(latest)
        self.window.open_recordings(selected)
        page = self.window.recordings
        page.player.setAudioOutput(None)
        for state in ('recording', 'counting', 'busy'):
            setattr(self.window, state, True)
            page.update_actions()
            self.assertFalse(page.upload.isEnabled())
            with patch.object(self.window, 'upload') as upload:
                page.upload_selected()
                self.window.upload_recording(str(selected))
                upload.assert_not_called()
            setattr(self.window, state, False)
        page.update_actions()
        with patch.object(self.window, 'find_cli', return_value='/fake/twg'), patch.object(glint, 'QProcess') as process:
            page.upload.click()
            self.assertEqual(self.window._upload_file, selected.resolve())
            self.assertEqual(process.return_value.setArguments.call_args.args[0],
                             ['loom', 'video', 'upload', '--help'])
            self.assertFalse(self.window.in_library())
            self.assertTrue(page.player.source().isEmpty())
            self.assertFalse(page.upload.isEnabled())
            self.window.upload_end('Mock upload finished')
        self.assertTrue(page.upload.isEnabled())

    def test_library_recovery_preserves_existing_mp4(self):
        source = self.root / 'interrupted.mkv'
        target = source.with_suffix('.mp4')
        source.write_bytes(b'recoverable original')
        target.write_bytes(b'existing MP4')
        self.window.open_recordings(source)
        with patch.object(self.window, 'remux') as remux, patch.object(glint, 'QProcess') as process:
            self.window.recordings.upload.click()
            remux.assert_not_called()
            process.assert_not_called()
        self.assertFalse(self.window.busy)
        self.assertEqual(source.read_bytes(), b'recoverable original')
        self.assertEqual(target.read_bytes(), b'existing MP4')
        self.assertIn('Both files are preserved', self.window.status.text())

    def test_upload_with_visibility_flag_copies_link_and_unlocks(self):
        path = self.root / 'selected.mp4'
        path.write_bytes(b'synthetic recording')
        self.window.open_recordings(path)
        with patch.object(self.window, 'find_cli', return_value='/fake/twg'), patch.object(glint, 'QProcess') as process_type:
            process_type.NormalExit = QProcess.NormalExit
            self.window.recordings.upload.click()
            process = process_type.return_value
            process.readAllStandardOutput.return_value = b'Usage: twg loom video upload <file> --visibility'
            process.readAllStandardError.return_value = b''
            self.window.upload_help(0, QProcess.NormalExit)
            self.assertIn('--visibility', process.setArguments.call_args.args[0])
            process.readAllStandardOutput.return_value = b'{"url":"https://www.loom.com/share/abc123"}'
            self.window.upload_done(0, QProcess.NormalExit)
        self.assertEqual(qt.clipboard().text(), 'https://www.loom.com/share/abc123')
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.library_button.isEnabled())
        self.assertTrue(self.window.recordings.upload.isEnabled())

    def test_successful_save_auto_uploads_saved_file(self):
        path = self.root / 'saved.mp4'
        path.write_bytes(b'saved recording')
        self.window.prefs.setValue('auto_upload', True)
        with patch.object(self.window, 'upload') as upload:
            self.window.finish_save(path, '')
            upload.assert_called_once_with()
        self.assertEqual(self.window.last_file, path)

    def test_failed_stop_restores_pointer_zoom(self):
        self.window.set_mode('screen')
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
        self.window.set_mode('screen')
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
