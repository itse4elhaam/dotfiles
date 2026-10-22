"""Compact microphone telemetry display. This widget never opens a device."""
import math

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QSizePolicy


class MicrophoneMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.name = QLabel()
        self.name.setObjectName('muted')
        self.name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.level = QProgressBar()
        self.level.setRange(0, 60)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(5)
        self.message = QLabel()
        self.message.setObjectName('muted')
        self.message.setWordWrap(True)
        layout.addWidget(self.name)
        layout.addWidget(self.level)
        layout.addWidget(self.message)
        self.show_status(None)

    def show_status(self, status, name='', enabled=True):
        if not isinstance(status, dict) or status.get('state') == 'off':
            status = dict(state='idle' if enabled else 'off', peak_db=-math.inf)
        state = status['state']
        source = status.get('source')
        active_name = name or source or 'Microphone'
        self.name.setText(active_name)
        self.name.setToolTip(source or active_name)
        messages = dict(idle='Waiting for live microphone', off='Microphone off',
                        no_packets='No audio packets', silent='Silent audio received',
                        quiet='Very quiet input', signal='Microphone signal received',
                        clipping='Clipping detected')
        peak = status.get('peak_db', -math.inf)
        self.level.setValue(round(max(0, min(60, peak + 60))) if math.isfinite(peak) else 0)
        color = '#f8957e' if state == 'clipping' else '#dabc72' if state in ('no_packets', 'silent', 'quiet') else '#6cdda6'
        self.level.setStyleSheet('QProgressBar { border: none; background: #35464c; border-radius: 2px; } '
                                'QProgressBar::chunk { background: ' + color + '; border-radius: 2px; }')
        reading = f' · {peak:.0f} dBFS' if math.isfinite(peak) else ''
        self.message.setText(messages.get(state, 'Microphone status unavailable') + reading)
        self.setToolTip('Signal after microphone processing. Peak is after the volume fader; '
                        'clipping checks the pre-fader peak too. This does not verify the saved file.')
