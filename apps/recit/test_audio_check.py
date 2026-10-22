"""Microphone checks use synthetic OBS float planes and mocked playback only."""
import ctypes as C
import math
from pathlib import Path
import tempfile
import time
import unittest
import wave
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QUrl
from audio_check import AudioCheck, AudioData, AudioSample
from engine import Engine
import test_app


def feed(sample, value=.25, muted=False, frames=4800):
    left = (C.c_float * frames)(*[value * math.sin(i / 7) for i in range(frames)])
    right = (C.c_float * frames)(*[value / 2 for i in range(frames)])
    data = AudioData()
    data.frames = frames
    data.data[0] = C.cast(left, C.POINTER(C.c_ubyte))
    data.data[1] = C.cast(right, C.POINTER(C.c_ubyte))
    sample.callback(None, None, C.pointer(data), muted)


class SampleChecks(unittest.TestCase):
    def test_real_callback_to_wave_samples_and_mute(self):
        for muted in (False, True):
            with tempfile.TemporaryDirectory() as root:
                sample = AudioSample(MagicMock(), 123)
                feed(sample, muted=muted)
                sample.detach()
                path = Path(root) / 'sample.wav'
                peak = sample.save(path)
                with wave.open(str(path), 'rb') as audio:
                    self.assertEqual((audio.getnchannels(), audio.getframerate(), audio.getnframes()), (2, 48000, 4800))
                    data = audio.readframes(4800)
                    self.assertEqual(any(data), not muted)
                self.assertEqual(peak == 0, muted)

    def test_bounded_and_empty(self):
        sample = AudioSample(MagicMock(), 123)
        with self.assertRaisesRegex(RuntimeError, 'No microphone signal'):
            sample.save('unused.wav')
        for _ in range(60):
            feed(sample)
        self.assertEqual(sample.frames, 240000)
        sample.detach()

    def test_engine_only_opens_microphone_and_same_filters(self):
        engine = Engine.__new__(Engine)
        engine._closed = False
        engine._output = None
        engine._obs = MagicMock()
        engine._sources = []
        engine.release_audio = MagicMock()
        engine._source = MagicMock(return_value=123)
        engine._microphone_filters = MagicMock()
        engine.verify_audio_route = MagicMock(return_value='exact.headset.source')
        engine.begin_audio_check('exact.headset.source', False)
        engine._source.assert_called_once_with('pulse_input_capture', 'RecIt microphone check', {'device_id': 'exact.headset.source'})
        engine._microphone_filters.assert_called_once_with(123, False)
        engine.end_audio_check()
        engine._obs.obs_source_remove_audio_capture_callback.assert_called_once()


class DialogChecks(unittest.TestCase):
    def setUp(self):
        self.engine, self.devices = MagicMock(), MagicMock()
        self.devices.prepare.return_value = 'exact.headset.source'
        self.devices.restore.return_value = True
        self.sample = AudioSample(MagicMock(), 123)
        feed(self.sample)
        self.engine.begin_audio_check.return_value = self.sample
        # Every playback call is mocked, so synthetic samples cannot reach speakers.
        self.player_patch = patch('audio_check.QMediaPlayer')
        self.player_type = self.player_patch.start()
        self.dialog = AudioCheck(self.engine, self.devices, 'default', True, 'Default microphone')

    def wait(self):
        deadline = time.monotonic() + 4
        while self.dialog.worker and time.monotonic() < deadline:
            test_app.qt.processEvents()
            time.sleep(.001)
        test_app.qt.processEvents()
        self.assertIsNone(self.dialog.worker)

    def tearDown(self):
        self.wait()
        self.dialog.reject()
        self.wait()
        self.dialog.deleteLater()
        self.player_patch.stop()

    def capture(self):
        self.dialog.start_check()
        self.wait()
        self.assertTrue(self.dialog.capturing)
        self.dialog.finish_capture()
        self.wait()

    def test_prepare_capture_release_restore_then_play(self):
        order = []
        self.engine.end_audio_check.side_effect = lambda: order.append('release')
        self.devices.restore.side_effect = lambda: order.append('restore') or True
        self.dialog.player.play.side_effect = lambda: order.append('play')
        self.capture()
        self.devices.prepare.assert_called_once_with('default')
        self.engine.begin_audio_check.assert_called_once_with('exact.headset.source', True)
        self.assertEqual(order, ['release', 'restore', 'play'])
        self.assertTrue(self.dialog.path.is_file())
        self.dialog.reject()
        self.assertFalse(self.dialog.path.exists())

    def test_friendly_label_tooltip_correlated_summaries_and_retry_session(self):
        from audio_debug import AudioTrace
        from test_audio_debug import records
        self.devices.source_label = 'OnePlus Buds 4'
        self.engine.audio_status.return_value = dict(source='exact.headset.source', packets=3,
            nonzero_packets=2, packet_age=.01, peak_db=-18., input_peak_db=-18., state='signal')
        with self.assertLogs('recit.audio') as logs:
            self.capture()
        rows = records(logs)
        names = [row['event'] for row in rows]
        expected = ['session.start', 'check.started', 'check.health', 'check.telemetry',
                    'check.stopped', 'check.validation']
        self.assertEqual([names.index(name) for name in expected],
                         sorted(names.index(name) for name in expected))
        trace = self.dialog.audio_trace
        self.assertIsInstance(trace, AudioTrace)
        self.assertIs(self.devices.audio_trace, trace)
        self.assertIs(self.engine.audio_trace, trace)
        self.assertEqual({row['session'] for row in rows}, {trace.session})
        self.assertEqual(self.dialog.device.text(), 'Microphone: OnePlus Buds 4')
        self.assertEqual(self.dialog.device.toolTip(), 'exact.headset.source')
        self.assertFalse(self.dialog.summary_timer.isActive())
        self.assertEqual([r['outcome'] for r in rows if r['event'] == 'check.telemetry'], [None, 'finished'])
        self.capture()
        self.assertNotEqual(self.dialog.audio_trace.session, trace.session)

    def test_deferred_restore_blocks_playback_until_safe(self):
        self.devices.restore.return_value = False
        self.capture()
        self.dialog.player.play.assert_not_called()
        self.assertIn('Another app', self.dialog.status.text())
        self.devices.restore.return_value = True
        self.dialog.prepare_playback()
        self.wait()
        self.dialog.player.play.assert_called_once()

    def test_silence_guidance_without_automatic_playback(self):
        self.sample.blocks.clear()
        self.sample.frames = 0
        feed(self.sample, muted=True)
        self.capture()
        self.assertIn('Check mute', self.dialog.status.text())
        self.dialog.player.play.assert_not_called()

    def test_empty_sample_can_retry_and_stop_clears_playback(self):
        self.sample.blocks.clear()
        self.sample.frames = 0
        self.capture()
        self.assertIn('No microphone signal', self.dialog.status.text())
        self.assertTrue(self.dialog.record.isEnabled())
        self.assertFalse(self.dialog.failed_capture)
        feed(self.sample)
        self.capture()
        self.dialog.stop_check()
        self.dialog.player.stop.assert_called()

    def test_prepare_error_releases_and_restores(self):
        self.devices.prepare.side_effect = RuntimeError('Headset disconnected')
        self.dialog.start_check()
        self.wait()
        self.assertIn('Headset disconnected', self.dialog.status.text())
        self.engine.end_audio_check.assert_called_once()
        self.devices.restore.assert_called_once()
        self.dialog.player.play.assert_not_called()

    def test_close_during_preparation_waits_and_never_plays(self):
        import threading
        ready = threading.Event()
        self.devices.prepare.side_effect = lambda _: ready.wait(2) and 'exact'
        self.dialog.start_check()
        self.dialog.reject()
        self.assertTrue(self.dialog.closing)
        ready.set()
        self.wait()
        self.engine.end_audio_check.assert_called_once()
        self.devices.restore.assert_called_once()
        self.dialog.player.play.assert_not_called()
        self.assertFalse(self.dialog.path.parent.exists())

    def test_idle_and_off_never_open_microphone(self):
        self.engine.begin_audio_check.assert_not_called()
        self.devices.prepare.assert_not_called()
        self.dialog.selection = None
        self.dialog.start_check()
        self.devices.prepare.assert_not_called()
        self.assertIn('off', self.dialog.status.text())


class EntryChecks(unittest.TestCase):
    setUp = test_app.AppChecks.setUp
    tearDown = test_app.AppChecks.tearDown

    def test_entry_guards_and_lock(self):
        window = self.window
        window.audio_devices = MagicMock()
        window.audio_devices.lease = None
        with patch('audio_check.AudioCheck') as dialog_type:
            for flag in ('recording', 'counting', 'busy', 'preparing_audio'):
                setattr(window, flag, True)
                window.open_audio_check()
                setattr(window, flag, False)
            dialog_type.assert_not_called()
            window.open_audio_check()
            self.assertTrue(window.busy)
            self.assertFalse(window.audio_check_button.isEnabled())
            self.assertFalse(window.record_button.isEnabled())
            window.audio_check_dialog = None
            window.busy = False


if __name__ == '__main__':
    unittest.main()
