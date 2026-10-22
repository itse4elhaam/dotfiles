"""Server attachment regressions. No capture, desktop, or live pactl calls."""
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import test_app
import test_audio_devices
import test_engine
from audio_check import AudioCheck, AudioSample
from audio_devices import AudioDeviceError
from engine import Engine
from test_audio_check import feed


class StreamIdentityTests(unittest.TestCase):
    def setUp(self):
        self.pulse = test_audio_devices.AudioDevicesTests()
        self.pulse.setUp()
        self.devices = self.pulse.devices
        self.source = self.devices.prepare()
        self.stream = dict(index=7356, source=42, properties={
            'application.name': 'OBS', 'application.process.id': str(os.getpid()),
            'application.process.binary': 'python3.10', 'media.name': 'RecIt microphone check'})
        self.pulse.data['source-outputs'] = [self.stream]
        self.pulse.data['sources'].append(dict(index=66, name='alsa_input.laptop'))
        self.engine = Engine.__new__(Engine)
        self.engine._microphone_route = (self.source, 'RecIt microphone check', None)
        self.service_patch = patch('engine.AudioDevices', return_value=self.devices)
        self.service_patch.start()
        self.addCleanup(self.service_patch.stop)

    def test_process_and_media_name_identify_recit_not_another_obs(self):
        self.pulse.data['source-outputs'].extend([
            dict(self.stream, index=100, source=66, properties=dict(self.stream['properties'],
                 **{'application.process.id': str(os.getpid() + 1)})),
            dict(self.stream, index=101, source=66, properties=dict(self.stream['properties'],
                 **{'media.name': 'RecIt desktop audio'}))])
        self.assertEqual(self.engine.verify_audio_route(), self.source)
        self.assertEqual(self.engine._microphone_route[2], 7356)
        self.stream['properties'].pop('application.process.id')
        with self.assertRaisesRegex(AudioDeviceError, 'Cannot verify'):
            self.engine.verify_audio_route()

    def test_requested_source_present_does_not_prove_stream_attachment(self):
        self.stream['source'] = 66
        self.assertEqual(self.devices.resolve(self.source), self.source)
        with self.assertRaisesRegex(AudioDeviceError, 'attached to alsa_input.laptop'):
            self.engine.verify_audio_route()

    def test_only_unpublished_new_stream_gets_a_bounded_wait(self):
        self.pulse.data['source-outputs'] = []
        def publish(_duration):
            self.pulse.data['source-outputs'] = [self.stream]
        with patch('engine.time.sleep', side_effect=publish) as sleep:
            self.assertEqual(self.engine.verify_audio_route(timeout=2), self.source)
            sleep.assert_called_once_with(.1)
        self.stream['source'] = 66
        with patch('engine.time.sleep') as sleep:
            with self.assertRaisesRegex(AudioDeviceError, 'stream changed'):
                self.engine.verify_audio_route(timeout=2)
            sleep.assert_not_called()

    def test_engine_start_rejects_wrong_source_despite_nonzero_telemetry(self):
        self.engine._closed = False
        self.engine._output = None
        self.engine._configured = True
        self.engine._microphone_meter = MagicMock()
        self.engine.audio_status = MagicMock(return_value=dict(packets=10,
            nonzero_packets=10, packet_age=.01))
        self.stream['source'] = 66
        with self.assertRaisesRegex(AudioDeviceError, 'attached to alsa_input.laptop'):
            self.engine.start('/unused.mkv')
        self.assertIsNone(self.engine._output)

    def test_observed_fallback_after_a2dp_and_source_removal(self):
        self.engine.verify_audio_route()
        self.pulse.card['active_profile'] = 'a2dp-sink'
        self.pulse.data['sources'] = [dict(index=66, name='alsa_input.laptop')]
        self.stream['source'] = 66
        with self.assertRaisesRegex(AudioDeviceError, 'attached to alsa_input.laptop'):
            self.engine.verify_audio_route()
        self.assertEqual(self.pulse.card['active_profile'], 'a2dp-sink')
        self.assertEqual(len([c for c in self.pulse.calls if c[0] == 'set-card-profile']), 1)

    def test_replaced_or_ambiguous_stream_is_rejected(self):
        self.engine.verify_audio_route()
        self.stream['index'] = 7357
        with self.assertRaisesRegex(AudioDeviceError, 'stream changed'):
            self.engine.verify_audio_route()
        self.pulse.data['source-outputs'].append(dict(self.stream, index=7358))
        with self.assertRaisesRegex(AudioDeviceError, 'Cannot verify'):
            self.engine.verify_audio_route()

    def test_late_verifier_does_not_write_into_new_session(self):
        verify = self.devices.verify_stream
        new_route = tuple(list(self.engine._microphone_route))
        def replaced(*args):
            index = verify(*args)
            self.engine._microphone_route = new_route
            return index
        with patch.object(self.devices, 'verify_stream', side_effect=replaced):
            with self.assertRaisesRegex(RuntimeError, 'session changed'):
                self.engine.verify_audio_route()
        self.assertEqual(self.engine._microphone_route, new_route)

    def test_same_microphone_survives_scene_configuration_and_handoff(self):
        fixture = test_engine.CameraPreviewTests()
        fixture.setUp()
        engine = fixture.engine
        engine._microphone_route = (self.source, 'RecIt microphone', None)
        engine._microphone_processing = True
        meter = engine._microphone_meter = MagicMock()
        engine._microphone_capture = 999
        engine._audio_sources = [999]
        engine._sources = [999]
        self.stream['properties']['media.name'] = 'RecIt microphone'
        engine.verify_audio_route()
        route = engine._microphone_route
        engine.configure(mode='screen', camera=None, microphone=self.source)
        self.assertIs(engine._microphone_route, route)
        self.assertIs(engine._microphone_meter, meter)
        meter.close.assert_not_called()
        engine._obs.obs_source_release.assert_not_called()
        self.assertEqual(engine.verify_audio_route(), self.source)
        self.assertEqual(engine._microphone_route[2], 7356)

    def test_deferred_restore_and_old_cleanup_cannot_restore_new_capture(self):
        old = self.devices.hold_capture()
        new = self.devices.hold_capture()
        self.devices.release_capture(old)
        # Even before OBS publishes its new stream, restoration is forbidden.
        self.pulse.data['source-outputs'] = []
        self.assertFalse(self.devices.restore())
        self.assertEqual(self.pulse.card['active_profile'], 'headset-head-unit-msbc')
        self.devices.release_capture(new)
        self.assertTrue(self.devices.restore())
        self.assertEqual(self.pulse.card['active_profile'], 'a2dp-sink')

    def test_nonzero_readiness_from_wrong_attachment_never_starts_video(self):
        fixture = test_app.AppChecks()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        window = fixture.window
        window.timer.stop()
        window.audio_devices = self.devices
        self.engine._microphone_route = (self.source, 'RecIt microphone', None)
        self.stream['properties']['media.name'] = 'RecIt microphone'
        self.stream['source'] = 66
        window.engine.verify_audio_route.side_effect = lambda **_: self.engine.verify_audio_route()
        window.engine.audio_status.return_value = dict(source=self.source, packets=10,
            nonzero_packets=10, packet_age=.01, state='signal')
        window.configure = MagicMock()
        window.configuration_valid = True
        window.audio_prepared(self.source, '')
        deadline = time.monotonic() + 3
        while window.audio_worker and time.monotonic() < deadline:
            test_app.qt.processEvents()
            time.sleep(.001)
        test_app.qt.processEvents()
        window.engine.start.assert_not_called()
        self.assertFalse(window.recording)
        self.assertIn('attached to alsa_input.laptop', window.status.text())

    def test_check_discards_nonzero_sample_after_route_moves(self):
        sample = AudioSample(MagicMock(), 123)
        feed(sample)
        engine = MagicMock()
        engine.begin_audio_check.return_value = sample
        engine.verify_audio_route.side_effect = self.engine.verify_audio_route
        with patch('audio_check.QMediaPlayer'):
            dialog = AudioCheck(engine, self.devices, self.source, True, 'OnePlus')
        def wait():
            deadline = time.monotonic() + 3
            while dialog.worker and time.monotonic() < deadline:
                test_app.qt.processEvents()
                time.sleep(.001)
            test_app.qt.processEvents()
            self.assertIsNone(dialog.worker)
        try:
            dialog.start_check()
            wait()
            self.assertTrue(dialog.capturing)
            # Reproduce the actual A2DP/source-66 fallback during the check.
            self.pulse.card['active_profile'] = 'a2dp-sink'
            self.pulse.data['sources'] = [dict(index=66, name='alsa_input.laptop')]
            self.stream['source'] = 66
            dialog.verify_route()
            wait()
            self.assertFalse(dialog.capturing)
            self.assertFalse(dialog.path.exists())
            self.assertIn('source verification failed', dialog.device.text())
            self.assertIn('attached to alsa_input.laptop', dialog.status.text())
            dialog.player.play.assert_not_called()
            engine.end_audio_check.assert_called_once()
        finally:
            dialog.reject()
            wait()
            dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
