"""Explicit microphone check. OBS supplies filtered samples; no second capture tool."""
from array import array
import ctypes as C
import math
from pathlib import Path
import sys
import tempfile
import time
import wave
from audio_debug import AudioTrace, emit

from PySide6.QtCore import QThread, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout


class AudioData(C.Structure):
    _fields_ = [('data', C.POINTER(C.c_ubyte) * 8), ('frames', C.c_uint32),
                ('timestamp', C.c_uint64)]


AudioCallback = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.POINTER(AudioData), C.c_bool)


class AudioSample:
    """Copy OBS 48 kHz stereo planar floats after filters, bounded to five seconds.

    OBS 27 source_output_audio_data signals these callbacks after filter_async_audio.
    Callback removal synchronizes with OBS's callback mutex before buffers are read.
    """
    def __init__(self, obs, source):
        self.obs, self.source = obs, source
        self.blocks = []
        self.frames = 0
        self.error = ''
        self.callback = AudioCallback(self.receive)
        for name in ('obs_source_add_audio_capture_callback', 'obs_source_remove_audio_capture_callback'):
            fn = getattr(obs, name)
            fn.restype = None
            fn.argtypes = [C.c_void_p, AudioCallback, C.c_void_p]
        obs.obs_source_add_audio_capture_callback(source, self.callback, None)

    def receive(self, _param, _source, data, muted):
        try:
            count = min(data.contents.frames, 240000 - self.frames)
            if count <= 0:
                return
            planes = []
            for channel in range(2):
                pointer = data.contents.data[channel]
                planes.append(bytes(count * 4) if muted or not pointer else C.string_at(pointer, count * 4))
            self.blocks.append(planes)
            self.frames += count
        except Exception:
            self.error = 'Could not read microphone samples. Retry the check.'

    def detach(self):
        if self.source is not None:
            self.obs.obs_source_remove_audio_capture_callback(self.source, self.callback, None)
            self.source = None

    def save(self, path):
        if self.error:
            raise RuntimeError(self.error)
        if not self.frames:
            raise RuntimeError('No microphone signal arrived. Check the input device and reconnect your headset, then retry.')
        pcm = array('h')
        peak = 0.0
        for left, right in self.blocks:
            channels = [array('f', left), array('f', right)]
            for pair in zip(*channels):
                for value in pair:
                    value = max(-1., min(1., value)) if math.isfinite(value) else 0.
                    peak = max(peak, abs(value))
                    pcm.append(round(value * 32767))
        if sys.byteorder != 'little':
            pcm.byteswap()
        with wave.open(str(path), 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(pcm.tobytes())
        self.blocks.clear()
        return peak


class CheckWorker(QThread):
    result = Signal(object, str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.audio_trace = getattr(parent, 'audio_trace', None)

    def run(self):
        started = time.monotonic()
        try:
            self.result.emit(self.action(), '')
        except Exception as exc:
            emit(self, 'check_worker.failed', level='warning', exception_type=type(exc).__name__,
                 duration_ms=round((time.monotonic() - started) * 1000))
            self.result.emit(None, str(exc))


class AudioCheck(QDialog):
    def __init__(self, engine, devices, selection, processing, device_label, parent=None):
        super().__init__(parent)
        self.engine, self.devices = engine, devices
        self.selection, self.processing = selection, processing
        self.worker = None
        self.capturing = False
        self.closing = False
        self.failed_capture = False
        self.sample = None
        self.capture_owner = None
        self.pending_finish = None
        self.temp = tempfile.TemporaryDirectory(prefix='recit-audio-check-')
        self.path = Path(self.temp.name) / 'microphone.wav'
        self.setWindowTitle('Quick audio check')
        self.setModal(True)
        self.resize(480, 280)
        layout = QVBoxLayout(self)
        title = QLabel('Quick audio check')
        title.setObjectName('title')
        layout.addWidget(title)
        self.device = QLabel(device_label)
        self.device.setWordWrap(True)
        layout.addWidget(self.device)
        self.status = QLabel('Record four seconds, then hear your microphone. The sample is temporary and stays out of Recordings.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.record = QPushButton('Record sample')
        self.play = QPushButton('Play sample')
        self.stop = QPushButton('Stop')
        self.done_button = QPushButton('Done')
        for button in (self.record, self.play, self.stop, self.done_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.record.clicked.connect(self.start_check)
        self.play.clicked.connect(self.prepare_playback)
        self.stop.clicked.connect(self.stop_check)
        self.done_button.clicked.connect(self.reject)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.playbackStateChanged.connect(lambda *_: self.update_buttons())
        self.player.errorOccurred.connect(lambda *_: self.status.setText('Could not play this sample. Check your playback device and retry.'))
        self.summary_timer = QTimer(self)
        self.summary_timer.setInterval(5000)
        self.summary_timer.timeout.connect(self.log_progress)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish_capture)
        self.route_timer = QTimer(self)
        self.route_timer.setInterval(200)
        self.route_timer.timeout.connect(self.verify_route)
        self.update_buttons()

    def update_buttons(self):
        working = self.worker is not None
        self.record.setEnabled(not working and not self.capturing and not self.failed_capture)
        self.play.setEnabled(not working and not self.capturing and self.path.is_file())
        self.stop.setEnabled(self.capturing or self.player.playbackState() == QMediaPlayer.PlayingState)

    def run_action(self, action, callback):
        worker = self.worker = CheckWorker(action, self)
        result = []
        worker.result.connect(lambda value, error: result.extend((value, error)))
        def finished():
            self.worker = None
            worker.deleteLater()
            callback(*result)
            if self.pending_finish is not None and self.worker is None:
                error, self.pending_finish = self.pending_finish, None
                self.finish_capture(error)
            self.update_buttons()
        worker.finished.connect(finished)
        worker.start()
        self.update_buttons()

    def clear_playback(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.path.unlink(missing_ok=True)

    def start_check(self):
        if self.worker or self.capturing or self.failed_capture:
            return
        self.clear_playback()
        if not self.selection:
            self.status.setText('Microphone is off. Choose a microphone before running the check.')
            return
        self.audio_trace = self.engine.audio_trace = self.devices.audio_trace = AudioTrace('check')
        emit(self, 'session.start', selection=self.selection, processing=self.processing)
        self.status.setText('Preparing microphone…')
        self.device.setText('Microphone: verifying actual capture source…')
        self.capture_owner = self.devices.hold_capture()
        def prepare():
            source = self.devices.prepare(self.selection)
            if not source:
                raise RuntimeError('No microphone is available. Choose an input device and retry.')
            self.sample = self.engine.begin_audio_check(source, self.processing)
            return source
        self.run_action(prepare, self.prepared)

    def prepared(self, source, error):
        if error or self.closing:
            self.finish_capture(error=error)
            return
        self.capturing = True
        self.record.setText('Retry')
        label = getattr(self.devices, 'source_label', None)
        self.device.setText(f'Microphone: {label if isinstance(label, str) and label else source}')
        self.device.setToolTip(source)
        emit(self, 'check.started', source=source)
        self.status.setText('Speak now. Recording four seconds…')
        self.summary_timer.start()
        self.log_progress()
        self.timer.start(4000)
        self.route_timer.start()

    def verify_route(self):
        if not self.capturing or self.worker:
            return
        def verified(source, error):
            if error:
                self.device.setText('Microphone: source verification failed')
                self.finish_capture(error=error)
            elif self.closing:
                self.finish_capture()
        self.run_action(self.engine.verify_audio_route, verified)

    def log_progress(self):
        if self.sample and self.capturing:
            emit(self, 'check.health', every=5, frames=self.sample.frames, obs_rate=48000)
            trace = getattr(self, 'audio_trace', None)
            if isinstance(trace, AudioTrace):
                trace.telemetry('check', self.engine.audio_status())

    def stop_check(self):
        self.player.stop()
        if self.capturing:
            self.finish_capture()
        self.update_buttons()

    def finish_capture(self, error=''):
        if self.worker:
            self.pending_finish = error
            return
        self.timer.stop()
        self.summary_timer.stop()
        self.route_timer.stop()
        self.capturing = False
        emit(self, 'check.stopped', reason='cancelled' if self.closing else 'finished')
        self.status.setText('Releasing microphone and restoring playback…')
        def finish():
            route_error = ''
            if self.sample and not error and not self.closing:
                try:
                    self.engine.verify_audio_route()
                except RuntimeError as exc:
                    route_error = str(exc)
            trace = getattr(self, 'audio_trace', None)
            if isinstance(trace, AudioTrace) and self.sample:
                trace.telemetry('check', self.engine.audio_status(), outcome='finished')
            self.engine.end_audio_check()
            self.devices.release_capture(self.capture_owner)
            self.capture_owner = None
            restored = self.devices.restore()
            peak, sample_error = None, route_error
            if self.sample and not error and not route_error and not self.closing:
                try:
                    peak = self.sample.save(self.path)
                    emit(self, 'check.validation', outcome='nonzero_audio' if peak >= .0001 else 'inaudible',
                         frames=self.sample.frames)
                except RuntimeError as exc:
                    emit(self, 'check.validation_failed', level='warning',
                         exception_type=type(exc).__name__, reason='sample_save_failed')
                    sample_error = str(exc)
            self.sample = None
            return restored, peak, sample_error
        def finished(result, failure):
            if failure:
                # Do not permit another capture after an uncertain teardown.
                self.failed_capture = True
                self.status.setText(f'Could not finish the check: {failure}. Close this check before trying again.')
                self.closing = False
                return
            self.failed_capture = False
            if self.closing:
                self.complete_close()
                return
            restored, peak, sample_error = result
            if error:
                self.device.setText('Microphone: source verification failed')
                self.status.setText(f'Could not prepare microphone: {error}')
            elif sample_error:
                self.device.setText('Microphone: sample not verified')
                self.status.setText(sample_error)
            elif peak is None or peak < .0001:
                self.status.setText('No audible microphone signal. Check mute, input volume and selected device, then retry.')
            elif not restored:
                self.status.setText('Sample ready. Another app is using the headset. Close its audio stream, then choose Play sample to restore playback safely.')
            else:
                self.status.setText('Playing your microphone sample. Retry to record again.')
                self.play_sample()
        self.run_action(finish, finished)

    def prepare_playback(self):
        if self.worker or self.capturing:
            return
        def restored(value, error):
            if self.closing:
                self.complete_close()
            elif error or not value:
                self.status.setText('Playback is waiting for the headset to be released by other apps. Close their audio streams and retry Play sample.')
            else:
                self.play_sample()
        self.run_action(self.devices.restore, restored)

    def play_sample(self):
        self.player.setSource(QUrl.fromLocalFile(str(self.path)))
        self.player.play()
        self.update_buttons()

    def reject(self):
        self.closing = True
        self.player.stop()
        if self.worker:
            return
        if self.capturing or self.sample or self.failed_capture:
            self.finish_capture()
        else:
            self.complete_close()

    def complete_close(self):
        self.clear_playback()
        self.temp.cleanup()
        super().reject()

