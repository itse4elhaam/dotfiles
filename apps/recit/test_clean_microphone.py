"""Clean microphone UI checks with a mocked engine and no device capture."""
import unittest
import time
from unittest.mock import MagicMock, patch
import test_app


class CleanMicrophoneChecks(unittest.TestCase):
    setUp = test_app.AppChecks.setUp
    tearDown = test_app.AppChecks.tearDown

    def test_default_persistence_and_control_lock(self):
        window = self.window
        self.assertTrue(window.clean_microphone.isChecked())
        self.assertIn('background', window.clean_microphone.toolTip())
        self.assertIn(window.clean_microphone, window.config_controls)
        window.clean_microphone.setChecked(False)
        window.save_preferences()
        window.clean_microphone.setChecked(True)
        window.restore_preferences()
        self.assertFalse(window.clean_microphone.isChecked())
        window.lock_controls(True)
        self.assertFalse(window.clean_microphone.isEnabled())
        window.lock_controls(False)
        self.assertTrue(window.clean_microphone.isEnabled())

    def test_setting_reaches_preview_and_recording_in_both_modes(self):
        window = self.window
        for mode in ('camera', 'screen'):
            window.set_mode(mode)
            for enabled in (True, False):
                window.clean_microphone.setChecked(enabled)
                for recording_setup in (False, True):
                    window.configure(microphone='test-source' if recording_setup else None,
                                     recording_setup=recording_setup)
                    kwargs = window.engine.configure.call_args.kwargs
                    self.assertEqual(kwargs['mode'], mode)
                    self.assertIs(kwargs['microphone_processing'], enabled)
                    self.assertEqual(kwargs['microphone'], 'test-source' if recording_setup else None)
        window.configure_timer.stop()

    def test_warnings_survive_ready_and_recording_status(self):
        window = self.window
        warning = 'RNNoise unavailable; using fallback.'
        window.engine.warnings = [warning]
        window.configure()
        self.assertIn(warning, window.status.text())
        window.audio_devices = MagicMock()
        window.audio_devices.resolve.return_value = 'test-source'
        window.engine.audio_status.return_value = dict(source='test-source', packets=2,
            nonzero_packets=1, packet_age=.01, state='quiet')
        with patch.object(window, 'release_audio'), patch.object(window, 'show_bubble'):
            window.audio_prepared('test-source', '')
            deadline = time.monotonic() + 2
            while window.preparing_audio and time.monotonic() < deadline:
                test_app.qt.processEvents()
                time.sleep(.001)
        window.engine.start.assert_called_once()
        self.assertTrue(window.recording)
        self.assertIn('Recording.', window.status.text())
        self.assertIn(warning, window.status.text())

    def test_mock_and_non_string_warnings_are_ignored(self):
        for warnings in (MagicMock(), None, 'not a warning list', [MagicMock(), None, '', '  ']):
            self.window.engine.warnings = warnings
            self.window.configure()
            self.assertTrue(self.window.configuration_valid)
            self.assertEqual(self.window.status.text(),
                             'Ready when you are. Your recording stays on this computer until you upload it.')


if __name__ == '__main__':
    unittest.main()
