"""Readiness with synthetic native level callbacks. Never initialize OBS/capture."""
import ctypes as C
import math
import time
import unittest
from unittest.mock import MagicMock, patch

import app
import test_app
from audio_devices import AudioDeviceError
from audio_telemetry import MicrophoneTelemetry
from engine import Engine, EngineError


class AudioReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_app.AppChecks()
        self.fixture.setUp()
        self.window = self.fixture.window
        self.window.timer.stop()
        self.window.audio_devices = MagicMock()
        self.window.audio_devices.lease = None
        self.window.audio_devices.resolve.return_value = 'exact-mic'
        self.obs = MagicMock()
        self.meter = MicrophoneTelemetry(self.obs, 42, 'exact-mic')
        self.window.engine.audio_status.side_effect = self.meter.status

    def tearDown(self):
        if self.window.audio_worker:
            self.window.audio_worker.wait()
            test_app.qt.processEvents()
        self.fixture.tearDown()
        self.meter.close()

    def emit(self, value):
        levels = (C.c_float * 8)(value, *([-math.inf] * 7))
        self.meter.callback(None, levels, levels, levels)

    def prepare(self):
        self.window.lock_controls(True)
        self.window.audio_prepared('exact-mic', '')

    def drain(self):
        deadline = time.monotonic() + 2
        while self.window.preparing_audio and time.monotonic() < deadline:
            test_app.qt.processEvents()
            time.sleep(.001)

    def expire(self):
        self.window._audio_deadline = 0
        self.window.poll_microphone(self.window._audio_generation)

    def test_no_packets_and_zero_only_are_distinct_and_never_start(self):
        for silence, expected in ((False, 'No microphone samples'), (True, 'only silence')):
            with self.subTest(silence=silence):
                if silence:
                    self.emit(-math.inf)
                self.prepare()
                self.assertIn('say a few words', self.window.status.text())
                self.assertTrue(self.window.preparing_audio)
                self.expire()
                self.window.engine.start.assert_not_called()
                self.assertIn(expected, self.window.status.text())
                self.assertFalse(self.window.busy)
                self.assertTrue(self.window.audio_check_button.isEnabled())

    def test_quiet_finite_sample_passes_without_speech_threshold(self):
        self.emit(-95)
        self.prepare()
        self.drain()
        self.window.audio_devices.resolve.assert_called_once_with('exact-mic')
        self.window.engine.start.assert_called_once()
        self.assertTrue(self.window.recording)

    def test_stale_signal_and_desktop_source_cannot_pass(self):
        with patch('audio_telemetry.time.monotonic', return_value=0):
            self.emit(-12)
        self.prepare()
        self.expire()
        self.window.engine.start.assert_not_called()
        self.emit(-12)
        self.meter.source_id = 'desktop-output'
        self.prepare()
        self.expire()
        self.window.engine.start.assert_not_called()

    def test_disconnected_muted_or_changed_exact_source_after_samples_fails(self):
        for error, result in ((AudioDeviceError('muted'), None),
                              (AudioDeviceError('disconnected'), None), (None, 'other-mic')):
            with self.subTest(error=error, result=result):
                self.emit(-12)
                self.window.audio_devices.resolve.side_effect = error
                self.window.audio_devices.resolve.return_value = result
                self.prepare()
                self.drain()
                self.window.engine.start.assert_not_called()
                self.assertFalse(self.window.preparing_audio)
                self.assertIn(str(error) if error else 'changed', self.window.status.text())

    def test_cancel_invalidates_queued_samples_and_metadata_result(self):
        self.prepare()
        generation = self.window._audio_generation
        self.window.cancel_countdown()
        self.emit(-12)
        self.window.poll_microphone(generation)
        self.window.microphone_verified(generation, 'exact-mic', '')
        self.window.begin_recording(generation)
        self.window.engine.start.assert_not_called()
        self.assertIn('cancelled', self.window.status.text())
        self.window.engine.release_audio.assert_called_once()

    def test_close_during_sample_wait_invalidates_pending_start(self):
        self.prepare()
        generation = self.window._audio_generation
        engine = self.window.engine
        self.window.close()
        self.emit(-12)
        self.window.poll_microphone(generation)
        self.window.microphone_verified(generation, 'exact-mic', '')
        self.window.begin_recording(generation)
        engine.start.assert_not_called()
        engine.close.assert_called_once()

    def test_deliberate_microphone_off_starts_without_samples(self):
        self.window.audio_prepared(None, '')
        self.window.engine.start.assert_called_once()
        self.window.audio_devices.resolve.assert_not_called()

    def test_silence_warning_is_delayed_pauses_reset_and_errors_survive(self):
        self.window.selected_source = 'exact-mic'
        with patch('app.time.monotonic', return_value=10):
            self.emit(-math.inf)
            self.assertEqual(self.window.microphone_warning(), '')
        with patch('app.time.monotonic', return_value=24):
            self.emit(-math.inf)
            self.assertEqual(self.window.microphone_warning(), '')
        self.window.recording_error = 'Keep the original error'
        with patch('app.time.monotonic', return_value=25):
            # Keep callback fresh while advancing the synthetic clock.
            self.emit(-math.inf)
            self.assertIn('only silence', self.window.microphone_warning())
        self.assertEqual(self.window.recording_error, 'Keep the original error')
        self.window.paused = True
        self.assertEqual(self.window.microphone_warning(), '')
        self.assertIsNone(self.window._audio_warning_since)

    def test_no_sample_warning_waits_five_seconds(self):
        self.window.selected_source = 'exact-mic'
        with patch('app.time.monotonic', return_value=10):
            self.assertEqual(self.window.microphone_warning(), '')
        with patch('app.time.monotonic', return_value=14):
            self.assertEqual(self.window.microphone_warning(), '')
        with patch('app.time.monotonic', return_value=15):
            self.assertIn('stopped arriving', self.window.microphone_warning())

    def test_engine_refuses_start_before_verified_samples_without_capture(self):
        engine = Engine.__new__(Engine)
        engine._closed = False
        engine._output = None
        engine._configured = True
        engine._microphone_meter = self.meter
        with self.assertRaisesRegex(EngineError, 'no verified audio'):
            engine.start(self.fixture.root / 'unused.mkv')
        self.emit(-math.inf)
        with self.assertRaisesRegex(EngineError, 'no verified audio'):
            engine.start(self.fixture.root / 'unused.mkv')
        self.assertFalse((self.fixture.root / 'unused.mkv').exists())
