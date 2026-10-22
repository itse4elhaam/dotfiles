"""Opt-in sample-to-AAC integration, with no hardware capture or playback.

Run: python apps/recit/test_native_audio.py --native-audio
Requires OBS 27 plugins, FFmpeg and Xvfb. Set RECIT_TEST_XVFB to an existing
Xvfb executable when it is not on PATH. Discovery skips this expensive test.
A private Xvfb and child process isolate libobs from the user's DISPLAY.
This exercises resampling, production microphone filters, mixer 0 and MKV/AAC,
but cannot establish PulseAudio, Bluetooth/HFP or real microphone readiness.
"""
import array
import ctypes as C
import json
import math
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import wave


BURSTS = ((0.0, .65), (1.8, 2.5), (3.4, 4.2))
DURATION = 5.0


def make_fixture(path):
    """16 kHz mono voiced harmonics, with ramps and two unmistakable pauses."""
    samples = array.array('h')
    for i in range(int(16000 * DURATION)):
        t = i / 16000
        value = 0.0
        for start, end in BURSTS:
            if start <= t < end:
                ramp = min(1, (t - start) / .015, (end - t) / .015)
                # Harmonics through the voice band, rather than a steady sine
                # that RNNoise can legitimately classify as background noise.
                phase = 2 * math.pi * (135 * t + 3 * math.sin(2 * math.pi * 2 * t))
                value = ramp * .65 * sum(math.sin(k * phase) / k for k in range(1, 24)) / 2
                break
        samples.append(round(value * 32767))
    if sys.byteorder != 'little':
        samples.byteswap()
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(samples.tobytes())


def record_fixture(directory):
    # Only the parent can grant a display, after spawning its private Xvfb.
    if os.environ.get('RECIT_NATIVE_PRIVATE_DISPLAY') != os.environ.get('DISPLAY'):
        raise RuntimeError('Native child requires its isolated Xvfb display')
    from engine import Engine, P, S, U, _bind

    class FixtureEngine(Engine):
        def _load_modules(self):
            # Never even load desktop, camera, Pulse input/output or monitoring
            # modules. Loading codecs/filters does not open capture devices.
            for name in ('obs-filters', 'obs-ffmpeg', 'obs-outputs', 'obs-x264'):
                module = P()
                code = self._obs.obs_open_module(C.byref(module),
                    f'/usr/lib/x86_64-linux-gnu/obs-plugins/{name}.so'.encode(),
                    f'/usr/share/obs/obs-plugins/{name}'.encode())
                if code or not self._obs.obs_init_module(module):
                    raise RuntimeError(f'Required native plugin {name} unavailable ({code})')
            self._obs.obs_post_load_modules()

        def _source(self, kind, name, settings):
            if kind not in {'ffmpeg_source', 'noise_suppress_filter_v2',
                            'noise_suppress_filter', 'limiter_filter'}:
                raise AssertionError(f'Forbidden source in synthetic test: {kind}')
            return super()._source(kind, name, settings)

    directory = Path(directory)
    fixture, output = directory / 'voiced.wav', directory / 'encoded.mkv'
    make_fixture(fixture)
    engine = FixtureEngine(0, 320, 180, 30)
    try:
        o = engine._obs
        backend = engine._microphone_noise_backend()
        if not backend or backend[1] != 'rnnoise':
            raise RuntimeError(f'RNNoise required for this test; found {backend!r}')
        engine.encoders.discard('ffmpeg_vaapi')  # CPU only, no render device.
        source = engine._source('ffmpeg_source', 'Synthetic voiced WAV', {
            'is_local_file': True, 'local_file': str(fixture), 'looping': False,
            'restart_on_activate': False, 'close_when_inactive': False,
            'clear_on_media_end': True, 'hw_decode': False})
        engine._sources.append(source)
        stop = _bind(o, 'obs_source_media_stop', None, P)
        restart = _bind(o, 'obs_source_media_restart', None, P)
        stop(source)
        engine._microphone_filters(source, enabled=True)
        # Fail if production falls back or silently loses either native filter.
        if any('Microphone processing:' in warning for warning in engine.warnings):
            raise AssertionError(engine.warnings)
        find_filter = _bind(o, 'obs_source_get_filter_by_name', P, P, S)
        for name in (b'RecIt microphone noise suppression', b'RecIt microphone peak limiter'):
            filt = find_filter(source, name)
            if not filt:
                raise AssertionError(f'Missing production filter: {name!r}')
            o.obs_source_release(filt)
        _bind(o, 'obs_source_set_audio_mixers', None, P, U)(source, 1)
        engine._scene = o.obs_scene_create(b'Synthetic audio test')
        if not engine._scene or not o.obs_scene_add(engine._scene, source):
            raise AssertionError('Could not attach file source to synthetic scene')
        o.obs_set_output_source(0, o.obs_scene_get_source(engine._scene))
        engine._configured = True
        engine.start(output)
        time.sleep(.2)  # Let the encoder start; retain a bounded known lead-in.
        restart(source)
        time.sleep(DURATION + .4)  # File source paces samples against OBS's clock.
        engine.stop()
        if engine.errors:
            raise AssertionError(engine.errors)
    finally:
        engine.close()
    return output


def analyze(output):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_name,sample_rate,channels:format=duration',
        '-of', 'json', str(output)], capture_output=True, text=True, check=True, timeout=10)
    info = json.loads(probe.stdout)
    stream = info['streams'][0]
    assert stream['codec_name'] == 'aac', stream
    assert stream['sample_rate'] == '48000' and stream['channels'] == 2, stream
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output),
        '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', '-'],
        capture_output=True, check=True, timeout=15)
    pcm = array.array('f')
    pcm.frombytes(decoded.stdout)
    if sys.byteorder != 'little':
        pcm.byteswap()
    channels = (pcm[0::2], pcm[1::2])
    duration = len(channels[0]) / 48000
    assert 5.0 <= duration <= 6.5, f'Unexpected decoded duration {duration}'
    assert 5.0 <= float(info['format']['duration']) <= 6.5, info
    evidence = []
    for channel in channels:
        def rms(start, end):
            window = channel[int(start * 48000):int(end * 48000)]
            assert window, (start, end, duration)
            return math.sqrt(sum(x*x for x in window) / len(window))
        # Use 20 ms windows to detect onset without mistaking AAC's tiny
        # pre-echo for signal. A missing first burst must fail independently.
        blocks = [rms(i / 50, (i + 1) / 50) for i in range(int(duration * 50))]
        peak = max(blocks)
        assert peak > .003, f'Silent/nearly silent channel: peak RMS {peak}'
        onset = next(i / 50 for i, value in enumerate(blocks) if value > peak * .15)
        assert .05 <= onset <= .55, f'Lost/delayed initial burst: {onset}s'
        bursts = [rms(onset + start + .15, onset + end - .12) for start, end in BURSTS]
        pauses = [rms(onset + .95, onset + 1.5), rms(onset + 2.8, onset + 3.1)]
        assert min(bursts) > .003, f'Lost a voiced burst: {bursts}'
        assert max(pauses) < min(bursts) * .15, f'Pause/timing mismatch: {bursts}, {pauses}'
        evidence.append({'onset_s': onset, 'burst_rms': bursts, 'pause_rms': pauses})
    print('NATIVE AUDIO EVIDENCE ' + json.dumps({'codec': stream, 'decoded_seconds': duration,
        'input': '16000 Hz mono synthetic WAV', 'filters': 'RNNoise -> limiter',
        'mixer': 0, 'channels': evidence}), flush=True)


class NativeAudioTests(unittest.TestCase):
    @unittest.skipUnless('--native-audio' in sys.argv,
        'opt-in synthetic native test: run test_native_audio.py --native-audio; requires Xvfb, OBS 27 and FFmpeg')
    def test_synthetic_samples_survive_production_filters_and_aac(self):
        xvfb = os.environ.get('RECIT_TEST_XVFB') or shutil.which('Xvfb')
        for name, executable in (('Xvfb (or RECIT_TEST_XVFB)', xvfb),
                                 ('ffmpeg', shutil.which('ffmpeg')), ('ffprobe', shutil.which('ffprobe'))):
            if not executable or not os.path.isfile(executable):
                self.skipTest(f'Native audio dependency unavailable: {name}')
        with tempfile.TemporaryDirectory(prefix='recit-native-audio-') as directory:
            env = dict(os.environ)
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'SESSION_MANAGER', 'DBUS_SESSION_BUS_ADDRESS'):
                env.pop(key, None)
            env.update(LIBGL_ALWAYS_SOFTWARE='1', QT_QPA_PLATFORM='offscreen',
                       PULSE_SERVER='unix:' + directory + '/no-pulse-server',
                       PULSE_CLIENTCONFIG=directory + '/pulse-client.conf',
                       XDG_RUNTIME_DIR=directory)
            Path(env['PULSE_CLIENTCONFIG']).write_text('autospawn = no\n')
            # -displayfd allocates a free server number, never reuses DISPLAY.
            read_fd, write_fd = os.pipe()
            try:
                with open(Path(directory) / 'xvfb.log', 'w+') as log:
                    server = subprocess.Popen([xvfb, '-displayfd', str(write_fd), '-screen', '0',
                        '640x480x24', '-nolisten', 'tcp', '-ac'], pass_fds=(write_fd,),
                        stdout=log, stderr=log, env=env)
                    os.close(write_fd)
                    write_fd = None
                    try:
                        if not select.select([read_fd], [], [], 10)[0]:
                            self.fail('Private Xvfb did not report a display within 10 seconds')
                        display = os.read(read_fd, 32).decode().strip()
                        if not display.isdigit():
                            log.seek(0)
                            self.fail('Private Xvfb failed: ' + log.read())
                        env.update(DISPLAY=':' + display, RECIT_NATIVE_PRIVATE_DISPLAY=':' + display)
                        child = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            '--native-worker', directory], env=env, capture_output=True,
                            text=True, timeout=45)
                        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
                        print(child.stdout, end='')
                    finally:
                        server.terminate()
                        try:
                            server.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait(timeout=5)
            finally:
                os.close(read_fd)
                if write_fd is not None:
                    os.close(write_fd)


if __name__ == '__main__':
    if '--native-worker' in sys.argv:
        analyze(record_fixture(sys.argv[-1]))
    else:
        unittest.main(argv=[arg for arg in sys.argv if arg != '--native-audio'], verbosity=2)
