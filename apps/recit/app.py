#!/usr/bin/env python3
"""RecIt: a small native frontend for the OBS recording engine."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer, Signal, QThread, QProcess, QUrl, QSettings
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap, QShortcut, QKeySequence, QCursor
from floating import CameraBubble, ZoomMotion
from windows import WindowCatalog
from recordings import Recordings
from naming import next_recording_path, recording_files
from audio_devices import AudioDevices, AudioDeviceError
from audio_debug import AudioTrace, emit
from engine import recording_audio_warning
from microphone_meter import MicrophoneMeter
from idle_audio import IdleAudio
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QSlider, QCheckBox, QFileDialog, QFrame,
    QSystemTrayIcon, QMenu, QMessageBox, QSizePolicy, QDialog, QLineEdit, QStackedWidget, QScrollArea,
)

ROOT = Path(__file__).resolve().parent
ICON = ROOT / 'assets/recit-mark.svg'
VIDEOS = Path.home() / 'Videos/RecIt'
STATE = Path.home() / '.local/state/glint'
STYLE = """
QWidget { background: #111b20; color: #eef1ec; font-family: 'Fira Sans', 'DejaVu Sans'; font-size: 14px; }
QMainWindow { background: #111b20; }
QLabel { background: transparent; }
QLabel#muted { color: #a8babb; font-size: 12px; }
QLabel#eyebrow { color: #9ddbc4; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#title { font-size: 28px; font-weight: 600; }
QLabel#section { font-size: 12px; font-weight: 600; color: #b7c5c4; }
QFrame#panel { background: #18252b; border: 1px solid #2a3a40; border-radius: 16px; }
QPushButton { background: #223239; border: 1px solid #35464c; padding: 10px 15px; border-radius: 9px; font-weight: 600; }
QPushButton:hover { background: #2d4148; border-color: #819a9b; }
QPushButton:checked { background: #28463e; border-color: #9ddbc4; color: #c5f2df; }
QPushButton:disabled { color: #617477; border-color: #26363c; background: #1b2a30; }
QPushButton#record { background: #6cdda6; color: #10291e; border: none; padding: 16px; font-size: 15px; }
QPushButton#record:hover { background: #8aebbc; }
QPushButton#record[stopping="true"] { background: #f8957e; color: #291812; }
QPushButton#record[stopping="true"]:hover { background: #ffae97; }
QPushButton#record:disabled { background: #2b5142; color: #9aada4; }
QScrollArea#sidebar { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #40575c; min-height: 24px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QPushButton#footerNavigation { padding: 8px 6px; font-size: 12px; }
QPushButton#quiet { border: none; background: transparent; color: #b8caca; padding: 6px; }
QComboBox, QLineEdit { background: #1c2b31; border: 1px solid #35464c; border-radius: 7px; padding: 9px; min-height: 15px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #223239; selection-background-color: #34564c; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #627e7e; border-radius: 4px; background: #1c2b31; }
QCheckBox::indicator:checked { background: #9ddbc4; }
QSlider::groove:horizontal { height: 4px; background: #35464c; border-radius: 2px; }
QSlider::handle:horizontal { background: #9ddbc4; width: 15px; margin: -6px 0; border-radius: 7px; }
QMenu { background: #1c2b31; padding: 6px; border: 1px solid #35464c; }
QMenu::item { padding: 9px 18px; }
QMenu::item:selected { background: #34564c; }
QToolTip { background: #2d4148; color: #eef1ec; border: none; padding: 7px; }
"""


def label(text, kind=None):
    item = QLabel(text)
    if kind:
        item.setObjectName(kind)
    return item


def cameras():
    result = []
    for path in sorted(Path('/sys/class/video4linux').glob('video*')):
        device = '/dev/' + path.name
        try:
            info = subprocess.run(['v4l2-ctl', '-d', device, '--list-formats-ext'], capture_output=True, text=True, timeout=2).stdout
            # Ignore metadata and infrared devices. Preserve capture devices with colour formats.
            if any(fmt in info for fmt in ('MJPG', 'YUYV', 'NV12', 'RGB3', 'H264')):
                result.append((path.joinpath('name').read_text().strip(), device))
        except (OSError, subprocess.TimeoutExpired):
            continue
    return result


def microphones():
    try:
        return AudioDevices().microphones()
    except AudioDeviceError:
        return []


class Hotkeys(QThread):
    toggle = Signal()
    pause = Signal()
    zoom = Signal()
    unavailable = Signal(str)

    def run(self):
        import select
        try:
            from Xlib import X, XK, display, error
            conn = display.Display()
            root = conn.screen().root
            mapping = {}
            for key, action in [('F8', self.zoom), ('F9', self.toggle), ('F10', self.pause)]:
                code = conn.keysym_to_keycode(XK.string_to_keysym(key))
                mapping[code] = action
                for locks in (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask):
                    catcher = error.CatchError(error.BadAccess)
                    root.grab_key(code, X.ControlMask | X.ShiftMask | locks, False, X.GrabModeAsync, X.GrabModeAsync, onerror=catcher)
                    conn.sync()
                    if catcher.get_error():
                        self.unavailable.emit('Global shortcuts are in use. Use the tray icon to stop recording.')
            while not self.isInterruptionRequested():
                if conn.pending_events() or select.select([conn.fileno()], [], [], .25)[0]:
                    event = conn.next_event()
                    if event.type == X.KeyPress and event.detail in mapping:
                        mapping[event.detail].emit()
            root.ungrab_key(X.AnyKey, X.AnyModifier)
            conn.sync()
            conn.close()
        except Exception as exc:
            self.unavailable.emit(f'Global shortcuts unavailable. Use the tray icon. {exc}')


class Preview(QWidget):
    resized = Signal(int, int)
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    def paintEngine(self):
        return None
    def resizeEvent(self, event):
        self.resized.emit(self.width(), self.height())
        super().resizeEvent(event)


class FinishWorker(QThread):
    finished_file = Signal(str, str)
    def __init__(self, engine, path):
        super().__init__()
        self.engine, self.path = engine, path
        self.audio_trace = getattr(engine, 'audio_trace', None)
    def run(self):
        started = time.monotonic()
        try:
            self.engine.stop()
            if self.engine.audio_expected is True:
                warning = recording_audio_warning(self.path, self.audio_trace)
                if warning:
                    self.engine.errors.append(warning)
            self.finished_file.emit(str(self.path), '')
        except Exception as exc:
            emit(self, 'finish.failed', level='warning', exception_type=type(exc).__name__,
                 duration_ms=round((time.monotonic() - started) * 1000))
            self.finished_file.emit(str(self.path), str(exc))


class AudioWorker(QThread):
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
            emit(self, 'audio_worker.failed', level='warning', exception_type=type(exc).__name__,
                 duration_ms=round((time.monotonic() - started) * 1000))
            self.result.emit(None, str(exc))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('RecIt')
        self.setWindowIcon(QIcon(str(ICON)))
        self.resize(1120, 840)
        self.setMinimumSize(960, 760)
        self.prefs = QSettings('TrueDevs', 'Glint')  # Preserve existing preferences.
        self.engine = None
        self.audio_devices = AudioDevices()
        self.audio_worker = None
        self.idle_audio = IdleAudio(self)
        self.selected_source = None
        self.preparing_audio = False
        self._audio_generation = 0
        self._audio_warning_since = None
        self._closing = False
        self._capture_window_state = None
        self._audio_retry_at = 0
        self.recording = False
        self.paused = False
        self.busy = False
        self.counting = False
        self.mode = 'camera'
        self.mask_path = self.prefs.value('mask', '')
        self.last_file = None
        self.recordings = None
        self.process = None
        self.worker = None
        self.started = 0
        self.pause_started = 0
        self.paused_duration = 0
        self.quit_after_save = False
        self._configure_pending = False
        self.configuration_valid = False
        self.recording_error = ''
        self.recording_error_baseline = 0
        self.zoom_motion = ZoomMotion()
        self.window_catalog = WindowCatalog()
        self.bubble = CameraBubble()
        self.bubble.stop_requested.connect(self.stop)
        self.bubble.pause_requested.connect(self.toggle_pause)
        self.bubble.zoom_requested.connect(self.toggle_zoom)
        self.bubble.open_requested.connect(self.reveal)
        self.bubble.moved.connect(self.move_camera_overlay)
        VIDEOS.mkdir(parents=True, exist_ok=True)
        STATE.mkdir(parents=True, exist_ok=True)
        self.build()
        self.setup_tray()
        self.restore_preferences()
        self.hotkeys = Hotkeys(self)
        self.hotkeys.toggle.connect(self.toggle_record)
        self.hotkeys.pause.connect(self.toggle_pause)
        self.hotkeys.zoom.connect(self.toggle_zoom)
        self.hotkeys.unavailable.connect(self.notice)
        self.hotkeys.start()
        QShortcut(QKeySequence('Escape'), self, activated=self.cancel_countdown)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)
        self.configure_timer = QTimer(self)
        self.configure_timer.setSingleShot(True)
        self.configure_timer.timeout.connect(self.configure)
        self.start_timer = QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self.start)
        self.zoom_timer = QTimer(self)
        self.zoom_timer.setTimerType(Qt.PreciseTimer)
        self.zoom_timer.setInterval(16)
        self.zoom_timer.timeout.connect(self.animate_zoom)
        QTimer.singleShot(300, self.initialize)

    def build(self):
        from PySide6.QtWidgets import QScrollArea

        class RecordButton(QPushButton):
            def setText(self, text):
                super().setText(text)
                self.setProperty('stopping', text.startswith('■'))
                self.style().unpolish(self)
                self.style().polish(self)

        container = QWidget()
        self.pages = QStackedWidget()
        self.recorder_page = container
        self.pages.addWidget(container)
        self.setCentralWidget(self.pages)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 24, 30, 20)
        layout.setSpacing(18)
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(str(ICON)).pixmap(46, 46))
        header.addWidget(logo)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(label('RecIt', 'title'))
        title_box.addWidget(label('A little less setup. A lot more showing.', 'muted'))
        header.addLayout(title_box)
        header.addStretch()
        layout.addLayout(header)

        content = QGridLayout()
        self.recorder_content = content
        content.setHorizontalSpacing(20)
        content.setVerticalSpacing(10)
        content.setRowStretch(0, 1)
        content.setColumnStretch(1, 1)
        controls = QVBoxLayout()
        controls.setSpacing(9)
        side = QWidget()
        self.controls_panel = QScrollArea()
        self.controls_panel.setObjectName('sidebar')
        self.controls_panel.setWidgetResizable(True)
        self.controls_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_panel.setFixedWidth(280)
        self.controls_panel.setWidget(side)
        side.setLayout(controls)
        controls.setContentsMargins(0, 0, 10, 0)
        controls.addWidget(label('RECORDING SETUP', 'eyebrow'))
        modes = QHBoxLayout()
        self.screen_button = QPushButton('▣  Loom')
        self.camera_button = QPushButton('◉  Camera')
        for button, mode in [(self.screen_button, 'screen'), (self.camera_button, 'camera')]:
            button.setCheckable(True)
            button.setMinimumHeight(42)
            button.clicked.connect(lambda checked, m=mode: self.set_mode(m))
            modes.addWidget(button)
        controls.addLayout(modes)
        self.mode_hint = label('Your screen, with you in the corner.', 'muted')
        self.mode_hint.setWordWrap(True)
        controls.addWidget(self.mode_hint)
        controls.addSpacing(6)
        self.capture_label = label('Capture', 'section')
        controls.addWidget(self.capture_label)
        self.capture_kind = QComboBox()
        self.capture_kind.addItem('Entire screen', 'screen')
        self.capture_kind.addItem('A specific window', 'window')
        controls.addWidget(self.capture_kind)
        self.screen = QComboBox()
        for index, screen in enumerate(QApplication.screens()):
            geo = screen.geometry()
            ratio = screen.devicePixelRatio()
            self.screen.addItem(f'{screen.name()} · {round(geo.width() * ratio)} × {round(geo.height() * ratio)}', index)
        controls.addWidget(self.screen)
        self.window_row = QWidget()
        window_layout = QHBoxLayout(self.window_row)
        window_layout.setContentsMargins(0, 0, 0, 0)
        self.capture_window = QComboBox()
        self.capture_window.setMinimumWidth(0)
        self.capture_window.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.capture_window.addItem('Select a window…', None)
        window_layout.addWidget(self.capture_window, 1)
        self.refresh_button = QPushButton('↻')
        self.refresh_button.setFixedWidth(40)
        self.refresh_button.setToolTip('Refresh open windows')
        self.refresh_button.clicked.connect(self.refresh_windows)
        window_layout.addWidget(self.refresh_button)
        self.window_row.setVisible(False)
        controls.addWidget(self.window_row)
        controls.addWidget(label('Camera', 'section'))
        self.camera = QComboBox()
        self.camera.addItem('Camera off', None)
        for name, path in cameras():
            self.camera.addItem(name, path)
        if self.camera.count() > 1:
            self.camera.setCurrentIndex(1)
        controls.addWidget(self.camera)
        controls.addWidget(label('Microphone', 'section'))
        self.microphone = QComboBox()
        self.microphone.addItem('Automatic microphone', 'default')
        self.microphone.addItem('Microphone off', None)
        for name, source in microphones():
            self.microphone.addItem(name, source)
        controls.addWidget(self.microphone)
        self.audio_check_button = QPushButton('Quick audio check')
        self.audio_check_button.clicked.connect(self.open_audio_check)
        controls.addWidget(self.audio_check_button)
        self.live_microphone = QCheckBox('Live microphone levels')
        self.live_microphone.setChecked(True)
        self.live_microphone.setToolTip('Uses your microphone while the recorder is visible. Bluetooth headsets use hands-free audio. Turn off to release the microphone.')
        self.live_microphone.toggled.connect(lambda _: self.idle_audio.reconcile())
        controls.addWidget(self.live_microphone)
        self.microphone_meter = MicrophoneMeter()
        controls.addWidget(self.microphone_meter)
        self.clean_microphone = QCheckBox('Clean microphone')
        self.clean_microphone.setChecked(True)
        self.clean_microphone.setToolTip('Reduce background microphone noise and control loud peaks. Turn off to record the microphone without processing. Computer sound is unchanged.')
        controls.addWidget(self.clean_microphone)
        self.desktop_audio = QCheckBox('Include computer sound')
        controls.addWidget(self.desktop_audio)
        controls.addSpacing(4)

        self.widget_panel = QFrame()
        self.widget_panel.setObjectName('panel')
        widget_layout = QVBoxLayout(self.widget_panel)
        widget_layout.setContentsMargins(14, 12, 14, 14)
        widget_layout.setSpacing(9)
        widget_layout.addWidget(label('YOUR CAMERA WIDGET', 'eyebrow'))
        self.shape = QComboBox()
        for name, value in [('Circle', 'circle'), ('Rounded square', 'rounded'), ('Square', 'square'), ('Custom shape…', 'custom')]:
            self.shape.addItem(name, value)
        widget_layout.addWidget(self.shape)
        size_row = QHBoxLayout()
        size_row.addWidget(label('Size', 'muted'))
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(12, 42)
        self.size.setValue(23)
        size_row.addWidget(self.size)
        widget_layout.addLayout(size_row)
        self.position = QComboBox()
        for name, value in [('Bottom right', 'bottom-right'), ('Bottom left', 'bottom-left'), ('Top right', 'top-right'), ('Top left', 'top-left')]:
            self.position.addItem(name, value)
        widget_layout.addWidget(self.position)
        self.mask_button = QPushButton('Choose shape image…')
        self.mask_button.setVisible(False)
        self.mask_button.clicked.connect(self.choose_mask)
        widget_layout.addWidget(self.mask_button)
        controls.addWidget(self.widget_panel)
        self.mirror = QCheckBox('Mirror my camera')
        self.mirror.setChecked(True)
        controls.addWidget(self.mirror)
        quality_row = QHBoxLayout()
        self.quality = QComboBox()
        self.quality.addItem('4K · 30 fps', (3840, 2160))
        self.quality.addItem('1080p · 30 fps', (1920, 1080))
        quality_row.addWidget(self.quality)
        controls.addLayout(quality_row)
        content.addWidget(self.controls_panel, 0, 0)

        right = QVBoxLayout()
        right.setSpacing(12)
        preview_top = QHBoxLayout()
        self.preview_title = label('FULL CAMERA VIEW', 'eyebrow')
        preview_top.addWidget(self.preview_title)
        self.focus_button = QPushButton('Expand camera')
        self.focus_button.setCheckable(True)
        self.focus_button.toggled.connect(self.focus_camera)
        preview_top.addWidget(self.focus_button)
        preview_top.addStretch()
        self.encoder_label = label('Starting recording engine…', 'muted')
        self.encoder_label.setWordWrap(True)
        preview_top.addWidget(self.encoder_label)
        right.addLayout(preview_top)
        preview_frame = QFrame()
        preview_frame.setObjectName('panel')
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(2, 2, 2, 2)
        self.preview = Preview()
        self.preview.resized.connect(self.resize_preview)
        preview_layout.addWidget(self.preview)
        right.addWidget(preview_frame, 1)
        self.source_note = label('4K output · source detail depends on your display and camera.', 'muted')
        self.source_note.setWordWrap(True)
        right.addWidget(self.source_note)
        zoom_row = QHBoxLayout()
        self.zoom_button = QPushButton('⌖  Zoom to pointer')
        self.zoom_button.setCheckable(True)
        self.zoom_button.setEnabled(False)
        self.zoom_button.setToolTip('While recording, press Ctrl + Shift + F8 to zoom in or out at your pointer.')
        self.zoom_button.clicked.connect(self.toggle_zoom)
        zoom_row.addWidget(self.zoom_button, 1)
        self.zoom_amount = QComboBox()
        for title, value in [('1.5×', 1.5), ('2×', 2.0), ('2.5×', 2.5)]:
            self.zoom_amount.addItem(title, value)
        self.zoom_amount.setCurrentIndex(1)
        zoom_row.addWidget(self.zoom_amount)
        right.addLayout(zoom_row)
        self.status = label('Getting your studio ready…')
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(38)
        right.addWidget(self.status)
        actions = QHBoxLayout()
        self.record_button = RecordButton('●  Start recording')
        self.record_button.setObjectName('record')
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.toggle_record)
        actions.addWidget(self.record_button, 1)
        self.pause_button = QPushButton('Pause')
        self.pause_button.setVisible(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        actions.addWidget(self.pause_button)
        right.addLayout(actions)
        shortcuts = label('Ctrl + Shift + F9  record / stop    ·    F10  pause    ·    F8  pointer zoom', 'muted')
        shortcuts.setWordWrap(True)
        right.addWidget(shortcuts)
        controls.addStretch()
        # Device/window labels must not set the scroll content's minimum width.
        # Qt then resizes it to the viewport, including the vertical scrollbar.
        for combo in side.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preview_column = right
        content.addLayout(right, 0, 1, 2, 1)
        self.navigation_footer = QWidget()
        self.navigation_footer.setFixedWidth(280)
        navigation = QHBoxLayout(self.navigation_footer)
        navigation.setContentsMargins(0, 0, 10, 0)
        navigation.setSpacing(6)
        self.library_button = QPushButton('Recordings')
        self.library_button.clicked.connect(lambda: self.open_recordings())
        self.sharing_button = QPushButton('Sharing')
        self.sharing_button.clicked.connect(self.sharing_settings)
        for button in (self.library_button, self.sharing_button):
            button.setObjectName('footerNavigation')
            navigation.addWidget(button, 1)
        content.addWidget(self.navigation_footer, 1, 0, Qt.AlignLeft | Qt.AlignBottom)
        layout.addLayout(content, 1)
        self.config_controls = [self.screen_button, self.camera_button, self.capture_kind, self.capture_window, self.refresh_button, self.screen, self.camera, self.microphone, self.clean_microphone, self.desktop_audio, self.shape, self.size, self.position, self.mask_button, self.mirror, self.quality]
        for combo in (self.screen, self.capture_window, self.camera, self.microphone, self.position):
            combo.currentIndexChanged.connect(self.schedule_configure)
        self.capture_kind.currentIndexChanged.connect(self.capture_changed)
        self.shape.currentIndexChanged.connect(self.shape_changed)
        self.size.valueChanged.connect(self.schedule_configure)
        self.mirror.toggled.connect(self.schedule_configure)
        self.clean_microphone.toggled.connect(self.schedule_configure)
        self.desktop_audio.toggled.connect(self.schedule_configure)
        self.quality.currentIndexChanged.connect(self.quality_changed)
        self.set_mode('screen', configure=False)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon(str(ICON)), self)
        self.tray.setToolTip('RecIt · Ready to record')
        menu = QMenu()
        menu.addAction('Open RecIt', self.reveal)
        self.tray_record = menu.addAction('Start recording', self.toggle_record)
        self.tray_pause = menu.addAction('Pause', self.toggle_pause)
        self.tray_pause.setEnabled(False)
        self.tray_zoom = menu.addAction('Zoom to pointer · Ctrl+Shift+F8', self.toggle_zoom)
        self.tray_zoom.setEnabled(False)
        menu.addSeparator()
        menu.addAction('Quit RecIt', self.close)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.reveal() if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    def restore_preferences(self):
        for name in ('camera', 'microphone', 'shape', 'position', 'quality'):
            widget = getattr(self, name)
            saved = self.prefs.value(name)
            if saved is not None:
                index = widget.findText(str(saved))
                if index >= 0:
                    widget.setCurrentIndex(index)
        if self.prefs.contains('microphone_id'):
            source = self.prefs.value('microphone_id') or None
            index = self.microphone.findData(source)
            if index < 0:
                self.microphone.addItem('Unavailable microphone: ' + source, source)
                index = self.microphone.count() - 1
            self.microphone.setCurrentIndex(index)
        self.size.setValue(int(self.prefs.value('size', 23)))
        self.mirror.setChecked(self.prefs.value('mirror', True, type=bool))
        self.clean_microphone.setChecked(self.prefs.value('clean_microphone', True, type=bool))
        self.desktop_audio.setChecked(self.prefs.value('desktop_audio', False, type=bool))
        self.set_mode(self.prefs.value('mode', 'camera'), configure=False)
        files = recording_files(VIDEOS)
        if files:
            self.set_last(files[0])

    def save_preferences(self):
        for name in ('camera', 'microphone', 'shape', 'position', 'quality'):
            self.prefs.setValue(name, getattr(self, name).currentText())
        self.prefs.setValue('microphone_id', self.microphone.currentData() or '')
        self.prefs.setValue('size', self.size.value())
        self.prefs.setValue('mirror', self.mirror.isChecked())
        self.prefs.setValue('clean_microphone', self.clean_microphone.isChecked())
        self.prefs.setValue('desktop_audio', self.desktop_audio.isChecked())
        self.prefs.setValue('mode', self.mode)
        self.prefs.setValue('mask', self.mask_path)
        self.prefs.sync()

    def initialize(self):
        if self._closing or self.in_library() or self.engine:
            return
        try:
            if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                raise RuntimeError('This version needs an X11 session. Sign in with an Xorg session to record.')
            from engine import Engine
            w, h = self.quality.currentData()
            self.engine = Engine(int(self.preview.winId()), w, h, fps=30)
            self.resize_preview(self.preview.width(), self.preview.height())
            self.configure()
        except Exception as exc:
            self.notice(f'Could not start the recording engine: {exc}')
            self.encoder_label.setText('Engine unavailable')
            self.record_button.setEnabled(False)

    def quality_changed(self):
        if self.engine and not (self.recording or self.busy):
            self.configuration_valid = False
            self.idle_audio.stop()
            self.hide_bubble()
            self.record_button.setEnabled(False)
            self.configure_timer.stop()
            try:
                self.engine.close()
            except Exception as exc:
                self.notice(str(exc))
            self.engine = None
            QTimer.singleShot(0, self.initialize)

    def set_mode(self, mode, configure=True):
        if self.recording or self.busy or self.counting:
            return
        self.mode = mode if mode in ('screen', 'camera') else 'screen'
        self.configuration_valid = False
        self.screen_button.setChecked(self.mode == 'screen')
        self.camera_button.setChecked(self.mode == 'camera')
        camera_mode = self.mode == 'camera'
        self.focus_button.setVisible(camera_mode)
        if not camera_mode:
            self.focus_button.setChecked(False)
        self.preview_title.setText('FULL CAMERA VIEW' if camera_mode else 'LIVE PREVIEW')
        self.capture_label.setVisible(not camera_mode)
        self.capture_kind.setVisible(not camera_mode)
        self.screen.setVisible(not camera_mode and self.capture_kind.currentData() == 'screen')
        self.window_row.setVisible(not camera_mode and self.capture_kind.currentData() == 'window')
        self.zoom_button.setVisible(not camera_mode)
        self.zoom_amount.setVisible(not camera_mode)
        self.widget_panel.setVisible(self.mode == 'screen')
        self.screen.setEnabled(self.mode == 'screen')
        self.capture_kind.setEnabled(self.mode == 'screen')
        self.capture_window.setEnabled(self.mode == 'screen')
        self.refresh_button.setEnabled(self.mode == 'screen')
        self.mode_hint.setText('Your screen, with you in the corner.' if self.mode == 'screen' else 'Just you. Full frame. Ready to explain.')
        if configure:
            self.schedule_configure()

    def focus_camera(self, expanded):
        self.controls_panel.setVisible(not expanded)
        self.recorder_content.removeItem(self.preview_column)
        if expanded:
            self.recorder_content.addLayout(self.preview_column, 0, 0, 1, 2)
        else:
            self.recorder_content.addLayout(self.preview_column, 0, 1, 2, 1)
        self.focus_button.setText('Show controls' if expanded else 'Expand camera')

    def capture_changed(self):
        window_mode = self.capture_kind.currentData() == 'window'
        self.screen.setVisible(self.mode == 'screen' and not window_mode)
        self.window_row.setVisible(self.mode == 'screen' and window_mode)
        if window_mode:
            self.refresh_windows()
        self.schedule_configure()

    def refresh_windows(self):
        previous = self.capture_window.currentData()
        self.capture_window.blockSignals(True)
        self.capture_window.clear()
        try:
            windows = self.window_catalog.list()
            for title, wid in windows:
                self.capture_window.addItem(title, wid)
            if not windows:
                self.capture_window.addItem('No open windows. Open one, then refresh.', None)
            index = self.capture_window.findData(previous)
            self.capture_window.setCurrentIndex(max(0, index))
            self.capture_window.setToolTip(self.capture_window.currentText())
        except Exception as exc:
            self.capture_window.addItem('Window list unavailable', None)
            if hasattr(self, 'status'):
                self.notice(f'Could not list windows: {exc}')
        finally:
            self.capture_window.blockSignals(False)
        self.schedule_configure()

    def shape_changed(self):
        custom = self.shape.currentData() == 'custom'
        self.mask_button.setVisible(custom)
        if custom and not self.mask_path and self.engine:
            self.choose_mask()
        self.schedule_configure()

    def choose_mask(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose a camera shape. White/opaque areas keep your image.', str(Path.home()), 'Shape images (*.png *.webp *.bmp)')
        if path:
            self.mask_path = path
            self.mask_button.setText(Path(path).name)
            self.schedule_configure()
        elif not self.mask_path:
            self.shape.setCurrentIndex(0)

    def schedule_configure(self, *_):
        if hasattr(self, 'configure_timer') and self.engine and not (self.recording or self.busy or self.counting):
            self.configuration_valid = False
            self.record_button.setEnabled(False)
            self._configure_pending = True
            self.configure_timer.start(180)

    def configure(self, microphone=None, recording_setup=False):
        if not recording_setup:
            key = (self.microphone.currentData(), self.clean_microphone.isChecked())
            if self.idle_audio.source and self.idle_audio.key != key:
                self.idle_audio.stop()
            microphone = self.idle_audio.source
        if self.in_library() or not self.engine or self.recording or (self.busy and not recording_setup):
            return
        self._configure_pending = False
        self.configuration_valid = False
        try:
            self.hide_bubble()
            camera = self.camera.currentData()
            window_id = self.capture_window.currentData() if self.capture_kind.currentData() == 'window' and self.mode == 'screen' else None
            if self.mode == 'screen' and self.capture_kind.currentData() == 'window':
                if not window_id or not self.window_catalog.geometry(window_id):
                    raise ValueError('Select an open window. Refresh the list if needed.')
            if self.mode == 'camera' and not camera:
                raise ValueError('Choose a camera to use Camera mode.')
            self.engine.configure(mode=self.mode, camera=camera, microphone=microphone,
                microphone_processing=self.clean_microphone.isChecked(),
                desktop_audio=recording_setup and self.desktop_audio.isChecked(), shape=self.shape.currentData(),
                mask_path=self.mask_path or None, size=self.size.value() / 100,
                position=self.position.currentData(), screen=self.screen.currentData() or 0,
                mirror=self.mirror.isChecked(), floating_camera=self.mode == 'screen' and bool(camera) and not window_id, window_id=window_id)
            if self.mode == 'screen' and camera:
                self.show_bubble()
            self.record_button.setEnabled(True)
            self.configuration_valid = True
            self.engine_notice('Ready when you are. Your recording stays on this computer until you upload it.')
            self.encoder_label.setText('OBS engine · Intel hardware available')
            screen = QApplication.screens()[self.screen.currentIndex()]
            geo = screen.geometry()
            ratio = screen.devicePixelRatio()
            self.source_note.setText(f'{self.quality.currentText()} output · Display source {round(geo.width() * ratio)} × {round(geo.height() * ratio)}. '
                + ('Source resolution determines actual detail.' if camera else 'Camera is off.'))
            if self.mode == 'camera':
                self.source_note.setText(f'{self.camera.currentText()} · {self.quality.currentText()} output · Full image, no crop.')
            if window_id:
                self.source_note.setText(f'{self.quality.currentText()} · Recording only the selected window. Keep it open and unminimized.')
            self.save_preferences()
        except Exception as exc:
            self.record_button.setEnabled(False)
            self.notice(f'Check your setup: {exc}')

    def resize_preview(self, width, height):
        if self.engine:
            ratio = self.preview.devicePixelRatioF()
            self.engine.resize_preview(round(width * ratio), round(height * ratio))

    def show_bubble(self):
        screen = QApplication.screens()[self.screen.currentIndex()]
        self.bubble.arrange(screen, self.size.value() / 100, self.position.currentData(), self.shape.currentData(), self.mask_path,
            mirror_mask=self.capture_kind.currentData() == 'window' and self.mirror.isChecked())
        self.bubble.recording = self.recording
        self.bubble.show()
        ratio = self.bubble.devicePixelRatioF()
        try:
            self.engine.attach_camera_preview(int(self.bubble.winId()), round(self.bubble.width() * ratio), round(self.bubble.height() * ratio))
        except Exception:
            self.bubble.hide()
            raise

    def hide_bubble(self):
        if self.engine:
            self.engine.detach_camera_preview()
        self.bubble.hide()

    def move_camera_overlay(self):
        if self.engine and self.mode == 'screen' and self.capture_kind.currentData() == 'window':
            bounds = QApplication.screens()[self.screen.currentIndex()].availableGeometry()
            dx = max(1, bounds.width() - self.bubble.width())
            dy = max(1, bounds.height() - self.bubble.height())
            self.engine.set_camera_position((self.bubble.x() - bounds.left()) / dx, (self.bubble.y() - bounds.top()) / dy)

    def toggle_zoom(self, *_):
        if not self.recording or self.busy or self.mode != 'screen':
            self.zoom_button.setChecked(False)
            return
        self.zoom_motion.enabled = not self.zoom_motion.enabled
        self.zoom_motion.last_time = time.monotonic()
        self.zoom_button.setChecked(self.zoom_motion.enabled)
        self.zoom_button.setText('⌖  Zoom out' if self.zoom_motion.enabled else '⌖  Zoom to pointer')
        self.bubble.zoomed = self.zoom_motion.enabled
        self.tray_zoom.setText('Zoom out · Ctrl+Shift+F8' if self.zoom_motion.enabled else 'Zoom to pointer · Ctrl+Shift+F8')
        self.zoom_timer.start()

    def animate_zoom(self):
        if not self.engine or not self.recording or self.busy or self.mode != 'screen':
            self.zoom_timer.stop()
            return
        if self.paused:
            self.zoom_motion.last_time = time.monotonic()
            return
        screen = QApplication.screens()[self.screen.currentIndex()]
        bounds = screen.geometry()
        pointer = QCursor.pos()
        x, y = self.zoom_motion.x, self.zoom_motion.y
        if bounds.contains(pointer):
            x = (pointer.x() - bounds.left()) / bounds.width()
            y = (pointer.y() - bounds.top()) / bounds.height()
        if self.capture_kind.currentData() == 'window':
            geometry = self.window_catalog.geometry(self.capture_window.currentData())
            if not geometry:
                return  # The recording health check will save if the target closes.
            px, py = self.window_catalog.pointer()
            wx, wy, width, height = geometry
            if wx <= px < wx + width and wy <= py < wy + height:
                x, y = (px - wx) / width, (py - wy) / height
            else:
                x, y = self.zoom_motion.x, self.zoom_motion.y
        try:
            factor, x, y = self.zoom_motion.step(self.zoom_amount.currentData(), x, y)
            self.engine.set_screen_zoom(factor, x, y)
            if not self.zoom_motion.enabled and factor == 1.0:
                self.zoom_timer.stop()
        except Exception as exc:
            self.zoom_timer.stop()
            self.notice(f'Pointer zoom stopped: {exc}')

    def reset_zoom(self):
        self.zoom_timer.stop()
        self.zoom_motion.reset()
        self.zoom_button.setChecked(False)
        self.zoom_button.setEnabled(False)
        self.zoom_button.setText('⌖  Zoom to pointer')
        self.tray_zoom.setEnabled(False)
        self.tray_zoom.setText('Zoom to pointer · Ctrl+Shift+F8')
        self.bubble.zoomed = False
        if self.engine:
            self.engine.set_screen_zoom(1.0, .5, .5)

    def toggle_record(self):
        if self.in_library():
            return
        if self.recording:
            self.stop()
        elif self.counting:
            self.cancel_countdown()
        elif self.engine and not self.busy and self.record_button.isEnabled():
            self.counting = True
            self.countdown = 3
            self.lock_controls(True)
            self.record_button.setText('Cancel · 3')
            self.notice('Starting in 3… Get your explanation ready. Esc cancels.')
            self.count_timer = QTimer(self)
            self.count_timer.timeout.connect(self.countdown_tick)
            self.count_timer.start(1000)

    def countdown_tick(self):
        if self.in_library():
            return
        self.countdown -= 1
        if self.countdown:
            self.record_button.setText(f'Cancel · {self.countdown}')
            self.notice(f'Starting in {self.countdown}… Esc cancels.')
        else:
            self.count_timer.stop()
            # Hide before capture starts, avoiding the preview recursion in the recording.
            if self.mode == 'screen':
                self._capture_window_state = self.windowState() & ~Qt.WindowMinimized
                self.hide()
            self.start_timer.start(250)

    def cancel_countdown(self):
        if self.preparing_audio:
            self.audio_start_failed('Microphone check cancelled. Recording has not started.')
            return
        if self.counting:
            self.count_timer.stop()
            self.start_timer.stop()
            self.counting = False
            self.lock_controls(False)
            self.record_button.setText('●  Start recording')
            self.notice('Countdown cancelled. Ready when you are.')
            self.restore_capture_window()

    def start(self):
        if self._closing or self.in_library() or self.busy or self.recording or not self.counting or not self.configuration_valid:
            return
        if self.audio_worker and self.audio_worker.isRunning():
            self.start_timer.start(100)  # Serialize preparation with deferred restoration.
            return
        self.counting = False
        self.busy = self.preparing_audio = True
        self.record_button.setEnabled(False)
        self.notice('Preparing microphone…')
        selection = self.microphone.currentData()
        trace = self.idle_audio.audio_trace if self.idle_audio.source else None
        if not isinstance(trace, AudioTrace):
            trace = AudioTrace()
            trace.event('session.start', selection=selection, processing=self.clean_microphone.isChecked(),
                        desktop_audio=self.desktop_audio.isChecked())
        self.audio_trace = self.engine.audio_trace = self.audio_devices.audio_trace = trace
        emit(self, 'record.requested', selection=selection, processing=self.clean_microphone.isChecked(),
             desktop_audio=self.desktop_audio.isChecked())
        self._audio_generation += 1
        generation = self._audio_generation
        if self.idle_audio.source:
            source = self.idle_audio.transfer()
            self.audio_prepared(source, '')
            return
        self._capture_owner = self.audio_devices.hold_capture()
        self.run_audio(lambda: self.audio_devices.prepare(selection),
            lambda source, error: self.audio_prepared(source, error)
            if generation == self._audio_generation else None)

    def run_audio(self, action, callback):
        generation = self._audio_generation
        worker = self.audio_worker = AudioWorker(action, self)
        worker.result.connect(callback)
        def finished():
            if self.audio_worker is worker:
                self.audio_worker = None
            worker.deleteLater()
            if generation != self._audio_generation and not self.preparing_audio and not self._closing:
                self.retry_audio_restore()
        worker.finished.connect(finished)
        worker.start()

    def audio_prepared(self, source, error):
        if self._closing:
            return  # closeEvent releases capture and restores after the worker exits.
        if error:
            self.audio_start_failed(error)
            return
        self.selected_source = source
        self.configure(microphone=source, recording_setup=True)
        if not self.configuration_valid:
            self.audio_start_failed(self.status.text())
            return
        if source:
            self.busy = self.preparing_audio = True
            self.record_button.setEnabled(False)
            self.restore_capture_window()
            self.engine_notice('Checking microphone; say a few words… Esc cancels.')
            self._audio_deadline = time.monotonic() + 8
            self.poll_microphone(self._audio_generation)
        else:
            self.begin_recording()

    def audio_start_failed(self, error):
        emit(self, 'preparation.aborted', level='warning', reason='preparation_failed_or_cancelled')
        self._audio_generation += 1
        self.busy = self.preparing_audio = False
        self.release_audio()
        self.lock_controls(False)
        self.record_button.setEnabled(self.configuration_valid)
        self.record_button.setText('●  Start recording')
        self.notice(f'Could not prepare microphone: {error}')
        self.restore_capture_window()

    def poll_microphone(self, generation):
        if self._closing or generation != self._audio_generation or not self.preparing_audio:
            return
        status = self.engine.audio_status()
        trace = getattr(self, 'audio_trace', None)
        if isinstance(trace, AudioTrace):
            trace.telemetry('readiness', status)
        if self.microphone_ready(status):
            if self.audio_worker and self.audio_worker.isRunning():
                QTimer.singleShot(100, lambda: self.poll_microphone(generation))
                return
            source = self.selected_source
            self.run_audio(lambda: self.engine.verify_audio_route(timeout=2),
                lambda result, error: self.microphone_verified(generation, result, error))
        elif time.monotonic() >= self._audio_deadline:
            if isinstance(trace, AudioTrace):
                trace.telemetry('readiness', status, outcome='timeout')
                trace.event('readiness.failed', level='warning', exception_type='TimeoutError',
                            reason='no_fresh_nonzero_packets')
            detail = ('No microphone samples arrived.' if not status.get('packets') or
                status.get('packet_age') is None or status['packet_age'] >= 1.5 else
                'Microphone samples contain only silence.')
            self.audio_start_failed(detail + ' Say a few words and try again, or use Check microphone. '
                'If the room is quiet, try turning Clean microphone off. Recording has not started.')
        else:
            QTimer.singleShot(100, lambda: self.poll_microphone(generation))

    def microphone_ready(self, status):
        return (isinstance(status, dict) and status.get('source') == self.selected_source
            and status.get('packets', 0) > 0 and status.get('nonzero_packets', 0) > 0
            and status.get('packet_age') is not None and status['packet_age'] < 1.5)

    def microphone_verified(self, generation, source, error):
        if self._closing or generation != self._audio_generation or not self.preparing_audio:
            return
        if error or source != self.selected_source:
            self.audio_start_failed(error or 'The selected microphone changed during preparation.')
        elif not self.microphone_ready(self.engine.audio_status()):
            self.poll_microphone(generation)
        elif self.mode == 'screen':
            emit(self, 'readiness.ready', source=source)
            self._capture_window_state = self.windowState() & ~Qt.WindowMinimized
            self.hide()
            QTimer.singleShot(250, lambda: self.begin_recording(generation))
        else:
            self.begin_recording(generation)

    def begin_recording(self, generation=None):
        if self._closing or (generation is not None and generation != self._audio_generation):
            return
        if self.selected_source and not self.microphone_ready(self.engine.audio_status()):
            self.poll_microphone(self._audio_generation)
            return
        self.busy = self.preparing_audio = False
        emit(self, 'readiness.accepted', source=self.selected_source)
        self.record_button.setEnabled(True)
        source = self.selected_source
        try:
            if not self.configuration_valid:
                raise RuntimeError(self.status.text())
            if self.mode == 'screen' and self.capture_kind.currentData() == 'window' and not self.window_catalog.geometry(self.capture_window.currentData()):
                raise RuntimeError('The selected window is no longer available. Choose an open window and try again.')
            if shutil.disk_usage(VIDEOS).free < 1024 ** 3:
                raise RuntimeError('Less than 1 GB free. Make some room before recording.')
            window_title = self.capture_window.currentText() if self.mode == 'screen' and self.capture_kind.currentData() == 'window' else ''
            self.record_path = next_recording_path(VIDEOS, self.mode, window_title)
            self.recording_error = ''
            self.recording_error_baseline = len(self.engine.errors)
            self.engine.start(self.record_path)
            encoder = self.engine.stats().get('encoder', '')
            self.encoder_label.setText('Intel hardware · H.264' if encoder == 'ffmpeg_vaapi' else 'CPU encoding · H.264')
            self.started = time.monotonic()
            self.paused_duration = 0
            self.paused = False
            self.recording = True
            self._audio_warning_since = None
            self.bubble.recording = True
            self.zoom_button.setEnabled(self.mode == 'screen')
            self.tray_zoom.setEnabled(self.mode == 'screen')
            self.record_button.setText('■  Stop and save')
            self.pause_button.setVisible(True)
            self.pause_button.setText('Pause')
            self.tray_pause.setEnabled(True)
            self.tray_record.setText('Stop and save')
            self.tray.setIcon(self.record_icon())
            self.engine_notice('Recording. Ctrl + Shift + F9 stops and saves.\n'
                + (f'Microphone: {source}' if source else 'Microphone off'))
            if self.mode == 'screen':
                self.tray.setToolTip('RecIt · Recording\nF9 stop · F10 pause · F8 zoom\nHold Ctrl + Shift with each key')
        except Exception as exc:
            emit(self, 'record_start.failed', level='warning', exception_type=type(exc).__name__)
            self.release_audio()
            self.lock_controls(False)
            self.record_button.setText('●  Start recording')
            self.notice(f'Could not start recording: {exc}')
            self.restore_capture_window()

    def stop(self):
        if not self.recording or self.busy:
            return
        self.busy = True
        self.zoom_timer.stop()
        self.zoom_button.setEnabled(False)
        self.tray_zoom.setEnabled(False)
        self.record_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.tray_record.setEnabled(False)
        self.tray_pause.setEnabled(False)
        self.notice('Saving your recording…')
        self.worker = FinishWorker(self.engine, self.record_path)
        self.worker.finished_file.connect(self.stopped)
        self.worker.start()

    def stopped(self, path, error):
        if error and self.engine.recording:
            self.busy = False
            self.record_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.tray_record.setEnabled(True)
            self.tray_pause.setEnabled(True)
            self.zoom_button.setEnabled(self.mode == 'screen')
            self.tray_zoom.setEnabled(self.mode == 'screen')
            if self.mode == 'screen' and (self.zoom_motion.enabled or self.zoom_motion.factor != 1.):
                self.zoom_motion.last_time = time.monotonic()
                self.zoom_timer.start()
            self.notice(f'OBS is still stopping: {error}. Try Stop again; your recording is retained.')
            self.restore_capture_window()
            return
        engine_errors = self.engine.errors[self.recording_error_baseline:]
        if engine_errors:
            self.recording_error = (self.recording_error + ' ' if self.recording_error else '') + 'Recording ended with an error. Review the saved video before sharing. ' + '; '.join(engine_errors)
        self.recording = False
        self.release_audio()
        self.paused = False
        self.bubble.recording = False
        self.bubble.paused = False
        self.reset_zoom()
        self.tray.setIcon(QIcon(str(ICON)))
        self.tray.setToolTip('RecIt · Saving recording')
        self.restore_capture_window()
        self.pause_button.setVisible(False)
        if error:
            self.finish_save(Path(path), f'Recording stopped with an error: {error}. The original file is preserved.')
            return
        source = Path(path)
        if not source.exists() or source.stat().st_size == 0:
            self.finish_save(None, 'The engine did not produce a recording. Check the camera and recording log.')
            return
        self.remux(source)

    def remux(self, source):
        self.notice('Preparing your MP4. The original recording is safe.')
        self.record_button.setText('Preparing video…')
        target = source.with_suffix('.mp4')
        self.process = QProcess(self)
        self.process.setProgram('ffmpeg')
        self.process.setArguments(['-hide_banner', '-loglevel', 'error', '-n', '-i', str(source), '-map', '0', '-c', 'copy', '-movflags', '+faststart', str(target)])
        self.process.finished.connect(lambda code, status: self.remux_done(source, target, code))
        self.process.errorOccurred.connect(lambda error: self.remux_error(source, error))
        self.process.start()

    def remux_error(self, source, error):
        if error == QProcess.FailedToStart:
            self.finish_save(source, 'FFmpeg could not start. Your MKV recording is safe and can be played.')

    def remux_done(self, source, target, code):
        if code == 0 and target.exists() and target.stat().st_size:
            source.unlink()
            self.finish_save(target, self.recording_error)
        else:
            details = bytes(self.process.readAllStandardError()).decode(errors='replace')[-600:]
            # Never offer a partial MP4 or remove the recoverable original.
            if target.exists():
                target.unlink()
            self.finish_save(source, f'MP4 preparation failed. Your MKV is safe. {details}')

    def finish_save(self, path, error):
        emit(self, 'save.result', outcome='warning' if error else 'saved')
        self.busy = False
        self.record_button.setText('●  Start recording')
        self.record_button.setEnabled(self.configuration_valid)
        self.pause_button.setEnabled(True)
        self.tray_record.setEnabled(True)
        self.tray_record.setText('Start recording')
        self.tray.setToolTip('RecIt · Ready to record')
        self.lock_controls(False)
        if path and path.exists():
            self.set_last(path)
        self.notice(error or 'Saved. Play it back, or upload to Loom when you are ready.')
        if not error and self.prefs.value('auto_upload', False, type=bool):
            self.upload()
        if self.quit_after_save and not self.busy:
            self.close()

    def toggle_pause(self):
        if not self.recording or self.busy:
            return
        try:
            self.engine.pause(not self.paused)
            self.paused = not self.paused
            self.bubble.paused = self.paused
            if self.paused:
                self.pause_started = time.monotonic()
            else:
                self.paused_duration += time.monotonic() - self.pause_started
            self.pause_button.setText('Resume' if self.paused else 'Pause')
            self.tray_pause.setText('Resume' if self.paused else 'Pause')
        except Exception as exc:
            self.notice(f'Could not change pause state: {exc}')
            self.restore_capture_window()

    def open_audio_check(self):
        if (not self.engine or self.recording or self.counting or self.busy or
                self.preparing_audio or self.in_library() or self._closing or
                (self.audio_worker and self.audio_worker.isRunning())):
            return
        from audio_check import AudioCheck
        self.configure_timer.stop()
        self.start_timer.stop()
        self.idle_audio.stop()
        self.busy = True
        self.lock_controls(True)
        self.record_button.setEnabled(False)
        dialog = self.audio_check_dialog = AudioCheck(self.engine, self.audio_devices,
            self.microphone.currentData(), self.clean_microphone.isChecked(),
            self.microphone.currentText(), self)
        def finished():
            self.audio_check_dialog = None
            self.busy = False
            self.lock_controls(False)
            self.record_button.setEnabled(self.configuration_valid)
            dialog.deleteLater()
            self.retry_audio_restore()
            if self._configure_pending:
                self.configure_timer.start(0)
        dialog.finished.connect(finished)
        dialog.open()

    def release_audio(self):
        self.idle_audio.stop()
        if self.engine:
            self.engine.release_audio()
        owner = getattr(self, '_capture_owner', None)
        if owner is not None:
            self.audio_devices.release_capture(owner)
            self._capture_owner = None
        self.selected_source = None
        self.retry_audio_restore()

    def retry_audio_restore(self):
        if (self.idle_audio.owner is not None or getattr(self, 'audio_check_dialog', None) or self._closing or self.recording or self.preparing_audio or
                (self.audio_worker and self.audio_worker.isRunning())):
            return
        self._audio_retry_at = time.monotonic() + 3
        if self.audio_devices.lease:
            self.run_audio(self.audio_devices.restore, lambda result, error: None)

    def audio_checked(self, source, error):
        if error:
            emit(self, 'health.source_unavailable', level='warning', source=self.selected_source)
        if error and self.recording and not self.busy:
            self.recording_error = self.recording_error or f'Microphone disconnected or became unavailable. The recording was saved. {error}'
            self.stop()

    def microphone_warning(self):
        if self.paused or not self.selected_source:
            self._audio_warning_since = None
            return ''
        status = self.engine.audio_status()
        problem = status.get('state') if isinstance(status, dict) else None
        if problem not in ('no_packets', 'silent', 'off'):
            self._audio_warning_since = None
            return ''
        now = time.monotonic()
        previous = self._audio_warning_since
        if previous is None or previous[0] != problem:
            self._audio_warning_since = (problem, now)
            return ''
        if now - previous[1] < (15 if problem == 'silent' else 5):
            return ''
        emit(self, 'health.warning', every=5, level='warning', reason=problem, source=self.selected_source)
        warning = ('Microphone is sending only silence. Say a few words and check the meter.'
            if problem == 'silent' else 'Microphone samples stopped arriving. Check your microphone connection.')
        self.recording_error = self.recording_error or (warning + ' Review the audio before sharing.')
        return warning

    def update_microphone_meter(self):
        status = self.engine.audio_status() if self.engine else None
        source = status.get('source') if isinstance(status, dict) else None
        if self.idle_audio.source and not self.idle_audio.verified:
            status = None
            source = None
        index = self.microphone.findData(source) if source else -1
        name = self.microphone.itemText(index) if index >= 0 else source or 'Automatic microphone · preparing…'
        friendly = getattr(self.audio_devices, 'source_label', None)
        if source and isinstance(friendly, str) and friendly:
            name = friendly
        if not source and self.microphone.currentData() != 'default':
            name = self.microphone.currentText()
        self.microphone_meter.show_status(status, name, self.microphone.currentData() is not None)
        if not self.recording and not self.preparing_audio and not getattr(self, 'audio_check_dialog', None):
            if self.idle_audio.error:
                self.microphone_meter.message.setText('Monitor unavailable: ' + self.idle_audio.error)
            elif self.idle_audio.pending or (self.idle_audio.source and not self.idle_audio.verified):
                self.microphone_meter.message.setText('Preparing live microphone…')
            elif self.idle_audio.source:
                self.microphone_meter.message.setText('Live · ' + self.microphone_meter.message.text())
            elif not self.live_microphone.isChecked() and self.microphone.currentData():
                self.microphone_meter.message.setText('Live monitoring off')
        trace = getattr(self, 'audio_trace', None)
        if isinstance(trace, AudioTrace) and self.recording:
            trace.telemetry('health', status)

    def tick(self):
        self.idle_audio.reconcile()
        self.update_microphone_meter()
        audio_idle = not self.audio_worker or not self.audio_worker.isRunning()
        if (self.recording and not self.busy and self.selected_source and audio_idle
                and time.monotonic() >= getattr(self, '_recording_route_at', 0)):
            self._recording_route_at = time.monotonic() + .5
            source = self.selected_source
            generation = self._audio_generation
            self.run_audio(self.engine.verify_audio_route,
                lambda result, error: self.audio_checked(result, error)
                if generation == self._audio_generation and self.selected_source == source else None)
        elif not self.recording and audio_idle and time.monotonic() >= self._audio_retry_at:
            self.retry_audio_restore()
        if self.recording and not self.busy:
            if self.mode == 'screen' and self.capture_kind.currentData() == 'window' and not self.window_catalog.geometry(self.capture_window.currentData()):
                self.recording_error = self.recording_error or 'The selected window closed or was minimized. The recording was saved; review it before sharing.'
                self.stop()
                return
            if self.mode == 'screen' and self.capture_kind.currentData() == 'window':
                # Refit after a target-window resize, even while zoom is off.
                self.engine.set_screen_zoom(self.zoom_motion.factor, self.zoom_motion.x, self.zoom_motion.y)
            stats = self.engine.stats()
            if not stats.get('recording', True):
                self.notice('The recording engine stopped. Saving the recoverable recording…')
                self.stop()
                return
            elapsed = int((self.pause_started if self.paused else time.monotonic()) - self.started - self.paused_duration)
            duration = f'{elapsed // 60:02d}:{elapsed % 60:02d}'
            state = 'Paused' if self.paused else 'Recording'
            warning = self.microphone_warning()
            self.engine_notice(f'{state} · {duration}   |   Ctrl + Shift + F9 to stop and save\n'
                + (f'Microphone: {self.selected_source}' if self.selected_source else 'Microphone off')
                + ('\n' + (self.recording_error or warning) if self.recording_error or warning else ''))
            self.record_button.setText(f'■  Stop and save · {duration}')
            self.tray.setToolTip(f'RecIt · {state} {duration}\nCtrl + Shift + F9 to stop')
            if elapsed % 10 == 0 and shutil.disk_usage(VIDEOS).free < 256 * 1024 ** 2:
                self.notice('Storage almost full. Stopping to save your recording.')
                self.stop()

    def lock_controls(self, locked):
        self.live_microphone.setEnabled(not locked)
        self.audio_check_button.setEnabled(not locked)
        self.sharing_button.setEnabled(not locked)
        self.library_button.setEnabled(not locked)
        if locked and self.recordings:
            self.recordings.release()
            self.pages.setCurrentWidget(self.recorder_page)
        for widget in self.config_controls:
            widget.setEnabled(not locked)
        if not locked:
            self.screen.setEnabled(self.mode == 'screen')
            self.capture_kind.setEnabled(self.mode == 'screen')
            self.capture_window.setEnabled(self.mode == 'screen')
            self.refresh_button.setEnabled(self.mode == 'screen')
        if self.recordings:
            self.recordings.update_actions()

    def set_last(self, path):
        path = Path(path)
        self.last_file = path if path.is_file() else None

    def in_library(self):
        return self.pages.currentWidget() != self.recorder_page

    def back_to_recorder(self):
        if self.recordings:
            self.recordings.release()
        self.pages.setCurrentWidget(self.recorder_page)
        self.preview.show()
        self.tray_record.setEnabled(True)
        if self.engine:
            self.configure()
        # Qt must finish showing/resizing the native parent before GLX creates
        # its child. A later navigation invalidates this queued restoration.
        generation = self._preview_generation = getattr(self, '_preview_generation', 0) + 1
        QTimer.singleShot(0, lambda: self.restore_preview(generation))

    def restore_preview(self, generation):
        if (self._closing or generation != getattr(self, '_preview_generation', 0) or
                self.in_library()):
            return
        if not self.engine:
            self.initialize()
            return
        try:
            ratio = self.preview.devicePixelRatioF()
            self.engine.attach_preview(int(self.preview.winId()),
                round(self.preview.width() * ratio), round(self.preview.height() * ratio))
        except Exception as exc:
            self.notice(f'Could not restore the preview: {exc}')

    def open_recordings(self, path=None):
        if self.recording or self.counting or self.busy:
            return
        if self.recordings is None:
            self.recordings = Recordings(VIDEOS, self,
                deletion_blocked=lambda path: self.recording or self.counting or self.busy)
            self.recordings.recording_deleted.connect(self.recording_deleted)
            self.recordings.recording_renamed.connect(self.recording_renamed)
            self.recordings.upload_requested.connect(self.upload_recording)
            self.recordings.back_requested.connect(self.back_to_recorder)
            self.pages.addWidget(self.recordings)
        self.configure_timer.stop()
        self.start_timer.stop()
        self._preview_generation = getattr(self, '_preview_generation', 0) + 1
        self.hide_bubble()
        self.release_audio()
        if self.engine:
            self.engine.detach_preview()
        self.preview.hide()
        self.pages.setCurrentWidget(self.recordings)
        self.tray_record.setEnabled(False)
        self.recordings.search.clear()
        self.recordings.refresh(path)

    def recording_renamed(self, old_path, new_path):
        if self.last_file is not None and Path(old_path) == self.last_file:
            self.set_last(new_path)

    def recording_deleted(self, path):
        if self.last_file is None or Path(path) != self.last_file:
            return
        paths = recording_files(VIDEOS)
        if paths:
            self.set_last(paths[0])
            return
        self.last_file = None

    def upload_recording(self, path):
        if self.busy or self.recording or self.counting or self._closing:
            return
        self.set_last(path)
        if self.last_file is None:
            self.recordings.update_actions()
            self.recordings.message.setText('This recording is missing. Refresh the list.')
            return
        self.back_to_recorder()
        self.upload()

    def sharing_settings(self):
        if self.busy or self.recording or self.counting:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('RecIt · Sharing')
        dialog.setMinimumWidth(540)
        dialog.resize(580, 740)
        outer = QVBoxLayout(dialog)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label('LOOM', 'eyebrow'))
        text = label('RecIt saves locally first. Loom uploads use Atlassian’s official Teamwork Graph CLI and your signed-in account.')
        text.setWordWrap(True)
        layout.addWidget(text)
        self.cli_status = label('Checking Loom connection…', 'muted')
        self.cli_status.setWordWrap(True)
        cli = self.find_cli()
        self.cli_status.setText('TWG CLI is installed; account sign-in has not been checked. Connect below using browser OAuth. Uploads require Business, Business + AI, or Enterprise, excluding trials.' if cli else 'Install Atlassian’s TWG CLI, then connect your account. Uploads require Business, Business + AI, or Enterprise, excluding trials.')
        layout.addWidget(self.cli_status)
        connect = QPushButton('Connect Loom account ↗')
        connect.setEnabled(bool(cli))
        connect.clicked.connect(self.connect_loom)
        layout.addWidget(connect)
        layout.addWidget(label('Who can watch uploaded videos?', 'section'))
        visibility = QComboBox()
        for title, value in [('Only me', 'owner'), ('My Loom workspace', 'workspace'), ('Anyone with the link', 'public')]:
            visibility.addItem(title, value)
        visibility.setCurrentIndex(max(0, visibility.findData(self.prefs.value('visibility', 'owner'))))
        layout.addWidget(visibility)
        auto = QCheckBox('Upload automatically after I stop recording')
        auto.setChecked(self.prefs.value('auto_upload', False, type=bool))
        auto.setEnabled(bool(cli))
        layout.addWidget(auto)
        docs = QPushButton('Open Loom connection instructions ↗')
        docs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://developer.atlassian.com/cloud/twg-cli/')))
        layout.addWidget(docs)
        privacy = label('RecIt applies this choice after upload. Your Loom account’s defaults apply while uploading. “Anyone with the link” allows people who receive the link to watch.', 'muted')
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        done = QPushButton('Done')
        done.clicked.connect(dialog.accept)
        layout.addWidget(done)
        if dialog.exec():
            self.prefs.setValue('auto_upload', auto.isChecked())
            self.prefs.setValue('visibility', visibility.currentData())

    def connect_loom(self):
        cli = self.find_cli()
        if not cli:
            self.notice('Install the official TWG CLI using Sharing instructions, then connect Loom.')
            return
        terminal = shutil.which('gnome-terminal')
        command = [terminal, '--', 'bash', str(ROOT / 'connect-loom.sh'), cli] if terminal else ['x-terminal-emulator', '-e', 'bash', str(ROOT / 'connect-loom.sh'), cli]
        try:
            subprocess.Popen(command, start_new_session=True)
            self.notice('Complete consent and browser OAuth sign-in in the terminal, then return here. No video is uploaded by connecting.')
        except OSError as exc:
            self.notice(f'Could not open the sign-in terminal: {exc}')

    @staticmethod
    def find_cli():
        for path in [shutil.which('twg'), str(Path.home() / '.local/bin/twg'), str(Path.home() / '.local/share/glint/twg')]:
            if path and Path(path).is_file() and os.access(path, os.X_OK):
                return path
        return None

    def upload(self):
        if not self.last_file or self.busy or self.recording or self.counting or self._closing:
            return
        try:
            size = self.last_file.stat().st_size
            if not self.last_file.is_file() or not os.access(self.last_file, os.R_OK):
                raise OSError('unreadable file')
        except OSError:
            self.notice('The local recording is missing or unreadable. Choose an existing video before uploading.')
            return
        if size == 0:
            self.notice('This recording is empty. Nothing was uploaded.')
            return
        if self.last_file.suffix == '.mkv':
            if self.last_file.with_suffix('.mp4').exists():
                self.notice('An MP4 with this name already exists. Review it in Recordings before preparing this MKV. Both files are preserved.')
                return
            self.busy = True
            self.lock_controls(True)
            self.record_button.setEnabled(False)
            self.recording_error = 'Recovered the original recording. Play it back before uploading to Loom.'
            self.remux(self.last_file)
            return
        cli = self.find_cli()
        if not cli:
            self.sharing_settings()
            return
        if size >= 4 * 1024 ** 3:
            self.notice('This video exceeds Loom’s 4 GB upload limit. The local file is saved.')
            return
        self.busy = True
        self.lock_controls(True)
        self.record_button.setEnabled(False)
        self._upload_cli = cli
        self._upload_file = self.last_file.resolve()
        self._upload_visibility = self.prefs.value('visibility', 'owner')
        if self._upload_visibility not in ('owner', 'workspace', 'public'):
            self._upload_visibility = 'owner'
        self._upload_url = None
        self.notice('Uploading to Loom… Your local copy stays safe.')
        self.process = QProcess(self)
        self.process.setProgram(cli)
        # CLI command syntax is probed before upload; do not rely on undocumented flags.
        self.process.setArguments(['loom', 'video', 'upload', '--help'])
        self.process.finished.connect(self.upload_help)
        self.process.errorOccurred.connect(self.upload_process_error)
        self.process.start()

    def upload_process_error(self, error):
        if error == QProcess.FailedToStart:
            if getattr(self, '_upload_url', None):
                self.upload_end('Uploaded, but the sharing command could not start. Review permissions in Loom before sharing. Your local file is saved.')
            else:
                self.upload_end('Could not start the Loom CLI. Your local file is saved.')

    def upload_help(self, code, status):
        help_text = bytes(self.process.readAllStandardOutput()).decode(errors='replace') + bytes(self.process.readAllStandardError()).decode(errors='replace')
        if code != 0 or status != QProcess.NormalExit:
            self.upload_end('This TWG CLI does not support video uploads. Update it and connect your Loom account.')
            return
        # Versioned CLI accepts either --file or a positional file. Refuse unknown grammar.
        if '--file' in help_text:
            file_args = ['--file', str(self._upload_file)]
        elif '<file>' in help_text.lower() or '<path>' in help_text.lower():
            file_args = [str(self._upload_file)]
        else:
            self.upload_end('Upload syntax could not be verified. Open Sharing for connection instructions.')
            return
        self.process = QProcess(self)
        self.process.setProgram(self._upload_cli)
        self._upload_sets_visibility = '--visibility' in help_text
        args = ['loom', 'video', 'upload', *file_args, '-o', 'json']
        if self._upload_sets_visibility:
            args += ['--visibility', self._upload_visibility]
        self.process.setArguments(args)
        self.process.finished.connect(self.upload_done)
        self.process.errorOccurred.connect(self.upload_process_error)
        self.process.start()

    def upload_done(self, code, status):
        output = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        errors = bytes(self.process.readAllStandardError()).decode(errors='replace')
        import re
        urls = re.findall(r'https://(?:www\.)?loom\.com/share/[a-zA-Z0-9]+', output)
        if code == 0 and status == QProcess.NormalExit and urls:
            self._upload_url = urls[-1]
            if not getattr(self, '_upload_sets_visibility', False):
                self.notice('Uploaded. Applying your Loom sharing setting…')
                self.process = QProcess(self)
                self.process.setProgram(self._upload_cli)
                self.process.setArguments(['loom', 'video', 'visibility', 'set', urls[-1], '--visibility', self._upload_visibility, '-o', 'json'])
                self.process.finished.connect(self.visibility_done)
                self.process.errorOccurred.connect(self.upload_process_error)
                self.process.start()
                return
            QApplication.clipboard().setText(urls[-1])
            self.upload_end('Uploaded to Loom. The link is copied to your clipboard.')
        elif code == 0 and status == QProcess.NormalExit:
            self.upload_end('Upload command completed without a Loom link. Check your library and permissions before sharing or retrying.')
        else:
            # CLI diagnostics can include credentials or private account details.
            detail = (errors or output).lower()
            if any(word in detail for word in ('oauth', 'login', 'unauthorized', 'authentication', 'token')):
                advice = 'Open Sharing and connect your Loom account again.'
            elif any(word in detail for word in ('plan', 'upgrade', 'subscription', 'trial')):
                advice = 'Uploads require Business, Business + AI, or Enterprise, excluding Business + AI trials.'
            else:
                advice = 'Check your connection, Loom plan, and account permissions. A failed command may leave a remote video; check your library before retrying.'
            self.upload_end('Loom upload failed. Your local recording is safe. ' + advice)

    def visibility_done(self, code, status):
        if code == 0 and status == QProcess.NormalExit:
            QApplication.clipboard().setText(self._upload_url)
            self.upload_end('Uploaded to Loom. Sharing setting applied. Link copied.')
        else:
            self.upload_end('Uploaded, but Loom could not apply the sharing setting. Review permissions in Loom before sharing the link.')

    def upload_end(self, text):
        self.busy = False
        self.lock_controls(False)
        self.record_button.setEnabled(bool(self.engine) and self.configuration_valid)
        self.notice(text)
        if self.quit_after_save:
            self.close()

    def engine_notice(self, text):
        warnings = getattr(self.engine, 'warnings', [])
        if isinstance(warnings, (list, tuple)):
            messages = [warning for warning in warnings if isinstance(warning, str) and warning.strip()]
            if messages:
                text += '\n' + '\n'.join(messages)
        self.notice(text)

    def notice(self, text):
        self.status.setText(text)

    def restore_capture_window(self):
        # Only undo our screen-capture hide. Camera callbacks must leave the
        # user's current visibility/state alone and must not request focus.
        state = self._capture_window_state
        self._capture_window_state = None
        if state is not None and not self._closing:
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            try:
                self.setWindowState(state)
                self.show()
            finally:
                self.setAttribute(Qt.WA_ShowWithoutActivating, False)

    def reveal(self):
        # Explicit tray/bubble/launcher requests may unminimize, but must keep
        # maximization. They also supersede a pending capture restoration.
        self._capture_window_state = None
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def record_icon():
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor('#f8957e'))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()
        return QIcon(pix)

    def hideEvent(self, event):
        if not (self.recording or self.counting or self.preparing_audio):
            self.idle_audio.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        if getattr(self, 'audio_check_dialog', None):
            self.audio_check_dialog.reject()
            event.ignore()
            return
        if self.counting:
            self.cancel_countdown()
        if self.recording:
            answer = QMessageBox.question(self, 'Save your recording?', 'Stop recording, save the video, and quit RecIt?', QMessageBox.Save | QMessageBox.Cancel, QMessageBox.Cancel)
            event.ignore()
            if answer == QMessageBox.Save:
                self.quit_after_save = True
                self.stop()
            return
        if self.busy and not self.preparing_audio:
            self.notice('Finishing your video. RecIt will stay open until it is safe to close.')
            event.ignore()
            return
        self._closing = True
        self._audio_generation += 1
        if self.audio_worker:
            self.audio_worker.wait()
            self.audio_worker = None
        self.busy = self.preparing_audio = False
        self.idle_audio.stop()
        self.idle_audio.release_owner()
        if self.recordings:
            self.recordings.release()
        self._preview_generation = getattr(self, '_preview_generation', 0) + 1
        self.configure_timer.stop()
        self.start_timer.stop()
        self.zoom_timer.stop()
        self.hide_bubble()
        self.bubble.close()
        self.window_catalog.close()
        self.save_preferences()
        self.hotkeys.requestInterruption()
        self.hotkeys.wait(1500)
        self.tray.hide()
        if self.engine:
            self.engine.close()
            self.engine = None
        owner = getattr(self, '_capture_owner', None)
        if owner is not None:
            self.audio_devices.release_capture(owner)
            self._capture_owner = None
        try:
            self.audio_devices.restore()
        except AudioDeviceError:
            pass  # Never force restoration while another client owns streams.
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('RecIt')
    app.setDesktopFileName('tech.truedevs.RecIt')
    app.setWindowIcon(QIcon(str(ICON)))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtCore import QLockFile, QStandardPaths
    runtime = Path(QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation))
    runtime.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(runtime / 'truedevs-glint.lock'))
    owns_lock = instance_lock.tryLock(0)
    socket = QLocalSocket()
    if not owns_lock:
        for attempt in range(10):
            socket.abort()
            socket.connectToServer('truedevs-glint-' + str(os.getuid()))
            if socket.waitForConnected(300):
                socket.write(b'open')
                socket.waitForBytesWritten(300)
                break
            time.sleep(.1)
        return 0
    QLocalServer.removeServer('truedevs-glint-' + str(os.getuid()))
    server = QLocalServer()
    if not server.listen('truedevs-glint-' + str(os.getuid())):
        raise RuntimeError('Could not open RecIt’s local activation socket: ' + server.errorString())
    window = Window()
    def activate():
        client = server.nextPendingConnection()
        if client:
            client.disconnectFromServer()
            client.deleteLater()
        window.reveal()
    server.newConnection.connect(activate)
    window.show()
    signal.signal(signal.SIGINT, lambda *_: window.close())
    signal.signal(signal.SIGTERM, lambda *_: window.close())
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
