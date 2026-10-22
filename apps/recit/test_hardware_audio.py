"""Explicit, audio-only hardware diagnostic. Discovery never opens a device.

Run with a connected headset and ambient speech/noise, after closing RecIt:
  RECIT_TEST_XVFB=/path/to/Xvfb python test_hardware_audio.py --microphone-hardware
Optional --source EXACT_PULSE_NAME overrides production Default preparation.
Samples stay in a private /tmp/recit-hardware-audio-* directory. No playback,
upload, camera, desktop capture, mute/gain changes or service changes occur.
Nonzero ambient samples prove transport, not intelligibility or audio quality.
"""
import array
import ctypes as C
import json
import math
import os
from pathlib import Path
import select
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import wave


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, timeout=15, **kwargs)


def pulse(kind):
    return json.loads(command(['pactl', '-f', 'json', 'list', kind]).stdout)


def stop_process(process, grace=3):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def json_safe(value):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return None if isinstance(value, float) and not math.isfinite(value) else value


def preflight():
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().split(b'\0')
        except (OSError, PermissionError):
            continue
        if any(arg.endswith(b'/recit/app.py') for arg in args):
            raise RuntimeError('Close RecIt, including its tray process, before testing')
    if pulse('source-outputs'):
        raise RuntimeError('An audio capture stream is active; close it before testing')


def levels(path):
    with wave.open(str(path), 'rb') as wav:
        rate, count, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        assert width == 2
        pcm = array.array('h', wav.readframes(wav.getnframes()))
    if sys.byteorder != 'little':
        pcm.byteswap()
    channels = []
    for index in range(count):
        values = pcm[index::count]
        n = len(values)
        rms = math.sqrt(sum(float(v) ** 2 for v in values) / n) / 32768 if n else 0
        peak = max(map(abs, values), default=0) / 32768
        channels.append(dict(samples=n, nonzero_ratio=sum(v != 0 for v in values) / n if n else 0,
                             rms=rms, rms_dbfs=20 * math.log10(rms) if rms else None,
                             peak=peak, clipped_samples=sum(abs(v) >= 32767 for v in values)))
    return dict(duration_s=len(pcm) / count / rate, rate=rate, channels=channels)


def sample_evidence(sample):
    """Inspect original float planes before the check's 16-bit WAV rounding."""
    channels = [array.array('f'), array.array('f')]
    for block in sample.blocks:
        for channel, data in zip(channels, block):
            channel.frombytes(data)
    evidence = []
    for values in channels:
        n = len(values)
        rms = math.sqrt(sum(float(v) ** 2 for v in values) / n) if n else 0
        evidence.append(dict(samples=n, nonzero_ratio=sum(v != 0 for v in values) / n if n else 0,
                             rms=rms, peak=max(map(abs, values), default=0)))
    return evidence


def native(directory, source, attempt):
    """Pulse PCM with no filters, tied to an exact source, never a default alias."""
    from audio_devices import is_microphone
    metadata = next(s for s in pulse('sources') if s['name'] == source)
    assert is_microphone(metadata)
    path = directory / f'native-{attempt}.wav'
    # Keep source rate/channel count; ffmpeg's Pulse interface performs no DSP.
    spec = metadata['sample_specification'].split()
    rate, channels = int(spec[2][:-2]), int(spec[1][:-2])
    log = directory / f'native-{attempt}.log'
    with log.open('wb') as output:
        process = subprocess.Popen(['ffmpeg', '-v', 'warning', '-nostdin', '-f', 'pulse',
            '-sample_rate', str(rate), '-channels', str(channels), '-i', source,
            '-t', '5', '-c:a', 'pcm_s16le', str(path)], stdout=output, stderr=output)
        stream = None
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and process.poll() is None:
                streams = [s for s in pulse('source-outputs') if str(s.get('properties', {}).get(
                    'application.process.id')) == str(process.pid)]
                if streams:
                    assert len(streams) == 1
                    stream = streams[0]
                    actual = next(s for s in pulse('sources') if s['index'] == stream['source'])
                    assert actual['name'] == source, 'Native stream attached to another microphone'
                    break
                time.sleep(.1)
            if stream is None:
                raise RuntimeError('Native stream attachment could not be verified')
            process.wait(timeout=12)
            if process.returncode:
                raise RuntimeError(f'Native capture failed; see {log}')
        finally:
            stop_process(process)
    return dict(file=str(path), source=metadata, stream=stream, levels=levels(path))


def obs_capture(directory, source, report):
    from audio_check import AudioSample
    from audio_debug import AudioTrace
    from audio_devices import AudioDevices
    from audio_telemetry import MicrophoneTelemetry
    from engine import Engine, P

    class DiagnosticSample(AudioSample):
        def __init__(self, obs, source):
            self.started = time.monotonic()
            self.first_packet_s = self.first_nonzero_s = None
            self.muted_packets = self.packet_count = 0
            super().__init__(obs, source)

        def receive(self, param, capture, data, muted):
            elapsed = time.monotonic() - self.started
            self.packet_count += 1
            self.muted_packets += int(muted)
            if self.first_packet_s is None:
                self.first_packet_s = elapsed
            super().receive(param, capture, data, muted)
            if self.first_nonzero_s is None and self.blocks:
                if any(any(array.array('f', plane)) for plane in self.blocks[-1]):
                    self.first_nonzero_s = elapsed

    class AudioOnlyEngine(Engine):
        def _load_modules(self):
            for name in ('linux-pulseaudio', 'obs-filters', 'obs-ffmpeg', 'obs-outputs', 'obs-x264'):
                module = P()
                code = self._obs.obs_open_module(C.byref(module),
                    f'/usr/lib/x86_64-linux-gnu/obs-plugins/{name}.so'.encode(),
                    f'/usr/share/obs/obs-plugins/{name}'.encode())
                if code or not self._obs.obs_init_module(module):
                    raise RuntimeError(f'Required audio test plugin unavailable: {name}')
            self._obs.obs_post_load_modules()

        def _source(self, kind, name, settings):
            if kind not in {'pulse_input_capture', 'noise_suppress_filter_v2',
                            'noise_suppress_filter', 'limiter_filter'}:
                raise AssertionError(f'Forbidden hardware test source: {kind}')
            if kind == 'pulse_input_capture' and settings.get('device_id') != source:
                raise AssertionError('Hardware test cannot fall back to another input')
            return super()._source(kind, name, settings)

    devices = AudioDevices()
    devices.audio_trace = AudioTrace('hardware')
    engine = None
    sample = None
    owner = devices.hold_capture()
    try:
        prepared = devices.prepare(report['selection'])
        assert prepared == source, 'Default preparation changed the selected physical microphone'
        report['prepared_source'] = prepared
        report['profile_lease'] = devices.lease
        engine = AudioOnlyEngine(0, 320, 180, 30)
        engine.audio_trace = devices.audio_trace
        engine.encoders.discard('ffmpeg_vaapi')
        # Observe the same live OBS source before and after production filters.
        engine.begin_audio_monitor(prepared, processing=False)
        report['obs_streams_initial'] = pulse('source-outputs')
        engine.verify_audio_route(timeout=2)
        report['obs_streams'] = pulse('source-outputs')
        capture = engine._microphone_capture
        for processed in (False, True):
            name = 'filtered' if processed else 'unfiltered'
            if processed:
                engine._release_microphone_meter()
                engine._microphone_filters(capture, enabled=True)
                engine._microphone_processing = True
                engine._microphone_meter = MicrophoneTelemetry(engine._obs, capture, prepared)
            sample = DiagnosticSample(engine._obs, capture)
            timeline = []
            for _ in range(10):
                time.sleep(.5)
                engine.verify_audio_route()
                timeline.append(dict(elapsed_s=(_ + 1) * .5, **engine.audio_status()))
            sample.detach()
            path = directory / f'obs-{name}.wav'
            callbacks = dict(packets=sample.packet_count, muted_packets=sample.muted_packets,
                             first_packet_s=sample.first_packet_s, first_nonzero_s=sample.first_nonzero_s,
                             float_channels=sample_evidence(sample))
            sample.save(path)
            sample = None
            report[name] = dict(file=str(path), levels=levels(path), timeline=timeline, callbacks=callbacks)
        report['warnings'] = engine.warnings
        report['filter_backend'] = engine._microphone_noise_backend()
        # A blank scene is synthetic black. No desktop/camera module is loaded.
        engine._scene = engine._obs.obs_scene_create(b'Audio diagnostic black')
        engine._obs.obs_set_output_source(0, engine._obs.obs_scene_get_source(engine._scene))
        engine._configured = True
        engine.audio_expected = True
        output = directory / 'recit.mkv'
        try:
            engine.start(output)  # Preserve production sample-readiness guard.
        except RuntimeError as exc:
            report['encoded_blocked'] = str(exc)
        else:
            time.sleep(5)
            engine.verify_audio_route()
            engine.stop()
            decoded = directory / 'recit-decoded.wav'
            command(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-map', '0:a:0',
                     '-c:a', 'pcm_s16le', str(decoded)])
            report['encoded'] = dict(file=str(output), levels=levels(decoded), probe=json.loads(command(
                ['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)]).stdout))
    finally:
        try:
            try:
                if sample:
                    sample.detach()
            finally:
                if engine:
                    try:
                        if engine.recording:
                            engine.stop()
                    finally:
                        engine.close()
        finally:
            devices.release_capture(owner)
            report['restored'] = devices.restore()


def worker(directory, selection):
    private_display = os.environ.get('RECIT_HARDWARE_PRIVATE_DISPLAY')
    if not private_display or private_display != os.environ.get('DISPLAY'):
        raise RuntimeError('Hardware worker requires a private Xvfb')
    # Parent timeout first requests orderly teardown, including profile restore.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit('Hardware diagnostic timed out'))
    from audio_devices import AudioDevices, is_microphone
    preflight()
    report = dict(selection=selection, started_unix=time.time(), native=[])
    try:
        source = AudioDevices().resolve(selection)
        metadata = next(s for s in pulse('sources') if s['name'] == source)
        assert is_microphone(metadata) and source.startswith('bluez_input.'), 'Expected exact earbuds input'
        report['source'] = source
        report['initial_cards'] = pulse('cards')
        for attempt in (1, 2):
            baseline = native(directory, source, attempt)
            report['native'].append(baseline)
            if any(c['nonzero_ratio'] for c in baseline['levels']['channels']):
                break
        obs_capture(directory, source, report)
        native_signal = any(c['rms'] > .0001 for b in report['native'] for c in b['levels']['channels'])
        if not native_signal:
            report['verdict'] = 'inconclusive: native baseline has zero or very low signal; OBS processing not blamed'
        elif not any(c['nonzero_ratio'] for c in report['unfiltered']['levels']['channels']):
            report['verdict'] = 'failure: native signal available but unfiltered OBS is zero'
        elif not any(c['nonzero_ratio'] for c in report['filtered']['levels']['channels']):
            report['verdict'] = 'inconclusive: filtered signal zero; speech stimulus needed to distinguish suppression'
        elif 'encoded' not in report or not all(c['nonzero_ratio'] for c in report['encoded']['levels']['channels']):
            report['verdict'] = 'failure: filtered OBS samples did not survive production AAC'
        else:
            report['verdict'] = 'transport passed; ambient signal does not prove speech quality'
    except BaseException as exc:
        report['error'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        report['final_cards'] = pulse('cards')
        report['remaining_capture_streams'] = pulse('source-outputs')
        (directory / 'report.json').write_text(json.dumps(json_safe(report), indent=2, allow_nan=False))
    print(report['verdict'], flush=True)


class HarnessSafetyTests(unittest.TestCase):
    def test_worker_without_private_display_cannot_reach_capture(self):
        with patch.dict(os.environ, {}, clear=True), patch(__name__ + '.preflight') as check:
            with self.assertRaisesRegex(RuntimeError, 'private Xvfb'):
                worker(Path('/unused'), 'default')
            check.assert_not_called()

    def test_numeric_report_distinguishes_low_signal_from_exact_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'low.wav'
            with wave.open(str(path), 'wb') as output:
                output.setparams((2, 2, 16000, 0, 'NONE', 'not compressed'))
                output.writeframes(array.array('h', [0, 1] * 160).tobytes())
            result = levels(path)
        self.assertEqual(result['duration_s'], .01)
        self.assertEqual(result['channels'][0]['nonzero_ratio'], 0)
        self.assertEqual(result['channels'][1]['nonzero_ratio'], 1)
        self.assertLess(result['channels'][1]['rms'], .0001)
        floats = sample_evidence(type('Sample', (), {'blocks': [[
            array.array('f', [0]).tobytes(), array.array('f', [1e-8]).tobytes()]]})())
        self.assertEqual(floats[1]['nonzero_ratio'], 1)
        self.assertGreater(floats[1]['rms'], 0)
        self.assertEqual(json.dumps(json_safe({'level': -math.inf}), allow_nan=False), '{"level": null}')


class HardwareAudioTests(unittest.TestCase):
    @unittest.skipUnless('--microphone-hardware' in sys.argv or os.environ.get('RECIT_TEST_MIC_HARDWARE') == '1',
                         'opt-in microphone hardware diagnostic; never records during ordinary discovery')
    def test_exact_headset_native_and_recit(self):
        preflight()
        xvfb = os.environ.get('RECIT_TEST_XVFB') or shutil.which('Xvfb')
        if not xvfb:
            self.skipTest('Set RECIT_TEST_XVFB to an Xvfb executable')
        directory = Path(tempfile.mkdtemp(prefix='recit-hardware-audio-'))
        os.chmod(directory, 0o700)
        selection = sys.argv[sys.argv.index('--source') + 1] if '--source' in sys.argv else 'default'
        env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', QT_QPA_PLATFORM='offscreen')
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'SESSION_MANAGER'):
            env.pop(key, None)
        read_fd, write_fd = os.pipe()
        server = None
        child = None
        try:
            with (directory / 'xvfb.log').open('w') as log:
                server = subprocess.Popen([xvfb, '-displayfd', str(write_fd), '-screen', '0',
                    '640x480x24', '-nolisten', 'tcp', '-ac'], env=env, pass_fds=(write_fd,),
                    stdout=log, stderr=log)
                os.close(write_fd)
                write_fd = None
                self.assertTrue(select.select([read_fd], [], [], 10)[0], 'Xvfb startup timed out')
                display = os.read(read_fd, 32).decode().strip()
                self.assertTrue(display.isdigit(), 'Xvfb did not allocate a private display')
                env.update(DISPLAY=':' + display, RECIT_HARDWARE_PRIVATE_DISPLAY=':' + display)
                with (directory / 'obs.log').open('w') as output:
                    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                        '--hardware-worker', str(directory), selection], env=env, stdout=output,
                        stderr=output)
                    try:
                        child.wait(timeout=75)
                    except subprocess.TimeoutExpired:
                        stop_process(child, grace=15)
                        self.fail(f'Hardware diagnostic timed out; see {directory}/obs.log')
                print(f'Private audio diagnostic artifacts: {directory}', flush=True)
                self.assertEqual(child.returncode, 0, f'See {directory}/obs.log')
                report = json.loads((directory / 'report.json').read_text())
                self.assertFalse(report['remaining_capture_streams'], 'Capture stream leaked')
                self.assertFalse(report['verdict'].startswith('failure:'), report['verdict'])
                if report['verdict'].startswith('inconclusive:'):
                    self.skipTest(report['verdict'])
        finally:
            stop_process(child, grace=15)
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
            stop_process(server)


if __name__ == '__main__':
    os.umask(0o077)
    if '--hardware-worker' in sys.argv:
        worker(Path(sys.argv[-2]), sys.argv[-1])
    else:
        args = sys.argv[1:]
        if '--source' in args:
            index = args.index('--source')
            del args[index:index + 2]
        unittest.main(argv=[sys.argv[0]] + [a for a in args if a != '--microphone-hardware'], verbosity=2)
