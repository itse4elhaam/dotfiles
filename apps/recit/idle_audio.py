"""Recorder-page microphone ownership. All device work uses the app's one worker."""
import time
from audio_debug import AudioTrace, emit


class IdleAudio:
    def __init__(self, window):
        self.window = window
        self.key = None
        self.source = None
        self.owner = None
        self.pending = False
        self.generation = 0
        self.error = ''
        self.retry_at = 0
        self.verify_at = 0
        self.verified = False
        self.audio_trace = None

    def wanted(self):
        w = self.window
        return (w.engine is not None and w.isVisible() and not w.isMinimized()
                and not w._closing and not w.in_library() and not w.recording
                and not w.busy and not w.counting and w.live_microphone.isChecked()
                and w.microphone.currentData() is not None)

    def stop(self):
        active = self.source is not None or self.owner is not None or self.pending
        if active:
            emit(self, 'idle.stopping', source=self.source, outcome='pending' if self.pending else 'active')
        self.generation += 1
        self.key = self.source = None
        self.verified = False
        w = self.window
        if w.engine and self.owner is not None:
            w.engine.release_audio()
        # A pending prepare may still switch profiles. Keep its fence until it exits.
        if not self.pending:
            self.release_owner()
        if active:
            emit(self, 'idle.stopped', outcome='pending_prepare' if self.pending else 'released')

    def release_owner(self):
        if self.owner is not None:
            self.window.audio_devices.release_capture(self.owner)
            self.owner = None

    def transfer(self):
        """Recording takes the live source and its restoration fence without a gap."""
        w = self.window
        w._capture_owner, self.owner = self.owner, None
        source = self.source
        emit(self, 'idle.handoff', source=source, outcome='recording', reason='reuse_capture')
        self.source = self.key = None
        self.generation += 1
        return source

    def reconcile(self):
        w = self.window
        # Recording/countdown and the check dialog own the chain during handoff.
        if w.recording or w.counting or w.preparing_audio or getattr(w, 'audio_check_dialog', None):
            return
        if not self.wanted():
            if self.key is not None or self.owner is not None:
                self.stop()
            return
        key = (w.microphone.currentData(), w.clean_microphone.isChecked())
        if self.key != key:
            self.stop()
            self.key = key
            self.error = ''
            self.retry_at = 0
        if self.pending or (w.audio_worker and w.audio_worker.isRunning()):
            return
        if self.source:
            if isinstance(self.audio_trace, AudioTrace):
                self.audio_trace.telemetry('idle', w.engine.audio_status())
            if time.monotonic() < self.verify_at:
                return
            self.verify_at = time.monotonic() + 2
            generation = self.generation
            def verified(source, error):
                if generation != self.generation or w._closing:
                    return
                if error or source != self.source:
                    self.fail(error or 'Microphone source changed. Reconnecting…')
                else:
                    if not self.verified:
                        emit(self, 'idle.verified', source=source)
                    self.verified = True
            w.run_audio(w.engine.verify_audio_route, verified)
            return
        if time.monotonic() < self.retry_at:
            return
        self.audio_trace = w.audio_trace = w.engine.audio_trace = w.audio_devices.audio_trace = AudioTrace('idle')
        emit(self, 'session.start', selection=key[0], processing=key[1])
        emit(self, 'idle.preparing', selection=key[0])
        self.pending = True
        self.owner = w.audio_devices.hold_capture()
        generation = self.generation
        def prepared(source, error):
            self.pending = False
            if generation != self.generation or not self.wanted():
                emit(self, 'idle.discarded', source=source, reason='cancelled_or_selection_changed')
                self.release_owner()
                self.key = None
                return
            if error:
                self.fail(error)
                return
            try:
                w.engine.begin_audio_monitor(source, key[1])
                self.source = source
                emit(self, 'idle.opened', source=source)
                self.verify_at = 0
            except Exception as exc:
                emit(self, 'idle.open_failed', level='warning', exception_type=type(exc).__name__)
                self.fail(str(exc))
        w.run_audio(lambda: w.audio_devices.prepare(key[0]), prepared)

    def fail(self, error):
        emit(self, 'idle.failed', level='warning', reason='monitor_unavailable', source=self.source)
        self.stop()
        self.error = error
        self.retry_at = time.monotonic() + 3
        # Keep the attempted key so a failed device doesn't retry on every tick.
        w = self.window
        self.key = (w.microphone.currentData(), w.clean_microphone.isChecked())
