"""Headset lifecycle tests: mocked OBS and PulseAudio, no capture or profile changes."""
import time
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import app
import test_app
from audio_devices import AudioDeviceError
from engine import Engine, EngineError


class HeadsetIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_app.AppChecks()
        self.fixture.setUp()
        self.window = self.fixture.window
        self.window.audio_devices = MagicMock()
        self.window.audio_devices.lease = None
        self.window.audio_devices.prepare.return_value = 'bluez_input.exact'
        self.window.engine.recording = False
        self.window.audio_devices.resolve.return_value = 'bluez_input.exact'
        self.window.engine.audio_status.side_effect = lambda: dict(
            source=self.window.selected_source, packets=3, nonzero_packets=1,
            packet_age=.01, state='quiet')

    def tearDown(self):
        if self.window.audio_worker:
            self.window.audio_worker.wait()
            test_app.qt.processEvents()
        self.fixture.tearDown()

    def start_and_wait(self):
        self.window.counting = True
        self.window.lock_controls(True)
        self.window.start()
        deadline = time.monotonic() + 3
        while self.window.preparing_audio and time.monotonic() < deadline:
            test_app.qt.processEvents()
            time.sleep(.001)
        test_app.qt.processEvents()
        self.assertFalse(self.window.preparing_audio)

    def test_preview_has_no_audio_then_start_uses_exact_microphone(self):
        self.window.configure()
        args = self.window.engine.configure.call_args.kwargs
        self.assertIsNone(args['microphone'])
        self.assertFalse(args['desktop_audio'])
        self.start_and_wait()
        self.window.audio_devices.prepare.assert_called_once_with('default')
        self.assertEqual(self.window.engine.configure.call_args.kwargs['microphone'], 'bluez_input.exact')
        self.window.engine.start.assert_called_once()
        self.assertTrue(self.window.recording)

    def test_explicit_and_off_selections_pass_through(self):
        for source in ('usb_explicit', None):
            self.window.microphone.addItem(str(source), source)
            self.window.microphone.setCurrentIndex(self.window.microphone.count() - 1)
            self.window.configure_timer.stop()
            self.window.configure()
            self.window.audio_devices.prepare.return_value = source
            self.window.audio_devices.resolve.return_value = source
            self.start_and_wait()
            self.window.audio_devices.prepare.assert_called_with(source)
            self.assertEqual(self.window.engine.configure.call_args.kwargs['microphone'], source)
            self.window.recording = False

    def test_prepare_failure_never_starts_and_releases_before_restore(self):
        self.window.audio_devices.prepare.side_effect = AudioDeviceError('Headset disconnected')
        self.window.audio_devices.lease = ('card', 'old', 'new')
        order = []
        self.window.engine.release_audio.side_effect = lambda: order.append('release')
        self.window.audio_devices.restore.side_effect = lambda: order.append('restore') or True
        self.start_and_wait()
        self.window.retry_audio_restore()
        if self.window.audio_worker:
            self.window.audio_worker.wait()
            test_app.qt.processEvents()
        self.window.engine.start.assert_not_called()
        self.assertEqual(order[:2], ['release', 'restore'])
        self.assertIn('Headset disconnected', self.window.status.text())

    def test_disconnect_stops_with_saved_video_warning(self):
        self.start_and_wait()
        self.window.audio_devices.resolve.reset_mock()
        self.window.audio_devices.resolve.side_effect = AudioDeviceError('missing exact source')
        with patch.object(self.window, 'stop') as stop:
            self.window.tick()
            self.window.audio_worker.wait()
            test_app.qt.processEvents()
            stop.assert_called_once()
        self.assertIn('Microphone disconnected', self.window.recording_error)
        self.window.audio_devices.resolve.assert_called_once_with('bluez_input.exact')

    def test_stop_releases_audio_without_tearing_down_scene(self):
        self.start_and_wait()
        self.window.busy = True
        with patch.object(self.window, 'finish_save'):
            self.window.stopped(str(self.fixture.root / 'empty.mkv'), '')
        self.window.engine.release_audio.assert_called_once()
        self.window.engine.close.assert_not_called()

    def test_deferred_restoration_retries_only_when_idle(self):
        self.window.audio_devices.lease = ('card', 'old', 'new')
        self.window.audio_devices.restore.return_value = False
        self.window.retry_audio_restore()
        self.window.audio_worker.wait()
        test_app.qt.processEvents()
        self.window.audio_devices.restore.assert_called_once()
        self.window.recording = True
        self.window.retry_audio_restore()
        self.window.audio_devices.restore.assert_called_once()
        self.window.recording = False
        self.window.retry_audio_restore()
        self.window.audio_worker.wait()
        test_app.qt.processEvents()
        self.assertEqual(self.window.audio_devices.restore.call_count, 2)

    def test_failed_engine_start_releases_audio(self):
        self.window.engine.start.side_effect = RuntimeError('encoder failed')
        self.start_and_wait()
        self.assertFalse(self.window.recording)
        self.window.engine.release_audio.assert_called_once()
        self.assertIn('encoder failed', self.window.status.text())

    def test_cancel_countdown_never_prepares(self):
        self.window.toggle_record()
        self.window.cancel_countdown()
        self.window.audio_devices.prepare.assert_not_called()
        self.window.engine.start.assert_not_called()

    def test_close_restores_after_engine_close(self):
        order = []
        self.window.engine.close.side_effect = lambda: order.append('close')
        self.window.audio_devices.restore.side_effect = lambda: order.append('restore') or True
        self.window.close()
        self.assertEqual(order, ['close', 'restore'])

    def test_audio_release_keeps_scene_and_rejects_active_recording(self):
        engine = Engine.__new__(Engine)
        engine._output = None
        engine._obs = MagicMock()
        engine._sources = [101, 202]
        engine._audio_sources = [202]
        engine._scene = 303
        engine.release_audio()
        self.assertEqual(engine._sources, [101])
        self.assertEqual(engine._scene, 303)
        engine._obs.obs_source_release.assert_called_once_with(202)
        engine._output = 404
        engine._obs.obs_output_active.return_value = True
        with self.assertRaises(EngineError):
            engine.release_audio()


class HeadsetRoundtripTests(unittest.TestCase):
    """Real selection/restoration helper + Qt lifecycle; only Pulse/OBS are fake."""
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        cls.clip = Path(cls.media.name) / 'silent.mkv'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10', '-t', '0.2',
            '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.clip)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.media.cleanup()

    def setUp(self):
        HeadsetIntegrationTests.setUp(self)
        from test_audio_devices import AudioDevicesTests
        self.pulse = AudioDevicesTests()
        self.pulse.setUp()
        self.window.audio_devices = self.pulse.devices
        command = self.pulse.devices.command
        def pulse_command(*args):
            result = command(*args)
            if args[0] == 'set-card-profile' and args[2] == 'a2dp-sink':
                self.pulse.data['sources'] = [dict(name='brio', index=1),
                    dict(name='buds.monitor', index=2)]
            return result
        self.pulse.devices.command = pulse_command
        self.events = []
        self.window.engine.configure.side_effect = self.configure_engine
        self.window.engine.release_audio.side_effect = self.release_engine
        self.window.engine.close.side_effect = self.release_engine
        def record(path):
            shutil.copyfile(self.clip, path)
            self.events.append('record')
        self.window.engine.start.side_effect = record
        self.window.engine.stop.side_effect = lambda: self.events.append('stop')

    start_and_wait = HeadsetIntegrationTests.start_and_wait
    tearDown = HeadsetIntegrationTests.tearDown

    def configure_engine(self, **kwargs):
        source = kwargs['microphone']
        if source:
            self.assertEqual(self.pulse.card['active_profile'], 'headset-head-unit-msbc')
            self.assertEqual(source, self.pulse.mic['name'])
            self.pulse.data['source-outputs'] = [dict(source=42)]
            self.events.append('capture')

    def release_engine(self):
        self.events.append('release')
        self.pulse.data['source-outputs'] = []

    def drain(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            worker = self.window.audio_worker
            if worker:
                worker.wait(100)
            test_app.qt.processEvents()
            if not self.window.audio_worker:
                return
        self.fail('Audio worker did not finish')

    def finish(self):
        self.window.stop()
        self.wait_saved()

    def wait_saved(self):
        self.assertTrue(self.window.worker.wait(3000))
        deadline = time.monotonic() + 3
        while self.window.busy and time.monotonic() < deadline:
            test_app.qt.processEvents()
            time.sleep(.001)
        self.drain()
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.last_file.exists())
        self.assertEqual(self.window.last_file.suffix, '.mp4')
        self.assertFalse(self.window.record_path.exists())

    def switches(self):
        return [c[2] for c in self.pulse.calls if c[0] == 'set-card-profile']

    # These tests use the actual helper, unlike the mocked-helper parent cases.
    def test_roundtrip_stop_and_subsequent_recording(self):
        self.window.configure()
        self.assertEqual(self.switches(), [])
        for _ in range(2):
            self.start_and_wait()
            self.assertEqual(self.window.selected_source, self.pulse.mic['name'])
            self.assertTrue(self.window.recording)
            self.window.tick()
            self.drain()
            self.assertIn('Microphone: ' + self.pulse.mic['name'], self.window.status.text())
            self.assertFalse(self.pulse.devices.restore())  # OBS still owns capture.
            self.finish()
            self.assertEqual(self.pulse.card['active_profile'], 'a2dp-sink')
            self.assertIsNone(self.pulse.devices.lease)
        self.assertEqual(self.switches(), ['headset-head-unit-msbc', 'a2dp-sink'] * 2)
        self.assertEqual(self.events, ['capture', 'record', 'stop', 'release'] * 2)

    def test_failed_start_restores_after_release(self):
        self.window.engine.start.side_effect = RuntimeError('encoder failed')
        self.start_and_wait()
        self.drain()
        self.assertFalse(self.window.recording)
        self.assertEqual(self.events, ['capture', 'release'])
        self.assertEqual(self.switches(), ['headset-head-unit-msbc', 'a2dp-sink'])

    def test_busy_playback_defers_then_retries_and_external_change_wins(self):
        self.start_and_wait()
        self.pulse.data['sink-inputs'] = [dict(sink=43)]
        self.finish()
        self.assertEqual(self.pulse.card['active_profile'], 'headset-head-unit-msbc')
        self.assertIsNotNone(self.pulse.devices.lease)
        self.pulse.data['sink-inputs'] = []
        self.window.retry_audio_restore()
        self.drain()
        self.assertEqual(self.pulse.card['active_profile'], 'a2dp-sink')
        self.start_and_wait()
        self.pulse.card['active_profile'] = 'off'  # Another client changed it.
        self.finish()
        self.assertEqual(self.pulse.card['active_profile'], 'off')
        self.assertIsNone(self.pulse.devices.lease)
        self.assertEqual(self.switches(), ['headset-head-unit-msbc', 'a2dp-sink', 'headset-head-unit-msbc'])

    def test_disconnect_stops_and_releases_then_can_record_again(self):
        self.start_and_wait()
        self.pulse.data['sources'] = []
        self.window.tick()
        self.drain()
        self.assertIn('Microphone disconnected', self.window.recording_error)
        self.wait_saved()
        self.assertEqual(self.pulse.card['active_profile'], 'a2dp-sink')
        self.start_and_wait()
        self.assertTrue(self.window.recording)
        self.finish()

    def test_close_during_preparation_never_starts_queued_capture(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        original = self.pulse.devices.prepare
        def prepare(selection):
            result = original(selection)
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test preparation timed out')
            return result
        self.pulse.devices.prepare = prepare
        self.window.counting = True
        self.window.start()
        self.assertTrue(entered.wait(3))
        timer = threading.Timer(.05, release.set)
        timer.start()
        try:
            self.window.close()
            self.drain()
        finally:
            release.set()
            timer.join()
        self.assertIsNone(self.window.engine)
        self.assertTrue(self.window._closing)
        self.assertNotIn('record', self.events)
        self.assertNotIn('capture', self.events)
        self.assertEqual(self.switches(), ['headset-head-unit-msbc', 'a2dp-sink'])

    def test_explicit_brio_and_off_do_not_switch(self):
        for source in ('brio', None):
            self.window.engine.configure.side_effect = None
            self.window.microphone.addItem(str(source), source)
            self.window.microphone.setCurrentIndex(self.window.microphone.count() - 1)
            self.window.configure_timer.stop()
            self.window.configure()
            self.start_and_wait()
            self.assertEqual(self.window.engine.configure.call_args.kwargs['microphone'], source)
            self.assertEqual(self.window.selected_source, source)
            self.finish()
        self.assertEqual(self.switches(), [])

    def test_cancel_and_library_never_switch(self):
        self.window.toggle_record()
        self.window.cancel_countdown()
        self.window.open_recordings()
        self.window.start()
        self.assertEqual(self.switches(), [])
        self.window.engine.start.assert_not_called()

    def test_failed_preparation_after_switch_restores_and_reports(self):
        self.pulse.publish = False
        self.start_and_wait()
        self.drain()
        self.window.engine.start.assert_not_called()
        self.assertEqual(self.switches(), ['headset-head-unit-msbc', 'a2dp-sink'])
        self.assertIn('did not become available', self.window.status.text())

    def test_prior_handsfree_is_restored_exactly_and_unowned_is_untouched(self):
        self.pulse.card['active_profile'] = 'headset-head-unit-cvsd'
        self.start_and_wait()
        self.finish()
        self.assertEqual(self.pulse.card['active_profile'], 'headset-head-unit-cvsd')
        self.assertEqual(self.switches(), ['headset-head-unit-msbc', 'headset-head-unit-cvsd'])
        self.pulse.card['active_profile'] = 'headset-head-unit-msbc'
        self.pulse.calls.clear()
        self.start_and_wait()
        self.assertIsNone(self.pulse.devices.lease)
        self.finish()
        self.assertEqual(self.switches(), [])
        self.assertEqual(self.pulse.card['active_profile'], 'headset-head-unit-msbc')
