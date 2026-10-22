import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from audio_devices import AudioDeviceError, AudioDevices, handsfree_profile, on_card


class AudioDevicesTests(unittest.TestCase):
    def setUp(self):
        self.card = dict(name='bluez_card.test', index=17, active_profile='a2dp-sink', profiles={
            'headset-head-unit-cvsd': dict(sources=1, available=True),
            'headset-head-unit-msbc': dict(sources=1, available=True),
            'headset-head-unit-lc3-swb': dict(sources=1, available=False)})
        self.mic = dict(name='bluez_input.test.0', index=42, properties={'device.name': 'bluez_card.test'})
        self.data = {'info': dict(default_source_name='brio', default_sink_name='buds'),
                     'cards': [self.card], 'sources': [dict(name='brio', index=1), dict(name='buds.monitor', index=2)],
                     'sinks': [dict(name='buds', index=43, properties={'device.name': 'bluez_card.test'})],
                     'source-outputs': [], 'sink-inputs': []}
        self.calls = []
        self.now = 0
        self.publish = True
        self.devices = AudioDevices(self.command, lambda: self.now, self.sleep)

    def command(self, *args):
        self.calls.append(args)
        if args[0] == 'set-card-profile':
            self.card['active_profile'] = args[2]
            if self.publish:
                self.data['sources'] = [self.mic]
            return ''
        return json.dumps(self.data[args[-1]])

    def sleep(self, duration):
        self.now += duration

    def test_on_card_rejects_conflicting_stable_name_with_reused_index(self):
        source = dict(self.mic, card=self.card['index'],
                      properties={'device.name': 'bluez_card.other'})
        self.assertFalse(on_card(source, self.card))

    def test_on_card_accepts_stable_name_despite_changed_index(self):
        source = dict(self.mic, card=self.card['index'] + 1)
        self.assertTrue(on_card(source, self.card))

    def test_on_card_uses_numeric_index_without_stable_name(self):
        for properties in ({}, {'device.name': ''}, {'device.name': None}):
            with self.subTest(properties=properties):
                source = dict(card=str(self.card['index']), properties=properties)
                self.assertTrue(on_card(source, self.card))
                source['card'] = self.card['index'] + 1
                self.assertFalse(on_card(source, self.card))

    def test_on_card_rejects_missing_identity(self):
        for source in ({}, {'card': None},
                       {'properties': {'device.id': str(self.card['index'])}}):
            with self.subTest(source=source):
                self.assertFalse(on_card(source, self.card))

    def test_default_is_system_not_first_source_and_monitors_excluded(self):
        self.data['sources'].insert(0, dict(name='other', index=9))
        self.assertEqual(self.devices.resolve(), 'brio')
        self.assertEqual(self.devices.microphones(), [('other', 'other'), ('brio (system default)', 'brio')])
        self.assertFalse(any(c[0] == 'set-card-profile' for c in self.calls))

    def test_prepares_exact_obs_source_and_restores(self):
        self.assertEqual(self.devices.prepare(), 'bluez_input.test.0')
        self.assertEqual(self.card['active_profile'], 'headset-head-unit-msbc')
        self.assertTrue(self.devices.restore())
        self.assertEqual(self.card['active_profile'], 'a2dp-sink')

    def test_muted_and_zero_volume_rejected_without_changing_gain(self):
        for metadata, message in ((dict(mute=True), 'muted'),
                                  (dict(volume={'mono': {'value': 0}}), 'zero')):
            with self.subTest(metadata=metadata):
                self.mic.update(metadata)
                with self.assertRaisesRegex(AudioDeviceError, message):
                    self.devices.prepare()
                self.assertFalse(any(c[0] in ('set-source-mute', 'set-source-volume') for c in self.calls))
                self.mic.pop('mute', None)
                self.mic.pop('volume', None)

    def test_default_output_gap_retries_without_webcam_fallback(self):
        sinks = self.data['sinks']
        self.data['sinks'] = []
        with self.assertRaisesRegex(AudioDeviceError, 'output'):
            self.devices.prepare(timeout=.2)
        self.assertIsNone(self.devices.lease)
        def publish(duration):
            self.sleep(duration)
            self.data['sinks'] = sinks
        self.devices.sleep = publish
        self.assertEqual(self.devices.prepare(timeout=.2), self.mic['name'])

    def test_real_non_bluetooth_output_keeps_actual_default_microphone(self):
        self.data['sinks'] = [dict(name='buds', index=43)]
        self.assertEqual(self.devices.prepare(), 'brio')
        self.assertIsNone(self.devices.lease)

    def test_headset_source_can_arrive_after_profile(self):
        self.publish = False
        def publish(duration):
            self.sleep(duration)
            self.data['sources'] = [self.mic]
        self.devices.sleep = publish
        self.assertEqual(self.devices.prepare(timeout=.2), self.mic['name'])

    def test_explicit_and_disabled_auto_do_not_switch(self):
        self.assertEqual(self.devices.prepare('brio'), 'brio')
        self.assertEqual(self.devices.prepare(auto_headset=False), 'brio')
        self.assertIsNone(self.devices.prepare(None))
        self.assertIsNone(self.devices.lease)

    def test_missing_default_and_disconnected_fail(self):
        self.data['info']['default_source_name'] = 'absent'
        with self.assertRaises(AudioDeviceError):
            self.devices.resolve()
        self.card['properties'] = {'api.bluez5.connection': 'disconnected'}
        with self.assertRaises(AudioDeviceError):
            self.devices.prepare()
        self.assertIsNone(self.devices.lease)

    def test_timeout_does_not_fall_back_to_brio(self):
        self.publish = False
        with self.assertRaisesRegex(AudioDeviceError, 'did not become available'):
            self.devices.prepare(timeout=.2)
        self.assertIsNotNone(self.devices.lease)

    def test_restore_defers_for_other_streams_and_respects_profile_change(self):
        self.devices.prepare()
        self.data['source-outputs'] = [dict(source=42)]
        self.assertFalse(self.devices.restore())
        self.assertIsNotNone(self.devices.lease)
        self.data['source-outputs'] = []
        self.data['sink-inputs'] = [dict(sink=43)]
        self.assertFalse(self.devices.restore())
        self.card['active_profile'] = 'off'
        self.assertTrue(self.devices.restore())
        self.assertEqual(self.card['active_profile'], 'off')

    def test_profile_failure_and_removal(self):
        command = self.devices.command
        def fail(*args):
            if args[0] == 'set-card-profile':
                raise AudioDeviceError('switch failed')
            return command(*args)
        self.devices.command = fail
        with self.assertRaisesRegex(AudioDeviceError, 'switch failed'):
            self.devices.prepare()
        self.devices.command = command
        self.devices.lease = None
        self.publish = False
        def unplug(duration):
            self.data['cards'] = []
            self.sleep(duration)
        self.devices.sleep = unplug
        with self.assertRaisesRegex(AudioDeviceError, 'disconnected'):
            self.devices.prepare()

    def test_wideband_only_when_advertised(self):
        self.assertEqual(handsfree_profile(self.card), 'headset-head-unit-msbc')
        self.card['profiles']['headset-head-unit-lc3-swb']['available'] = True
        self.assertEqual(handsfree_profile(self.card), 'headset-head-unit-lc3-swb')
        del self.card['profiles']['headset-head-unit-lc3-swb']
        del self.card['profiles']['headset-head-unit-msbc']
        self.assertEqual(handsfree_profile(self.card), 'headset-head-unit-cvsd')

    def load_recorded_headset(self):
        # pactl snapshot taken read-only on PipeWire 1.0.3; address sanitized.
        self.data = json.loads((Path(__file__).parent / 'fixtures/oneplus-a2dp.json').read_text())
        self.card = self.data['cards'][0]
        self.mic.update(properties=dict(self.card['properties']))
        self.mic['name'] = 'bluez_input.AA_BB_CC_DD_EE_FF.0'
        self.mic['sample_specification'] = 's16le 1ch 16000Hz'

    def test_recorded_stale_disconnected_metadata_roundtrip(self):
        self.load_recorded_headset()
        with patch('audio_devices.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = self.data['bluez_connected']
            self.assertEqual(self.devices.prepare(), self.mic['name'])
            self.assertEqual(self.devices.resolve(self.mic['name']), self.mic['name'])
            self.assertIn(self.mic['name'], [name for _, name in self.devices.microphones()])
            self.assertTrue(self.devices.restore())
        self.assertEqual(self.card['active_profile'], 'a2dp-sink')
        self.assertIsNone(self.devices.lease)

    def test_recorded_phantom_nodes_never_override_bluez_disconnect(self):
        self.load_recorded_headset()
        self.data['sources'] = [self.mic]
        self.card['properties']['api.bluez5.connection'] = 'connected'
        with patch('audio_devices.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'b false\n'
            with self.assertRaises(AudioDeviceError):
                self.devices.prepare(timeout=.2)
            with self.assertRaises(AudioDeviceError):
                self.devices.resolve(self.mic['name'])
        self.assertIsNone(self.devices.lease)
        self.assertFalse(any(c[0] == 'set-card-profile' for c in self.calls))

    def test_recorded_reconnect_before_and_during_profile_transition(self):
        self.load_recorded_headset()
        with patch('audio_devices.subprocess.run') as run:
            # Reconnect before switching, then a brief gap as HFP appears.
            run.side_effect = [SimpleNamespace(returncode=0, stdout=value) for value in
                ['b false', 'b true', 'b false', 'b true', 'b true', 'b true']]
            self.assertEqual(self.devices.prepare(timeout=.5), self.mic['name'])
        self.assertAlmostEqual(self.now, .2)

    def test_recorded_already_handsfree_needs_no_profile_change(self):
        self.load_recorded_headset()
        self.card['active_profile'] = 'headset-head-unit-msbc'
        self.data['sources'] = [self.mic]
        with patch('audio_devices.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'b true'
            self.assertEqual(self.devices.prepare(), self.mic['name'])
        self.assertIsNone(self.devices.lease)
        self.assertFalse(any(c[0] == 'set-card-profile' for c in self.calls))

    def test_bluez_query_failure_never_trusts_stale_metadata(self):
        self.load_recorded_headset()
        with patch('audio_devices.subprocess.run') as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(AudioDeviceError, 'Cannot verify Bluetooth'):
                self.devices.prepare()
            self.devices.lease = (self.card['name'], 'a2dp-sink', 'headset-head-unit-msbc')
            with self.assertRaises(AudioDeviceError):
                self.devices.restore()
            self.assertIsNotNone(self.devices.lease)
        self.assertFalse(any(c[0] == 'set-card-profile' for c in self.calls))


if __name__ == '__main__':
    unittest.main()
