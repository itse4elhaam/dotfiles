"""Live microphone lifecycle with mocked devices only. No OBS initialization."""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import test_app
import test_audio


class IdleAudioTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_app.AppChecks()
        self.fixture.setUp()
        self.w = w = self.fixture.window
        w.timer.stop()
        w.audio_devices = MagicMock()
        w.audio_devices.lease = None
        w.audio_devices.prepare.return_value = 'bluez.exact'
        w.audio_devices.source_label = 'OnePlus Buds 4'
        w.engine.verify_audio_route.side_effect = None
        w.engine.verify_audio_route.return_value = 'bluez.exact'
        w.engine.audio_status.return_value = dict(source='bluez.exact', state='signal', peak_db=-18,
            packets=10, nonzero_packets=10, packet_age=.01)
        w.show()

    def tearDown(self):
        self.drain()
        self.fixture.tearDown()

    def drain(self):
        deadline = time.monotonic() + 3
        while self.w.audio_worker and time.monotonic() < deadline:
            self.w.audio_worker.wait(20)
            test_app.qt.processEvents()
        test_app.qt.processEvents()

    def monitor(self):
        self.w.idle_audio.reconcile()
        self.drain()
        self.assertEqual(self.w.idle_audio.source, 'bluez.exact')
        self.w.idle_audio.reconcile()
        self.drain()

    def test_default_live_actual_source_and_friendly_name(self):
        self.assertTrue(self.w.live_microphone.isChecked())
        self.monitor()
        self.w.audio_devices.prepare.assert_called_once_with('default')
        self.w.engine.begin_audio_monitor.assert_called_once_with('bluez.exact', True)
        self.w.update_microphone_meter()
        self.assertEqual(self.w.microphone_meter.name.text(), 'OnePlus Buds 4')
        self.assertEqual(self.w.microphone_meter.level.value(), 42)
        self.assertIn('Live', self.w.microphone_meter.message.text())
        self.w.retry_audio_restore()
        self.w.audio_devices.restore.assert_not_called()

    def test_scene_mode_reconfigure_preserves_live_microphone(self):
        self.monitor()
        self.w.set_mode('screen')
        self.w.configure()
        self.assertEqual(self.w.engine.configure.call_args.kwargs['microphone'], 'bluez.exact')
        self.w.engine.begin_audio_monitor.assert_called_once()

    def test_recording_transfers_owner_without_release_or_prepare(self):
        self.monitor()
        owner = self.w.idle_audio.owner
        self.w.counting = True
        with patch.object(self.w, 'audio_prepared') as prepared:
            self.w.start()
        prepared.assert_called_once_with('bluez.exact', '')
        self.assertIs(self.w._capture_owner, owner)
        self.w.audio_devices.release_capture.assert_not_called()
        self.w.engine.release_audio.assert_not_called()
        self.w.audio_devices.prepare.assert_called_once()

    def test_real_prepare_handoff_record_and_restore_share_idle_session(self):
        import test_audio_devices
        from test_audio_debug import records
        pulse = test_audio_devices.AudioDevicesTests()
        pulse.setUp()
        w = self.w
        w.audio_devices = pulse.devices
        source = pulse.mic['name']
        w.engine.verify_audio_route.return_value = source
        w.engine.audio_status.return_value = dict(source=source, packets=10, nonzero_packets=10,
            packet_age=.01, state='signal', peak_db=-18.)
        with self.assertLogs('recit.audio') as logs:
            w.idle_audio.reconcile()
            self.drain()
            trace = w.idle_audio.audio_trace
            w.idle_audio.reconcile()
            self.drain()
            self.assertTrue(w.idle_audio.verified)
            self.assertIs(w.engine.audio_trace, trace)
            self.assertIs(w.audio_devices.audio_trace, trace)
            owner = w.idle_audio.owner
            w.counting = True
            w.start()
            self.drain()
            self.assertTrue(w.recording)
            w.engine.start.assert_called_once()
            self.assertIs(w._capture_owner, owner)
            self.assertIs(w.audio_trace, trace)
            self.assertIs(w.engine.audio_trace, trace)
            self.assertEqual(trace.purpose, 'idle')
            w.recording = False
            w.release_audio()
            self.drain()
        rows = records(logs)
        names = [r['event'] for r in rows]
        expected = ['session.start', 'idle.preparing', 'prepare.start', 'selection.chosen',
                    'profile.requested', 'source.resolved', 'idle.opened', 'idle.verified',
                    'record.requested', 'idle.handoff', 'readiness.accepted', 'restore.requested']
        self.assertEqual([names.index(name) for name in expected],
                         sorted(names.index(name) for name in expected))
        self.assertEqual(names.count('session.start'), 1)
        self.assertEqual({r['session'] for r in rows}, {trace.session})
        self.assertEqual({r['purpose'] for r in rows}, {'idle'})
        self.assertEqual([c for c in pulse.calls if c[0] == 'set-card-profile'], [
            ('set-card-profile', 'bluez_card.test', 'headset-head-unit-msbc'),
            ('set-card-profile', 'bluez_card.test', 'a2dp-sink')])

    def test_idle_health_is_throttled_and_new_capture_gets_fresh_trace(self):
        from audio_debug import AudioTrace
        from test_audio_debug import records
        self.monitor()
        trace = self.w.idle_audio.audio_trace
        self.w.idle_audio.stop()
        self.monitor()
        self.assertIsNot(self.w.idle_audio.audio_trace, trace)
        now = [0.]
        trace = AudioTrace('idle', clock=lambda: now[0])
        self.w.idle_audio.audio_trace = trace
        # Route verification already has independent coverage. Keep this check on
        # the real polling path and suppress only its two-second worker schedule.
        self.w.idle_audio.verify_at = float('inf')
        with self.assertLogs('recit.audio') as logs:
            for value in (0., .1, 1., 4.99, 5., 5.1):
                now[0] = value
                self.w.idle_audio.reconcile()
        rows = records(logs)
        self.assertEqual([r['elapsed_ms'] for r in rows if r['event'] == 'idle.telemetry'], [0, 5000])
        self.assertTrue(all(r['packets'] == 10 and r['packet_age'] == .01 for r in rows))

    def test_processing_and_selection_change_replace_only_one_chain(self):
        self.monitor()
        self.w.clean_microphone.setChecked(False)
        self.w.idle_audio.reconcile()
        self.drain()
        self.w.engine.begin_audio_monitor.assert_called_with('bluez.exact', False)
        self.w.microphone.setCurrentIndex(1)
        self.w.idle_audio.reconcile()
        self.assertIsNone(self.w.idle_audio.source)
        self.assertIsNone(self.w.idle_audio.owner)

    def test_library_back_and_monitor_toggle_release(self):
        self.monitor()
        self.w.open_recordings()
        self.assertIsNone(self.w.idle_audio.owner)
        self.w.idle_audio.reconcile()
        self.assertIsNone(self.w.idle_audio.source)
        self.drain()
        self.w.back_to_recorder()
        self.monitor()
        self.w.live_microphone.setChecked(False)
        self.assertIsNone(self.w.idle_audio.source)
        self.w.retry_audio_restore()
        self.drain()

    def test_check_releases_monitor_before_dialog_and_resumes_after(self):
        self.monitor()
        with patch('audio_check.AudioCheck') as dialog:
            self.w.open_audio_check()
            self.assertIsNone(self.w.idle_audio.owner)
            self.w.engine.release_audio.assert_called()
            dialog.return_value.finished.connect.call_args.args[0]()
        self.drain()
        self.monitor()

    def test_close_during_pending_prepare_never_opens_chain_and_restores(self):
        gate = threading.Event()
        self.w.audio_devices.prepare.side_effect = lambda _: gate.wait(2) and 'bluez.exact'
        self.w.idle_audio.reconcile()
        engine = self.w.engine
        gate.set()
        self.w.close()
        test_app.qt.processEvents()
        engine.begin_audio_monitor.assert_not_called()
        self.assertIsNone(self.w.idle_audio.owner)
        self.w.audio_devices.restore.assert_called()

    def test_pending_selection_change_discards_old_preparation(self):
        gate = threading.Event()
        self.w.audio_devices.prepare.side_effect = lambda _: gate.wait(2) and 'old-source'
        self.w.idle_audio.reconcile()
        self.w.microphone.setCurrentIndex(1)
        self.w.idle_audio.reconcile()
        self.w.audio_devices.release_capture.assert_not_called()
        gate.set()
        self.drain()
        self.w.engine.begin_audio_monitor.assert_not_called()
        self.assertIsNone(self.w.idle_audio.owner)

    def test_source_name_and_levels_wait_for_actual_route_verification(self):
        self.w.idle_audio.reconcile()
        self.drain()
        self.w.update_microphone_meter()
        self.assertIn('preparing', self.w.microphone_meter.name.text())
        self.assertEqual(self.w.microphone_meter.level.value(), 0)
        self.w.idle_audio.reconcile()
        self.drain()
        self.w.update_microphone_meter()
        self.assertEqual(self.w.microphone_meter.name.text(), 'OnePlus Buds 4')

    def test_hidden_or_disabled_never_prepares_and_errors_release(self):
        self.w.hide()
        self.w.idle_audio.reconcile()
        self.w.audio_devices.prepare.assert_not_called()
        self.w.show()
        self.w.audio_devices.prepare.side_effect = RuntimeError('Headset disconnected')
        self.w.idle_audio.reconcile()
        self.drain()
        self.assertIsNone(self.w.idle_audio.owner)
        self.w.update_microphone_meter()
        self.assertIn('disconnected', self.w.microphone_meter.message.text())

    def test_monitor_route_mismatch_releases_and_surfaces_error(self):
        self.monitor()
        self.w.engine.verify_audio_route.side_effect = RuntimeError('Wrong actual source')
        self.w.idle_audio.verify_at = 0
        self.w.idle_audio.reconcile()
        self.drain()
        self.assertIsNone(self.w.idle_audio.source)
        self.assertIn('Wrong actual source', self.w.idle_audio.error)


class MonitorEngineTests(unittest.TestCase):
    setUp = test_audio.MicrophoneRoutingTests.setUp

    def test_scene_rebuild_retains_only_microphone_and_releases_old_desktop(self):
        import test_engine
        fixture = test_engine.CameraPreviewTests()
        fixture.setUp()
        e = fixture.engine
        e._microphone_route = ('exact', 'RecIt microphone', None)
        e._microphone_processing = True
        e._microphone_meter = MagicMock()
        e._microphone_capture = 999
        e._sources = [999, 998]
        e._audio_sources = [999, 998]
        e.configure(camera=None, microphone='exact')
        e._obs.obs_source_release.assert_called_once_with(998)
        self.assertIn(999, e._sources)
        self.assertNotIn(998, e._sources)
        e._obs.obs_set_output_source.assert_any_call(2, None)
        e._microphone_meter.close.assert_not_called()

    def test_live_handoff_does_not_create_a_second_microphone(self):
        e = self.engine
        e.configure(camera=None, microphone='exact')
        meter = e._microphone_meter
        route = e._microphone_route
        e._source.reset_mock()
        e.configure(camera=None, microphone='exact', desktop_audio=True)
        self.assertIs(e._microphone_meter, meter)
        self.assertEqual(e._microphone_route, route)
        self.assertNotIn('pulse_input_capture', [c.args[0] for c in e._source.call_args_list])
        e._clear_scene.assert_called_with(preserve_audio=True)
