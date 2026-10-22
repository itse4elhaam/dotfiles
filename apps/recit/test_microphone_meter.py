"""Mocked native level callbacks and offscreen widgets; no capture devices."""
import ctypes as C
import math
import threading
import unittest
from unittest.mock import Mock, patch, call

from audio_telemetry import MicrophoneTelemetry
from engine import Engine, _load_obs
import test_app


class TelemetryChecks(unittest.TestCase):
    def setUp(self):
        self.obs = Mock()
        self.obs.obs_volmeter_create.return_value = 99
        self.meter = MicrophoneTelemetry(self.obs, 42, 'selected-source')
        self.addCleanup(self.meter.close)

    def emit(self, peak, incoming=None):
        levels = (C.c_float * 8)(peak, *([-math.inf] * 7))
        inputs = (C.c_float * 8)(peak if incoming is None else incoming, *([-math.inf] * 7))
        self.meter.callback(None, levels, levels, inputs)

    def test_actual_levels_silence_quiet_signal_and_pre_fader_clipping(self):
        self.assertEqual(self.meter.status()['state'], 'no_packets')
        self.emit(-math.inf)
        self.assertEqual(self.meter.status()['state'], 'silent')
        self.emit(-90)
        self.assertEqual(self.meter.status()['state'], 'quiet')
        self.emit(-18)
        self.assertEqual(self.meter.status()['state'], 'signal')
        self.emit(-6, 0)
        status = self.meter.status()
        self.assertEqual(status['state'], 'clipping')
        self.assertEqual(status['packets'], 4)
        self.assertEqual(status['nonzero_packets'], 3)
        self.assertEqual(status['peak_db'], -6)
        self.assertEqual(status['input_peak_db'], 0)
        self.assertEqual(status['source'], 'selected-source')

    def test_stale_packets_do_not_claim_signal_or_clipping(self):
        with patch('audio_telemetry.time.monotonic', return_value=10):
            self.emit(0)
        with patch('audio_telemetry.time.monotonic', return_value=12):
            status = self.meter.status()
        self.assertEqual(status['state'], 'no_packets')
        self.assertFalse(status['signal'])
        self.assertFalse(status['clipping'])
        self.assertEqual(status['peak_db'], -math.inf)
        self.assertEqual(status['nonzero_packets'], 1)

    def test_callback_thread_and_repeated_teardown(self):
        worker = threading.Thread(target=lambda: [self.emit(-12) for _ in range(100)])
        worker.start()
        while worker.is_alive():
            status = self.meter.status()
            self.assertLessEqual(status['nonzero_packets'], status['packets'])
        worker.join()
        self.assertEqual(self.meter.status()['packets'], 100)
        self.obs.reset_mock()
        self.meter.close()
        self.meter.close()
        self.assertEqual(self.obs.mock_calls, [
            call.obs_volmeter_remove_callback(99, self.meter.callback, None),
            call.obs_volmeter_detach_source(99), call.obs_volmeter_destroy(99)])

    def test_engine_releases_callbacks_before_source(self):
        engine = Engine.__new__(Engine)
        engine._obs = self.obs
        engine._output = None
        engine._sources = engine._audio_sources = [42]
        engine._microphone_meter = self.meter
        engine.release_audio()
        calls = self.obs.mock_calls
        self.assertLess(calls.index(call.obs_volmeter_destroy(99)),
                        calls.index(call.obs_source_release(42)))
        self.assertEqual(engine.audio_status()['state'], 'off')
        self.assertEqual(engine.audio_status()['packets'], 0)

    def test_failed_attach_cleans_up(self):
        self.obs.obs_volmeter_attach_source.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'attach'):
            MicrophoneTelemetry(self.obs, 42, 'selected-source')
        self.obs.obs_volmeter_destroy.assert_called_with(99)

    def test_installed_obs27_exports_and_callback_abi_without_startup(self):
        obs = _load_obs()  # Loads symbols only. Does not initialize OBS/capture.
        self.assertEqual(obs.obs_get_version() >> 24, 27)
        self.assertEqual(obs.obs_volmeter_add_callback.argtypes[1], type(self.meter.callback))
        self.assertEqual(obs.obs_volmeter_attach_source.restype, C.c_bool)


class MeterUiChecks(unittest.TestCase):
    setUp = test_app.AppChecks.setUp
    tearDown = test_app.AppChecks.tearDown

    def test_idle_does_not_claim_microphone_was_checked_or_capture(self):
        self.window.engine.audio_status.return_value = Engine.__new__(Engine).audio_status()
        self.window.update_microphone_meter()
        meter = self.window.microphone_meter
        self.assertEqual(meter.message.text(), 'Waiting for live microphone')
        self.window.engine.start.assert_not_called()
        self.window.microphone.setCurrentIndex(1)
        self.window.update_microphone_meter()
        self.assertEqual(meter.message.text(), 'Microphone off')

    def test_active_name_states_and_long_name_sidebar_fit(self):
        window = self.window
        name = 'A long selected microphone name ' * 10
        window.microphone.addItem(name, 'test-source')
        window.microphone.setCurrentIndex(window.microphone.count() - 1)
        for state, text in [('no_packets', 'No audio packets'), ('silent', 'Silent audio'),
                            ('quiet', 'Very quiet'), ('signal', 'signal received'), ('clipping', 'Clipping')]:
            window.engine.audio_status.return_value = dict(source='test-source', state=state, peak_db=-12)
            window.update_microphone_meter()
            self.assertEqual(window.microphone_meter.name.text(), name)
            self.assertIn(text, window.microphone_meter.message.text())
        for width, height in ((960, 760), (1120, 840), (1920, 1080)):
            window.resize(width, height)
            window.show()
            test_app.qt.processEvents()
            meter = window.microphone_meter
            self.assertLessEqual(meter.width(), window.controls_panel.viewport().width())
            self.assertGreaterEqual(window.preview.height(), 360)
        window.focus_button.setChecked(True)
        self.assertTrue(window.controls_panel.isHidden())
        self.assertTrue(window.record_button.isVisible())


if __name__ == '__main__':
    unittest.main()
