"""OBS 27 microphone levels, without copying audio frames into Python.

ABI: obsproject/obs-studio 27.2.3 libobs/obs-audio-controls.h and .c.
Callbacks contain eight dBFS values per array, once per captured audio packet.
Both peaks are AFTER source filters. input_peak is before the volume fader,
not before RNNoise; peak includes source volume. Neither proves encoded audio.
"""
import ctypes as C
import math
import threading
import time


LevelsCallback = C.CFUNCTYPE(None, C.c_void_p, *([C.POINTER(C.c_float)] * 3))


class MicrophoneTelemetry:
    def __init__(self, obs, source, source_id):
        self.obs = obs
        self.source_id = source_id
        self.lock = threading.Lock()
        self.packets = self.nonzero_packets = 0
        self.last_packet = None
        self.peak = self.input_peak = -math.inf
        self.clipped_at = None
        self.callback = LevelsCallback(self._levels)
        self.handle = obs.obs_volmeter_create(2)  # OBS_FADER_LOG
        if not self.handle:
            raise RuntimeError('Could not create microphone level meter.')
        obs.obs_volmeter_set_peak_meter_type(self.handle, 0)  # SAMPLE_PEAK_METER
        obs.obs_volmeter_add_callback(self.handle, self.callback, None)
        if not obs.obs_volmeter_attach_source(self.handle, source):
            self.close()
            raise RuntimeError('Could not attach microphone level meter.')

    def _levels(self, _param, _magnitude, peak, input_peak):
        # OBS zeroes unused channels. Its dB conversion maps those to -inf.
        # Read only 16 scalar levels, never audio samples or Qt state.
        output = max((peak[i] for i in range(8) if not math.isnan(peak[i])), default=-math.inf)
        incoming = max((input_peak[i] for i in range(8) if not math.isnan(input_peak[i])), default=-math.inf)
        now = time.monotonic()
        with self.lock:
            self.packets += 1
            self.nonzero_packets += int(incoming > -math.inf)
            self.last_packet = now
            self.peak, self.input_peak = output, incoming
            if max(output, incoming) >= 0:
                self.clipped_at = now

    def status(self):
        now = time.monotonic()
        with self.lock:
            age = None if self.last_packet is None else now - self.last_packet
            fresh = age is not None and age < 1.5
            peak = self.peak if fresh else -math.inf
            incoming = self.input_peak if fresh else -math.inf
            clipping = fresh and self.clipped_at is not None and now - self.clipped_at < 1.5
            state = ('no_packets' if not fresh else 'clipping' if clipping else
                     'silent' if incoming == -math.inf else 'quiet' if incoming < -50 else 'signal')
            return dict(source=self.source_id, packets=self.packets,
                        nonzero_packets=self.nonzero_packets, peak_db=peak,
                        input_peak_db=incoming, packet_age=age, state=state,
                        signal=fresh and incoming > -math.inf, clipping=clipping)

    def close(self):
        if self.handle:
            # remove_callback waits on OBS's callback mutex. Do not hold ours.
            # Detach removes its source capture callback before destruction.
            self.obs.obs_volmeter_remove_callback(self.handle, self.callback, None)
            self.obs.obs_volmeter_detach_source(self.handle)
            self.obs.obs_volmeter_destroy(self.handle)
            self.handle = None
