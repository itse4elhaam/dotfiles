"""Bounded audio diagnostics to the launcher's existing stderr log, never samples.

Call only from control/UI/worker threads. No callback logging or file handler.
"""
from functools import wraps
import json
import logging
import math
import threading
import time
import uuid


logger = logging.getLogger('recit.audio')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# Deliberately no arbitrary messages, exception strings, file paths or payloads.
_FIELDS = set('selection source card label prior_profile target_profile changed outcome reason '
              'connection_signal connected stale_connection requested_source actual_source stream_index muted gain sample_specification '
              'obs_rate backend processing filter method threshold release_time packets '
              'nonzero_packets packet_age state peak_db input_peak_db signal clipping '
              'frames exception_type duration_ms phase auto_headset desktop_audio'.split())


class AudioTrace:
    def __init__(self, purpose='record', clock=time.monotonic):
        self.session = uuid.uuid4().hex[:12]
        self.purpose, self.clock = purpose, clock
        self.started = clock()
        self.last = {}
        self.lock = threading.Lock()

    def event(self, event, *, level='info', every=0, **fields):
        with self.lock:
            now = self.clock()
            key = (event, fields.get('source'), fields.get('card'), fields.get('connected'))
            if every and now - self.last.get(key, -math.inf) < every:
                return
            self.last[key] = now
            record = dict(event=event, session=self.session, purpose=self.purpose,
                          elapsed_ms=round(max(0, now - self.started) * 1000),
                          phase=fields.get('phase', event.split('.')[0]), level=level)
            for key, value in fields.items():
                if key not in _FIELDS:
                    continue
                if isinstance(value, float) and not math.isfinite(value):
                    value = None
                if value is None or isinstance(value, (str, bool, int, float)):
                    record[key] = value[:256] if isinstance(value, str) else value
            logger.log(logging.WARNING if level == 'warning' else logging.INFO,
                       'recit.audio %s', json.dumps(record, separators=(',', ':'), allow_nan=False))

    def telemetry(self, phase, status, *, outcome=None):
        if isinstance(status, dict):
            fields = {key: status[key] for key in (
                'source', 'packets', 'nonzero_packets', 'packet_age', 'state',
                'peak_db', 'input_peak_db', 'signal', 'clipping') if key in status}
            self.event(f'{phase}.telemetry', every=0 if outcome else 5,
                       outcome=outcome, **fields)


def traced(phase, every=0):
    """Keep typed failures and monotonic phase durations before UI stringification."""
    def decorate(function):
        @wraps(function)
        def call(self, *args, **kwargs):
            trace = getattr(self, 'audio_trace', None)
            if not isinstance(trace, AudioTrace):
                return function(self, *args, **kwargs)
            started = trace.clock()
            trace.event(f'{phase}.start', every=every, phase=phase)
            try:
                result = function(self, *args, **kwargs)
            except Exception as exc:
                trace.event(f'{phase}.failed', level='warning', phase=phase,
                            exception_type=type(exc).__name__,
                            reason=type(exc.__cause__).__name__ if exc.__cause__ else None,
                            duration_ms=round((trace.clock() - started) * 1000))
                raise
            trace.event(f'{phase}.done', every=every, phase=phase,
                        duration_ms=round((trace.clock() - started) * 1000))
            return result
        return call
    return decorate


def emit(owner, event, **fields):
    trace = getattr(owner, 'audio_trace', None)
    if isinstance(trace, AudioTrace):
        trace.event(event, **fields)
