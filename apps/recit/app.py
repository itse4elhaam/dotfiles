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
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QCheckBox, QFileDialog, QFrame,
    QSystemTrayIcon, QMenu, QMessageBox, QSizePolicy, QDialog, QLineEdit,
)

ROOT = Path(__file__).resolve().parent
ICON = ROOT / 'assets/recit-mark.svg'
VIDEOS = Path.home() / 'Videos/RecIt'
STATE = Path.home() / '.local/state/glint'
STYLE = """
QWidget { background: #111b20; color: #eef1ec; font-family: 'Inter', 'DejaVu Sans'; font-size: 13px; }
QMainWindow { background: #111b20; }
QLabel { background: transparent; }
QLabel#muted { color: #9aadae; font-size: 12px; }
QLabel#eyebrow { color: #9ddbc4; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLabel#section { font-size: 12px; font-weight: 600; color: #b7c5c4; }
QFrame#panel { background: #18252b; border: 1px solid #2a3a40; border-radius: 16px; }
QPushButton { background: #223239; border: 1px solid #35464c; padding: 10px 15px; border-radius: 9px; font-weight: 600; }
QPushButton:hover { background: #2d4148; border-color: #819a9b; }
QPushButton:checked { background: #28463e; border-color: #9ddbc4; color: #c5f2df; }
QPushButton:disabled { color: #617477; border-color: #26363c; background: #1b2a30; }
QPushButton#record { background: #f8957e; color: #172329; border: none; padding: 16px; font-size: 15px; }
QPushButton#record:hover { background: #ffae97; }
QPushButton#record:disabled { background: #634b46; color: #ab9490; }
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
        data = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sources'], timeout=3))
        return [(s.get('description', s['name']), s['name']) for s in data if not s['name'].endswith('.monitor')]
    except (OSError, ValueError, subprocess.SubprocessError):
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
    def run(self):
        try:
            self.engine.stop()
            self.finished_file.emit(str(self.path), '')
        except Exception as exc:
            self.finished_file.emit(str(self.path), str(exc))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('RecIt')
        self.setWindowIcon(QIcon(str(ICON)))
        self.resize(1120, 840)
        self.setMinimumSize(960, 760)
        self.prefs = QSettings('TrueDevs', 'Glint')  # Preserve existing preferences.
        self.engine = None
        self.recording = False
        self.paused = False
        self.busy = False
        self.counting = False
        self.mode = 'screen'
        self.mask_path = self.prefs.value('mask', '')
        self.last_file = None
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
        self.timer.start(500)
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
        container = QWidget()
        self.setCentralWidget(container)
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
        self.library_button = QPushButton('Recordings ↗')
        self.library_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(VIDEOS))))
        header.addWidget(self.library_button)
        settings = QPushButton('Sharing')
        settings.clicked.connect(self.sharing_settings)
        header.addWidget(settings)
        layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(22)
        controls = QVBoxLayout()
        controls.setSpacing(9)
        side = QWidget()
        side.setFixedWidth(300)
        side.setLayout(controls)
        controls.addWidget(label('MAKE YOURSELF CLEAR', 'eyebrow'))
        modes = QHBoxLayout()
        self.screen_button = QPushButton('▣  Loom')
        self.camera_button = QPushButton('◉  Camera')
        for button, mode in [(self.screen_button, 'screen'), (self.camera_button, 'camera')]:
            button.setCheckable(True)
            button.setMinimumHeight(54)
            button.clicked.connect(lambda checked, m=mode: self.set_mode(m))
            modes.addWidget(button)
        controls.addLayout(modes)
        self.mode_hint = label('Your screen, with you in the corner.', 'muted')
        controls.addWidget(self.mode_hint)
        controls.addSpacing(6)
        controls.addWidget(label('Capture', 'section'))
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
        self.microphone.addItem('Default microphone', 'default')
        self.microphone.addItem('Microphone off', None)
        for name, source in microphones():
            self.microphone.addItem(name, source)
        controls.addWidget(self.microphone)
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
        controls.addStretch()
        content.addWidget(side)

        right = QVBoxLayout()
        right.setSpacing(12)
        preview_top = QHBoxLayout()
        preview_top.addWidget(label('LIVE PREVIEW', 'eyebrow'))
        preview_top.addStretch()
        self.encoder_label = label('Starting recording engine…', 'muted')
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
        self.record_button = QPushButton('●  Start recording')
        self.record_button.setObjectName('record')
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.toggle_record)
        actions.addWidget(self.record_button, 1)
        self.pause_button = QPushButton('Pause')
        self.pause_button.setVisible(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        actions.addWidget(self.pause_button)
        right.addLayout(actions)
        right.addWidget(label('Ctrl + Shift + F9  record / stop    ·    F10  pause    ·    F8  pointer zoom', 'muted'))
        self.recent = QFrame()
        self.recent.setObjectName('panel')
        recent_layout = QVBoxLayout(self.recent)
        recent_layout.setContentsMargins(16, 14, 16, 14)
        recent_layout.addWidget(label('YOUR LAST RECORDING', 'eyebrow'))
        self.recent_name = label('Your next explanation starts here.', 'muted')
        self.recent_name.setWordWrap(True)
        recent_layout.addWidget(self.recent_name)
        recent_actions = QHBoxLayout()
        self.play_button = QPushButton('Play')
        self.play_button.clicked.connect(self.play)
        self.upload_button = QPushButton('Upload to Loom')
        self.upload_button.clicked.connect(self.upload)
        self.copy_button = QPushButton('Copy file path')
        self.copy_button.clicked.connect(self.copy_path)
        for button in (self.play_button, self.upload_button, self.copy_button):
            button.setEnabled(False)
            recent_actions.addWidget(button)
        recent_layout.addLayout(recent_actions)
        right.addWidget(self.recent)
        content.addLayout(right, 1)
        layout.addLayout(content, 1)
        self.config_controls = [self.screen_button, self.camera_button, self.capture_kind, self.capture_window, self.refresh_button, self.screen, self.camera, self.microphone, self.desktop_audio, self.shape, self.size, self.position, self.mask_button, self.mirror, self.quality]
        for combo in (self.screen, self.capture_window, self.camera, self.microphone, self.position):
            combo.currentIndexChanged.connect(self.schedule_configure)
        self.capture_kind.currentIndexChanged.connect(self.capture_changed)
        self.shape.currentIndexChanged.connect(self.shape_changed)
        self.size.valueChanged.connect(self.schedule_configure)
        self.mirror.toggled.connect(self.schedule_configure)
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
        self.size.setValue(int(self.prefs.value('size', 23)))
        self.mirror.setChecked(self.prefs.value('mirror', True, type=bool))
        self.desktop_audio.setChecked(self.prefs.value('desktop_audio', False, type=bool))
        self.set_mode(self.prefs.value('mode', 'screen'), configure=False)
        files = sorted([*VIDEOS.glob('RecIt-*.mp4'), *VIDEOS.glob('RecIt-*.mkv'), *VIDEOS.glob('Glint-*.mp4'), *VIDEOS.glob('Glint-*.mkv')], key=lambda p: p.stat().st_mtime)
        if files:
            self.set_last(files[-1])

    def save_preferences(self):
        for name in ('camera', 'microphone', 'shape', 'position', 'quality'):
            self.prefs.setValue(name, getattr(self, name).currentText())
        self.prefs.setValue('size', self.size.value())
        self.prefs.setValue('mirror', self.mirror.isChecked())
        self.prefs.setValue('desktop_audio', self.desktop_audio.isChecked())
        self.prefs.setValue('mode', self.mode)
        self.prefs.setValue('mask', self.mask_path)
        self.prefs.sync()

    def initialize(self):
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
        self.widget_panel.setVisible(self.mode == 'screen')
        self.screen.setEnabled(self.mode == 'screen')
        self.capture_kind.setEnabled(self.mode == 'screen')
        self.capture_window.setEnabled(self.mode == 'screen')
        self.refresh_button.setEnabled(self.mode == 'screen')
        self.mode_hint.setText('Your screen, with you in the corner.' if self.mode == 'screen' else 'Just you. Full frame. Ready to explain.')
        if configure:
            self.schedule_configure()

    def capture_changed(self):
        window_mode = self.capture_kind.currentData() == 'window'
        self.screen.setVisible(not window_mode)
        self.window_row.setVisible(window_mode)
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

    def configure(self):
        if not self.engine or self.recording or self.busy:
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
            self.engine.configure(mode=self.mode, camera=camera, microphone=self.microphone.currentData(),
                desktop_audio=self.desktop_audio.isChecked(), shape=self.shape.currentData(),
                mask_path=self.mask_path or None, size=self.size.value() / 100,
                position=self.position.currentData(), screen=self.screen.currentData() or 0,
                mirror=self.mirror.isChecked(), floating_camera=self.mode == 'screen' and bool(camera) and not window_id, window_id=window_id)
            if self.mode == 'screen' and camera:
                self.show_bubble()
            self.record_button.setEnabled(True)
            self.configuration_valid = True
            self.notice('Ready when you are. Your recording stays on this computer until you upload it.')
            self.encoder_label.setText('OBS engine · Intel hardware available')
            screen = QApplication.screens()[self.screen.currentIndex()]
            geo = screen.geometry()
            ratio = screen.devicePixelRatio()
            self.source_note.setText(f'{self.quality.currentText()} output · Display source {round(geo.width() * ratio)} × {round(geo.height() * ratio)}. '
                + ('Source resolution determines actual detail.' if camera else 'Camera is off.'))
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
        self.bubble.hide()
        if self.engine:
            self.engine.detach_camera_preview()

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
        self.countdown -= 1
        if self.countdown:
            self.record_button.setText(f'Cancel · {self.countdown}')
            self.notice(f'Starting in {self.countdown}… Esc cancels.')
        else:
            self.count_timer.stop()
            # Hide before capture starts, avoiding the preview recursion in the recording.
            if self.mode == 'screen':
                self.hide()
            self.start_timer.start(250)

    def cancel_countdown(self):
        if self.counting:
            self.count_timer.stop()
            self.start_timer.stop()
            self.counting = False
            self.lock_controls(False)
            self.record_button.setText('●  Start recording')
            self.notice('Countdown cancelled. Ready when you are.')
            self.reveal()

    def start(self):
        if self.busy or self.recording or not self.counting or not self.configuration_valid:
            return
        self.counting = False
        try:
            if self.mode == 'screen' and self.capture_kind.currentData() == 'window' and not self.window_catalog.geometry(self.capture_window.currentData()):
                raise RuntimeError('The selected window is no longer available. Choose an open window and try again.')
            if shutil.disk_usage(VIDEOS).free < 1024 ** 3:
                raise RuntimeError('Less than 1 GB free. Make some room before recording.')
            stamp = time.strftime('%Y-%m-%d-%H%M%S')
            self.record_path = VIDEOS / f'RecIt-{stamp}-{time.time_ns() % 1000000:06d}.mkv'
            self.recording_error = ''
            self.recording_error_baseline = len(self.engine.errors)
            self.engine.start(self.record_path)
            encoder = self.engine.stats().get('encoder', '')
            self.encoder_label.setText('Intel hardware · H.264' if encoder == 'ffmpeg_vaapi' else 'CPU encoding · H.264')
            self.started = time.monotonic()
            self.paused_duration = 0
            self.paused = False
            self.recording = True
            self.bubble.recording = True
            self.zoom_button.setEnabled(self.mode == 'screen')
            self.tray_zoom.setEnabled(self.mode == 'screen')
            self.record_button.setText('■  Stop and save')
            self.pause_button.setVisible(True)
            self.pause_button.setText('Pause')
            self.tray_pause.setEnabled(True)
            self.tray_record.setText('Stop and save')
            self.tray.setIcon(self.record_icon())
            self.notice('Recording. Ctrl + Shift + F9 stops and saves.')
            if self.mode == 'screen':
                self.tray.setToolTip('RecIt · Recording\nF9 stop · F10 pause · F8 zoom\nHold Ctrl + Shift with each key')
        except Exception as exc:
            self.lock_controls(False)
            self.record_button.setText('●  Start recording')
            self.notice(f'Could not start recording: {exc}')
            self.reveal()

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
            self.reveal()
            return
        engine_errors = self.engine.errors[self.recording_error_baseline:]
        if engine_errors:
            self.recording_error = 'Recording ended with an error. Review the saved video before sharing. ' + '; '.join(engine_errors)
        self.recording = False
        self.paused = False
        self.bubble.recording = False
        self.bubble.paused = False
        self.reset_zoom()
        self.tray.setIcon(QIcon(str(ICON)))
        self.tray.setToolTip('RecIt · Saving recording')
        self.reveal()
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
            self.reveal()

    def tick(self):
        if self.recording and not self.busy:
            if self.mode == 'screen' and self.capture_kind.currentData() == 'window' and not self.window_catalog.geometry(self.capture_window.currentData()):
                self.recording_error = 'The selected window closed or was minimized. The recording was saved; review it before sharing.'
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
            self.status.setText(f'{state} · {duration}   |   Ctrl + Shift + F9 to stop and save')
            self.record_button.setText(f'■  Stop and save · {duration}')
            self.tray.setToolTip(f'RecIt · {state} {duration}\nCtrl + Shift + F9 to stop')
            if elapsed % 10 == 0 and shutil.disk_usage(VIDEOS).free < 256 * 1024 ** 2:
                self.notice('Storage almost full. Stopping to save your recording.')
                self.stop()

    def lock_controls(self, locked):
        for widget in self.config_controls:
            widget.setEnabled(not locked)
        if not locked:
            self.screen.setEnabled(self.mode == 'screen')
            self.capture_kind.setEnabled(self.mode == 'screen')
            self.capture_window.setEnabled(self.mode == 'screen')
            self.refresh_button.setEnabled(self.mode == 'screen')
        for button in (self.play_button, self.upload_button, self.copy_button):
            button.setEnabled(not locked and bool(self.last_file))

    def set_last(self, path):
        self.last_file = path
        self.recent_name.setText(f'{path.name}\n{path.stat().st_size / 1024 ** 2:.1f} MB · Saved in Videos/RecIt')
        for button in (self.play_button, self.upload_button, self.copy_button):
            button.setEnabled(True)
        self.copy_button.setText('Copy file path')
        self.copy_button.setProperty('url', None)
        self.upload_button.setText('Prepare MP4' if path.suffix == '.mkv' else 'Upload to Loom')

    def play(self):
        if self.last_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_file)))

    def copy_path(self):
        value = self.copy_button.property('url') or str(self.last_file or '')
        QApplication.clipboard().setText(value)
        self.notice('Link copied.' if self.copy_button.property('url') else 'File path copied. This is a local file, not a public link.')

    def sharing_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('RecIt · Sharing')
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label('STRAIGHT TO LOOM', 'eyebrow'))
        text = label('RecIt saves locally first. Loom uploads use Atlassian’s official Teamwork Graph CLI and your signed-in account.')
        text.setWordWrap(True)
        layout.addWidget(text)
        self.cli_status = label('Checking Loom connection…', 'muted')
        self.cli_status.setWordWrap(True)
        cli = self.find_cli()
        self.cli_status.setText('The Loom connector is installed. Connect your account below. Your Loom plan must support uploads.' if cli else 'Loom sharing is not connected yet. Install Atlassian’s TWG CLI, then connect your account. Your Loom plan must support uploads.')
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
        terminal = shutil.which('gnome-terminal')
        command = [terminal, '--', 'bash', str(ROOT / 'connect-loom.sh')] if terminal else ['x-terminal-emulator', '-e', 'bash', str(ROOT / 'connect-loom.sh')]
        try:
            subprocess.Popen(command, start_new_session=True)
        except OSError as exc:
            self.notice(f'Could not open the sign-in terminal: {exc}')

    @staticmethod
    def find_cli():
        for path in [shutil.which('twg'), str(Path.home() / '.local/bin/twg'), str(Path.home() / '.local/share/glint/twg')]:
            if path and os.access(path, os.X_OK):
                return path
        return None

    def upload(self):
        if not self.last_file or self.busy or self.recording:
            return
        if self.last_file.suffix == '.mkv':
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
        if self.last_file.stat().st_size >= 4 * 1024 ** 3:
            self.notice('This video exceeds Loom’s 4 GB upload limit. The local file is saved.')
            return
        self.busy = True
        self.lock_controls(True)
        self.record_button.setEnabled(False)
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
            self.upload_end('Could not start the Loom CLI. Your local file is saved.')

    def upload_help(self, code, status):
        help_text = bytes(self.process.readAllStandardOutput()).decode(errors='replace') + bytes(self.process.readAllStandardError()).decode(errors='replace')
        if code != 0:
            self.upload_end('This TWG CLI does not support video uploads. Update it and connect your Loom account.')
            return
        # Versioned CLI accepts either --file or a positional file. Refuse unknown grammar.
        if '--file' in help_text:
            file_args = ['--file', str(self.last_file)]
        elif '<file>' in help_text.lower() or '<path>' in help_text.lower():
            file_args = [str(self.last_file)]
        else:
            self.upload_end('Upload syntax could not be verified. Open Sharing for connection instructions.')
            return
        self.process = QProcess(self)
        self.process.setProgram(self.find_cli())
        self._upload_sets_visibility = '--visibility' in help_text
        args = ['loom', 'video', 'upload', *file_args, '-o', 'json']
        if self._upload_sets_visibility:
            args += ['--visibility', self.prefs.value('visibility', 'owner')]
        self.process.setArguments(args)
        self.process.finished.connect(self.upload_done)
        self.process.errorOccurred.connect(self.upload_process_error)
        self.process.start()

    def upload_done(self, code, status):
        output = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        errors = bytes(self.process.readAllStandardError()).decode(errors='replace')
        import re
        urls = re.findall(r'https://(?:www\.)?loom\.com/share/[a-zA-Z0-9]+', output)
        if code == 0 and urls:
            self.copy_button.setProperty('url', urls[-1])
            self.copy_button.setText('Copy Loom link')
            if not getattr(self, '_upload_sets_visibility', False):
                self.notice('Uploaded. Applying your Loom sharing setting…')
                self.process = QProcess(self)
                self.process.setProgram(self.find_cli())
                self.process.setArguments(['loom', 'video', 'visibility', 'set', urls[-1], '--visibility', self.prefs.value('visibility', 'owner'), '-o', 'json'])
                self.process.finished.connect(self.visibility_done)
                self.process.errorOccurred.connect(self.upload_process_error)
                self.process.start()
                return
            QApplication.clipboard().setText(urls[-1])
            self.upload_end('Uploaded to Loom. The link is copied to your clipboard.')
        elif code == 0:
            self.upload_end('Upload completed. Open your Loom library to get the link.')
        else:
            self.upload_end('Loom upload failed. Your local recording is safe. ' + (errors or output)[-400:])

    def visibility_done(self, code, status):
        if code == 0:
            QApplication.clipboard().setText(self.copy_button.property('url'))
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

    def notice(self, text):
        self.status.setText(text)

    def reveal(self):
        self.showNormal()
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

    def closeEvent(self, event):
        if self.counting:
            self.cancel_countdown()
        if self.recording:
            answer = QMessageBox.question(self, 'Save your recording?', 'Stop recording, save the video, and quit RecIt?', QMessageBox.Save | QMessageBox.Cancel, QMessageBox.Cancel)
            event.ignore()
            if answer == QMessageBox.Save:
                self.quit_after_save = True
                self.stop()
            return
        if self.busy:
            self.notice('Finishing your video. RecIt will stay open until it is safe to close.')
            event.ignore()
            return
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
