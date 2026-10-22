"""Pulse device selection. Enumeration never opens capture or changes profiles.

Call prepare() only on a user recording start. Release OBS audio sources before
restore(); it conservatively defers restoration while any card streams remain.
"""
import json
import os
import subprocess
import threading
import time
from audio_debug import emit, traced


class AudioDeviceError(RuntimeError):
    pass


class AudioStreamPending(AudioDeviceError):
    """The new OBS stream has not been published by the audio server yet."""


def pactl(*args):
    try:
        result = subprocess.run(['pactl', *args], capture_output=True, text=True, timeout=2)
        if result.returncode:
            raise AudioDeviceError(result.stderr.strip() or 'PulseAudio command failed.')
        return result.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioDeviceError(f'Cannot contact audio server: {exc}') from exc


def is_microphone(source):
    return (not source['name'].endswith('.monitor')
            and source.get('properties', {}).get('device.class') != 'monitor'
            and source.get('monitor_of_sink') in (None, 4294967295, '4294967295'))


def connected(device, trace=None):
    properties = device.get('properties', {})
    name = device.get('name', '')
    identity = {'card': name} if name.startswith('bluez_card.') else {'source': name}
    path = properties.get('api.bluez5.path')
    if path:
        # PipeWire 1.0.3 can export the initial connection=disconnected and
        # bluez5.profile=off on live cards AND their nodes. Query the owner of
        # the connection, not those inherited snapshot properties.
        try:
            result = subprocess.run(['busctl', '--system', '--timeout=1',
                'get-property', 'org.bluez', path, 'org.bluez.Device1', 'Connected'],
                capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired) as exc:
            if trace:
                trace.event('connection.failed', level='warning', **identity,
                            exception_type=type(exc).__name__, connection_signal='org.bluez.Device1.Connected')
            raise AudioDeviceError(f'Cannot verify Bluetooth headset connection: {exc}') from exc
        if result.returncode or result.stdout.strip() not in ('b true', 'b false'):
            if trace:
                trace.event('connection.failed', level='warning', **identity,
                            exception_type='AudioDeviceError', reason='invalid_bluez_response')
            raise AudioDeviceError('Cannot verify Bluetooth headset connection. Reconnect it or choose another microphone.')
        live = result.stdout.strip() == 'b true'
        if trace:
            trace.event('connection.checked', every=5,
                        **identity, connected=live,
                        connection_signal='org.bluez.Device1.Connected',
                        stale_connection=properties.get('api.bluez5.connection'))
        return live
    live = properties.get('api.bluez5.connection') != 'disconnected'
    if trace:
        trace.event('connection.checked', every=5, **identity,
                    connected=live, connection_signal='pulse_property',
                    stale_connection=properties.get('api.bluez5.connection'))
    return live


def on_card(device, card):
    # PipeWire device.id is NOT pactl's card index. device.name is inherited by
    # nodes and wins over reused indices; native PulseAudio exposes a card index.
    name = device.get('properties', {}).get('device.name')
    if name:
        return name == card['name']
    return device.get('card') is not None and str(device['card']) == str(card['index'])


def handsfree_profile(card):
    candidates = []
    for name, profile in card.get('profiles', {}).items():
        if not name.startswith(('headset-head-unit', 'handsfree_head_unit')):
            continue
        if profile.get('available') in (False, 'no') or not profile.get('sources', 0):
            continue
        quality = 4 if 'lc3' in name else 3 if 'msbc' in name else 1 if 'cvsd' in name else 2
        candidates.append((quality, profile.get('priority', 0), name))
    return max(candidates)[2] if candidates else None


class AudioDevices:
    def __init__(self, command=pactl, clock=time.monotonic, sleep=time.sleep):
        self.command, self.clock, self.sleep = command, clock, sleep
        self.lease = None
        self.audio_trace = None
        self._lease_trace = None
        self.source_label = None
        self._capture_lock = threading.RLock()
        self._capture_owner = None

    def hold_capture(self):
        """Fence deferred restores before preparing a new capture session."""
        with self._capture_lock:
            self._capture_owner = object()
            return self._capture_owner

    def release_capture(self, owner):
        with self._capture_lock:
            if owner is self._capture_owner:
                self._capture_owner = None

    def verify_stream(self, source, media_name, stream_index=None, pid=None):
        """Verify the server's attachment, never OBS's requested device setting."""
        pid = os.getpid() if pid is None else pid
        streams = [s for s in self.read('source-outputs')
                   if str(s.get('properties', {}).get('application.process.id')) == str(pid)
                   and s.get('properties', {}).get('application.name') in ('OBS', 'OBS Studio', 'RecIt')
                   and s.get('properties', {}).get('media.name') == media_name]
        if not streams and stream_index is None:
            raise AudioStreamPending('Cannot verify RecIt microphone stream. Retry the microphone check.')
        if len(streams) != 1:
            emit(self, 'route.rejected', level='warning', requested_source=source,
                 reason='missing_or_ambiguous_stream', exception_type='AudioDeviceError')
            raise AudioDeviceError('Cannot verify RecIt microphone stream. Retry the microphone check.')
        stream = streams[0]
        actual = next((s for s in self.read('sources')
                       if str(s['index']) == str(stream.get('source'))), None)
        if (not actual or actual['name'] != source or not is_microphone(actual)
                or (stream_index is not None and str(stream['index']) != str(stream_index))):
            name = actual['name'] if actual else 'unavailable source'
            emit(self, 'route.mismatch', level='warning', requested_source=source, actual_source=name,
                 stream_index=stream.get('index'), reason='source_or_stream_changed',
                 exception_type='AudioDeviceError')
            raise AudioDeviceError(f'Microphone stream changed: requested {source}, attached to {name}. '
                                   'Choose the microphone and retry.')
        self.resolve(source)
        emit(self, 'route.verified', every=5, requested_source=source, actual_source=actual['name'],
             stream_index=stream['index'])
        return stream['index']

    def read(self, kind):
        try:
            return json.loads(self.command('-f', 'json', *(['info'] if kind == 'info' else ['list', kind])))
        except (ValueError, TypeError) as exc:
            raise AudioDeviceError('Audio server returned invalid device information.') from exc

    def microphones(self):
        default = self.read('info').get('default_source_name')
        return [(s.get('description', s['name']) + (' (system default)' if s['name'] == default else ''), s['name'])
                for s in self.read('sources') if is_microphone(s) and connected(s)]

    @traced('resolve', every=5)
    def resolve(self, selection='default'):
        if not selection:
            return None
        name = self.read('info').get('default_source_name') if selection == 'default' else selection
        source = next((s for s in self.read('sources') if s['name'] == name and is_microphone(s)), None)
        if not source or not connected(source, self.audio_trace):
            emit(self, 'source.rejected', level='warning', source=name, reason='missing_or_disconnected')
            raise AudioDeviceError('Selected microphone is unavailable. Reconnect it or choose another microphone.')
        self.source_label = (source.get('properties', {}).get('device.alias')
            or source.get('properties', {}).get('device.description')
            or source.get('description') or name)
        emit(self, 'source.resolved', every=5, source=name, label=self.source_label,
             card=source.get('properties', {}).get('device.name', source.get('card')),
             muted=source.get('mute'),
             gain=','.join(str(v.get('value')) for v in source.get('volume', {}).values()),
             sample_specification=source.get('sample_specification'), obs_rate=48000)
        if source.get('mute') is True:
            emit(self, 'source.rejected', level='warning', reason='muted', source=name)
            raise AudioDeviceError('Selected microphone is muted. Unmute it in system sound settings and try again.')
        volumes = [v.get('value') for v in source.get('volume', {}).values()]
        if volumes and all(v == 0 for v in volumes):
            emit(self, 'source.rejected', level='warning', reason='zero_gain', source=name)
            raise AudioDeviceError('Selected microphone volume is zero. Raise its input volume in system sound settings and try again.')
        return name

    @traced('prepare')
    def prepare(self, selection='default', auto_headset=True, timeout=4):
        """Return an exact OBS device_id, never the OBS default sentinel.

        Explicit microphone choices win. Default follows the system, except an
        enabled headset preference uses the current Bluetooth output's mic.
        """
        emit(self, 'selection.chosen', selection=selection, auto_headset=auto_headset)
        if not selection:
            return None
        if selection != 'default' or not auto_headset:
            return self.resolve(selection)
        deadline = self.clock() + timeout
        while True:
            info = self.read('info')
            sink = next((s for s in self.read('sinks') if s['name'] == info.get('default_sink_name')), None)
            cards = self.read('cards')
            card = next((c for c in cards if sink and on_card(sink, c)
                         and c['name'].startswith('bluez_card.')), None)
            bluetooth = sink and (sink['name'].startswith(('bluez_', 'bluez.'))
                or sink.get('properties', {}).get('device.api') == 'bluez5'
                or sink.get('properties', {}).get('device.name', '').startswith('bluez_card.'))
            if sink and (card or not bluetooth):
                break
            if self.clock() >= deadline:
                emit(self, 'prepare.timeout', level='warning', phase='default_output', exception_type='TimeoutError')
                raise AudioDeviceError('Default output is unavailable. Wait for your audio device to reconnect and try again.')
            self.sleep(.1)
        if card is None:
            return self.resolve(selection)
        while not connected(card, self.audio_trace):
            if self.clock() >= deadline:
                emit(self, 'prepare.timeout', level='warning', phase='connection', exception_type='TimeoutError')
                raise AudioDeviceError('Bluetooth headset is disconnected. Reconnect it or choose another microphone.')
            self.sleep(.1)
            card = next((c for c in self.read('cards') if c['name'] == card['name']), None)
            if card is None:
                raise AudioDeviceError('Bluetooth headset disconnected while preparing its microphone.')
        profile = handsfree_profile(card)
        if profile is None:
            raise AudioDeviceError('Bluetooth output has no available hands-free microphone. Choose another microphone.')
        if self.lease and self.lease[0] != card['name']:
            raise AudioDeviceError('Previous headset profile still needs restoration. Choose a microphone explicitly.')
        emit(self, 'profile.selected', card=card['name'], prior_profile=card.get('active_profile'),
             target_profile=profile, changed=card.get('active_profile') != profile)
        if card.get('active_profile') != profile:
            if self.lease:
                raise AudioDeviceError('Headset profile changed outside RecIt. Choose a microphone again.')
            # Retain ownership even on a timeout: the server may apply it late.
            self.lease = (card['name'], card.get('active_profile'), profile)
            self._lease_trace = self.audio_trace
            emit(self, 'profile.requested', card=card['name'], target_profile=profile)
            try:
                self.command('set-card-profile', card['name'], profile)
            except Exception as exc:
                emit(self, 'profile.failed', level='warning', card=card['name'],
                     target_profile=profile, exception_type=type(exc).__name__)
                raise
        while True:
            current = next((c for c in self.read('cards') if c['name'] == card['name']), None)
            if not current:
                raise AudioDeviceError('Bluetooth headset disconnected while preparing its microphone.')
            sources = [s for s in self.read('sources') if is_microphone(s) and on_card(s, current) and connected(s, self.audio_trace)] if connected(current, self.audio_trace) else []
            if current.get('active_profile') == profile and sources:
                emit(self, 'profile.ready', card=card['name'], target_profile=profile)
                source = max(sources, key=lambda s: int(s.get('properties', {}).get('priority.session', 0)))['name']
                resolved = self.resolve(source)
                self.source_label = (current.get('properties', {}).get('device.alias')
                    or current.get('properties', {}).get('device.description') or self.source_label)
                return resolved
            if self.clock() >= deadline:
                emit(self, 'prepare.timeout', level='warning', phase='profile_source', exception_type='TimeoutError')
                raise AudioDeviceError('Headset microphone did not become available. Reconnect it or select another microphone.')
            self.sleep(.1)

    def restore(self):
        with self._capture_lock:
            # A later capture can begin before a deferred profile restore.
            # Keep restoration evidence with the session that changed it.
            trace = self.audio_trace
            if self.lease and self._lease_trace is not None:
                self.audio_trace = self._lease_trace
            try:
                return self._restore_traced()
            finally:
                self.audio_trace = trace

    @traced('restore', every=5)
    def _restore_traced(self):
        if self._capture_owner is not None:
            emit(self, 'restore.deferred', every=5, reason='capture_owned')
            return False
        return self._restore_idle()

    def _restore_idle(self):
        """After releasing capture, restore only a profile still owned by us.

        Return False when streams still use the card; retry at a later idle
        boundary. Failure to inspect streams raises, leaving the lease intact.
        """
        if not self.lease:
            return True
        name, previous, selected = self.lease
        card = next((c for c in self.read('cards') if c['name'] == name), None)
        if not card or not connected(card, self.audio_trace) or card.get('active_profile') != selected:
            emit(self, 'restore.skipped', card=name, reason='missing_disconnected_or_external_change',
                 prior_profile=selected, target_profile=previous)
            self.lease = None
            return True
        sources = {str(s['index']) for s in self.read('sources') if on_card(s, card)}
        sinks = {str(s['index']) for s in self.read('sinks') if on_card(s, card)}
        if (any(str(s.get('source')) in sources for s in self.read('source-outputs'))
                or any(str(s.get('sink')) in sinks for s in self.read('sink-inputs'))):
            emit(self, 'restore.deferred', every=5, card=name, reason='active_streams',
                 prior_profile=selected, target_profile=previous)
            return False
        if previous:
            self.command('set-card-profile', name, previous)
            emit(self, 'restore.requested', card=name, prior_profile=selected,
                 target_profile=previous, changed=previous != selected)
        self.lease = None
        return True
