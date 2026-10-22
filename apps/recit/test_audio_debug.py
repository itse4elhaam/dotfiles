"""Correlated diagnostics using fake Pulse/OBS and synthetic samples only."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import test_audio_devices
from audio_debug import AudioTrace, traced
from audio_devices import AudioDeviceError
from engine import Engine, recording_audio_warning


def records(captured):
    return [json.loads(record.getMessage().split(' ', 1)[1]) for record in captured.records]


class AudioDebugTests(unittest.TestCase):
    def setUp(self):
        self.pulse = test_audio_devices.AudioDevicesTests()
        self.pulse.setUp()
        self.pulse.load_recorded_headset()
        self.devices = self.pulse.devices
        self.trace = AudioTrace(clock=lambda: self.pulse.now)
        self.devices.audio_trace = self.trace
        self.live = patch('audio_devices.subprocess.run', return_value=SimpleNamespace(
            returncode=0, stdout='b true'))
        self.live.start()
        self.addCleanup(self.live.stop)

    def test_prepare_record_stop_restore_validate_sequence_and_correlation(self):
        engine = Engine.__new__(Engine)
        engine.audio_trace = self.trace
        engine._closed, engine._output, engine._configured = False, None, True
        engine._obs = MagicMock()
        engine._obs.obs_output_paused.return_value = False
        engine._stop_event = threading.Event()
        engine._stop_event.set()
        engine.encoders, engine.warnings = ['obs_x264'], []
        engine._microphone_noise_backend = MagicMock(return_value=('noise_suppress_filter', 'rnnoise'))
        engine._filter = MagicMock()
        engine._create_recording = lambda *_: setattr(engine, '_output', 123)
        engine._release_recording = lambda: setattr(engine, '_output', None)
        engine.stats = MagicMock(return_value={})
        status = dict(source=self.pulse.mic['name'], packets=8, nonzero_packets=4,
                      packet_age=.01, state='signal', peak_db=-20., input_peak_db=-20.)
        with tempfile.TemporaryDirectory() as root, self.assertLogs('recit.audio') as logs:
            self.trace.event('session.start', selection='default')
            source = self.devices.prepare()
            engine._microphone_filters(123)
            self.trace.telemetry('readiness', status, outcome='ready')
            engine.start(Path(root) / 'synthetic.mkv')
            self.trace.telemetry('health', status)
            engine.stop()
            self.devices.restore()
            with patch('engine.subprocess.run', side_effect=[
                SimpleNamespace(returncode=0, stdout='{"streams":[{"index":1}]}'),
                SimpleNamespace(returncode=0, stderr='Peak level dB: -20\nNumber of samples: 4800')]):
                self.assertEqual(recording_audio_warning(Path(root) / 'synthetic.mkv', self.trace), '')
        rows = records(logs)
        names = [r['event'] for r in rows]
        expected = ['session.start', 'selection.chosen', 'profile.selected', 'profile.requested',
                    'profile.ready', 'source.resolved', 'filters.backend', 'filter.applied',
                    'readiness.telemetry', 'record_start.done', 'health.telemetry',
                    'record_stop.done', 'restore.requested', 'saved_validation.result']
        positions = [names.index(name) for name in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual({row['session'] for row in rows}, {self.trace.session})
        resolved = next(r for r in rows if r['event'] == 'source.resolved')
        self.assertEqual(resolved['source'], source)
        self.assertEqual(resolved['sample_specification'], 's16le 1ch 16000Hz')
        self.assertEqual(resolved['obs_rate'], 48000)
        connection = next(r for r in rows if r['event'] == 'connection.checked')
        self.assertEqual(connection['card'], self.pulse.card['name'])
        self.assertNotIn('source', connection)
        self.assertEqual(connection['connection_signal'], 'org.bluez.Device1.Connected')
        self.assertTrue(connection['connected'])
        self.assertEqual(connection['stale_connection'], 'disconnected')
        self.assertEqual(self.devices.source_label, 'OnePlus Buds 4')
        profile = next(r for r in rows if r['event'] == 'profile.selected')
        self.assertEqual(profile['card'], self.pulse.card['name'])
        self.assertEqual(profile['prior_profile'], 'a2dp-sink')
        self.assertTrue(profile['changed'])

    def test_noop_profile_is_distinct_from_change(self):
        self.pulse.card['active_profile'] = 'headset-head-unit-msbc'
        self.pulse.data['sources'] = [self.pulse.mic]
        with self.assertLogs('recit.audio') as logs:
            self.devices.prepare()
        rows = records(logs)
        self.assertFalse(next(r for r in rows if r['event'] == 'profile.selected')['changed'])
        self.assertNotIn('profile.requested', [r['event'] for r in rows])
        self.assertIsNone(self.devices.lease)

    def test_timeout_and_typed_exception_keep_phase_and_elapsed_without_message(self):
        self.pulse.publish = False
        with self.assertLogs('recit.audio') as logs:
            with self.assertRaises(AudioDeviceError):
                self.devices.prepare(timeout=.2)
        rows = records(logs)
        timeout = next(r for r in rows if r['event'] == 'prepare.timeout')
        self.assertEqual(timeout['phase'], 'profile_source')
        self.assertEqual(timeout['exception_type'], 'TimeoutError')
        self.assertGreaterEqual(timeout['elapsed_ms'], 200)
        self.assertEqual(rows[-1]['exception_type'], 'AudioDeviceError')
        self.assertGreaterEqual(rows[-1]['duration_ms'], 200)
        owner = SimpleNamespace(audio_trace=self.trace)
        @traced('secret_failure')
        def fail(_):
            raise ValueError('token=DO_NOT_LOG_VOICE_TRANSCRIPT')
        with self.assertLogs('recit.audio') as logs:
            with self.assertRaises(ValueError):
                fail(owner)
        self.assertEqual(records(logs)[-1]['exception_type'], 'ValueError')
        self.assertNotIn('DO_NOT_LOG', ' '.join(logs.output))

    def test_throttled_poll_summaries_and_immediate_warning(self):
        status = dict(source='exact', packets=7, nonzero_packets=2, state='quiet', peak_db=-math.inf)
        with self.assertLogs('recit.audio') as logs:
            for now in (0, .1, 1, 4.99, 5, 5.1):
                self.pulse.now = now
                self.trace.telemetry('health', status)
            self.trace.event('health.warning', level='warning', reason='silent')
            self.trace.telemetry('readiness', status, outcome='timeout')
        rows = records(logs)
        self.assertEqual([r['elapsed_ms'] for r in rows if r['event'] == 'health.telemetry'], [0, 5000])
        self.assertIsNone(rows[0]['peak_db'])
        self.assertEqual(rows[-2]['level'], 'warning')
        self.assertEqual(rows[-1]['outcome'], 'timeout')

    def test_route_reports_actual_source_and_mismatch_with_same_session(self):
        source = self.devices.prepare()
        stream = dict(index=7356, source=42, properties={
            'application.process.id': str(os.getpid()), 'application.name': 'OBS', 'media.name': 'RecIt microphone'})
        self.pulse.data['source-outputs'] = [stream]
        self.pulse.data['sources'].append(dict(index=66, name='alsa_input.unwanted'))
        engine = Engine.__new__(Engine)
        engine.audio_trace = self.trace
        engine._microphone_route = (source, 'RecIt microphone', None)
        with patch('engine.AudioDevices', return_value=self.devices), self.assertLogs('recit.audio') as logs:
            self.assertEqual(engine.verify_audio_route(), source)
            stream['source'] = 66
            with self.assertRaises(AudioDeviceError):
                engine.verify_audio_route()
        rows = records(logs)
        attached = next(r for r in rows if r['event'] == 'route.verified')
        mismatch = next(r for r in rows if r['event'] == 'route.mismatch')
        self.assertEqual(attached['actual_source'], source)
        self.assertEqual(mismatch['requested_source'], source)
        self.assertEqual(mismatch['actual_source'], 'alsa_input.unwanted')
        self.assertEqual(mismatch['stream_index'], 7356)
        self.assertEqual({r['session'] for r in rows}, {self.trace.session})

    def test_privacy_no_payloads_or_subprocess_output_and_no_callback_logging(self):
        from audio_check import AudioSample
        from test_audio_check import feed
        secret = 'PRIVATE_PCM_TRANSCRIPT_TOKEN_ENV'
        sample = AudioSample(MagicMock(), 123)
        with patch('audio_debug.logger.log') as log:
            feed(sample)
            sample.detach()
            log.assert_not_called()
        with self.assertLogs('recit.audio') as logs:
            self.trace.telemetry('health', dict(source='exact', packets=1, pcm=secret,
                                              transcript=secret, token=secret, environ=secret))
            self.trace.event('privacy.checked', pcm=secret, transcript=secret, token=secret, env=secret,
                             full_pactl_json={'secret': secret}, data=b'raw audio')
            with patch('engine.subprocess.run', side_effect=subprocess.TimeoutExpired(secret, 30, stderr=secret)):
                self.assertIn('could not be verified', recording_audio_warning(Path(secret), self.trace))
        self.assertNotIn(secret, ' '.join(logs.output))
        self.assertNotIn('raw audio', ' '.join(logs.output))
        self.assertEqual(records(logs)[-1]['exception_type'], 'TimeoutExpired')

    def test_configure_source_events_follow_creation_success_and_failure(self):
        import test_engine
        for fail in (False, True):
            fixture = test_engine.CameraPreviewTests()
            fixture.setUp()
            engine = fixture.engine
            engine.audio_trace = self.trace
            engine._source = MagicMock(side_effect=RuntimeError('secret device error') if fail else [301, 302])
            engine._microphone_filters = MagicMock()
            with patch('engine.os.access', return_value=True), patch('engine.camera_settings', return_value={}), \
                    patch('engine.MicrophoneTelemetry'), self.assertLogs('recit.audio') as logs:
                if fail:
                    # Camera succeeds; the following microphone source fails.
                    engine._source.side_effect = [301, RuntimeError('secret device error')]
                    with self.assertRaises(RuntimeError):
                        engine.configure(mode='camera', camera='/dev/fake', microphone='exact')
                else:
                    engine.configure(mode='camera', camera='/dev/fake', microphone='exact')
            outcomes = [r['outcome'] for r in records(logs) if r['event'] == 'obs.source']
            self.assertEqual(outcomes, ['requested'] if fail else ['requested', 'created'])
            self.assertNotIn('secret device error', ' '.join(logs.output))

    def test_quick_check_attaches_existing_telemetry_and_releases_it(self):
        import ctypes as C
        from audio_telemetry import MicrophoneTelemetry
        engine = Engine.__new__(Engine)
        engine.audio_trace = AudioTrace('check')
        engine._closed, engine._output = False, None
        engine._obs = MagicMock()
        engine._sources = []
        engine._source = MagicMock(return_value=123)
        engine._microphone_filters = MagicMock()
        engine.verify_audio_route = MagicMock()
        with self.assertLogs('recit.audio') as logs:
            engine.begin_audio_check('exact', True)
            self.assertIsInstance(engine._microphone_meter, MicrophoneTelemetry)
            values = (C.c_float * 8)(*([-20.] + [-math.inf] * 7))
            with patch('audio_debug.logger.log') as log:
                engine._microphone_meter.callback(None, values, values, values)
                log.assert_not_called()
            engine.audio_trace.telemetry('check', engine.audio_status(), outcome='finished')
            engine.end_audio_check()
        self.assertEqual([r['outcome'] for r in records(logs) if r['event'] == 'obs.source'],
                         ['requested', 'created'])
        status = next(r for r in records(logs) if r['event'] == 'check.telemetry')
        self.assertEqual((status['packets'], status['nonzero_packets']), (1, 1))
        self.assertEqual(status['state'], 'signal')
        self.assertLess(status['packet_age'], 1.5)
        self.assertEqual(status['peak_db'], -20.)
        engine._obs.obs_volmeter_detach_source.assert_called_once()
        self.assertIsNone(engine._microphone_meter)

    def test_deferred_restore_keeps_profile_changing_session_after_new_capture(self):
        with self.assertLogs('recit.audio') as logs:
            self.devices.prepare()
            self.pulse.data['source-outputs'] = [dict(source=42)]
            self.assertFalse(self.devices.restore())
            newer = AudioTrace('idle')
            self.devices.audio_trace = newer
            self.devices.prepare()
            self.pulse.data['source-outputs'] = []
            self.assertTrue(self.devices.restore())
        rows = records(logs)
        restore = [r for r in rows if r['event'].startswith('restore.')]
        self.assertTrue(restore)
        self.assertEqual({r['session'] for r in restore}, {self.trace.session})
        self.assertIs(self.devices.audio_trace, newer)
        self.assertNotEqual(newer.session, self.trace.session)
