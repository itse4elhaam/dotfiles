"""Local recordings browser using Qt's native media player."""
from datetime import datetime
from pathlib import Path
from naming import recording_title, recording_files, rename_recording

from PySide6.QtCore import Qt, QUrl, Signal, QSize, QSignalBlocker
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QWidget, QFrame, QSplitter, QStackedWidget, QLineEdit, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSlider, QVBoxLayout, QApplication, QMessageBox, QInputDialog, QStyle, QStyleOptionSlider,
)


class PlaybackSlider(QSlider):
    """Let a click on the track select a position, as well as dragging."""
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
            if not handle.contains(event.position().toPoint()):
                span = self.width() - handle.width()
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), round(event.position().x() - handle.width() / 2),
                    span, option.upsideDown))
                event.accept()
                return
        super().mousePressEvent(event)


def timestamp(milliseconds):
    seconds = milliseconds // 1000
    return f'{seconds // 60}:{seconds % 60:02d}'


class Recordings(QWidget):
    back_requested = Signal()
    recording_deleted = Signal(str)
    recording_renamed = Signal(str, str)
    upload_requested = Signal(str)

    def __init__(self, directory, parent=None, deletion_blocked=None):
        super().__init__(parent)
        self.directory = Path(directory)
        self.deletion_blocked = deletion_blocked or (lambda path: False)
        self.setObjectName('recordingsPage')
        self.setStyleSheet("""
            QListWidget { background: #111b20; border: none; outline: none; }
            QListWidget::item { background: #18252b; border: 1px solid #2a3a40;
                border-radius: 12px; margin: 0 6px 10px 0; padding: 16px; }
            QListWidget::item:hover { background: #223239; }
            QListWidget::item:selected { background: #28463e; border-color: #9ddbc4; color: #c5f2df; }
            QSplitter::handle { background: transparent; }
            QPushButton#playRecording { background: #9ddbc4; color: #172329; }
            QPushButton#playRecording:disabled { background: #223239; color: #617477; }
        """)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.5)
        self.player.setAudioOutput(self.audio)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(18)
        header = QHBoxLayout()
        self.back = QPushButton('←  Back to recorder')
        self.back.clicked.connect(self.reject)
        header.addWidget(self.back)
        header.addStretch()
        privacy = QLabel('LOCAL LIBRARY  ·  Only on this computer')
        privacy.setObjectName('eyebrow')
        header.addWidget(privacy)
        layout.addLayout(header)
        title = QLabel('Your recordings')
        title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel('A place for everything you have shown, explained, and shared.')
        subtitle.setObjectName('muted')
        layout.addWidget(subtitle)
        body = self.body = QSplitter(Qt.Horizontal)
        body.setHandleWidth(12)
        body.setChildrenCollapsible(False)
        library = QWidget()
        library_layout = QVBoxLayout(library)
        library_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search recordings…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_files)
        library_layout.addWidget(self.search)
        self.count = QLabel()
        self.count.setObjectName('muted')
        self.count.setStyleSheet('color: #f8957e; padding: 4px 0;')
        library_layout.addWidget(self.count)
        self.files = QListWidget()
        self.files.setMinimumWidth(220)
        self.files.setTextElideMode(Qt.ElideMiddle)
        self.files.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        library_layout.addWidget(self.files, 1)
        body.addWidget(library)
        preview = QFrame()
        preview.setObjectName('panel')
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        heading = QLabel('WATCH & REVIEW')
        heading.setObjectName('eyebrow')
        preview_layout.addWidget(heading)
        self.video = QVideoWidget()
        self.video.setMinimumSize(160, 120)
        self.stage = QStackedWidget()
        self.placeholder = QLabel('Select a recording\nYour playback appears here')
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet('color: #9aadae; font-size: 18px; padding: 24px;')
        self.stage.addWidget(self.placeholder)
        self.stage.addWidget(self.video)
        preview_layout.addWidget(self.stage, 1)
        body.addWidget(preview)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 3)
        body.setSizes([340, 620])
        layout.addWidget(body, 1)
        self.player.setVideoOutput(self.video)
        self.message = QLabel('Select a recording to play.')
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        self.message.setMinimumWidth(0)
        preview_layout.addWidget(self.message)
        controls = QHBoxLayout()
        self.toggle = QPushButton('Play')
        self.toggle.setObjectName('playRecording')
        self.toggle.clicked.connect(self.toggle_play)
        controls.addWidget(self.toggle)
        self.seek = PlaybackSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.setAccessibleName('Playback position')
        self.seek.valueChanged.connect(self.player.setPosition)
        controls.addWidget(self.seek, 1)
        self.time = QLabel('0:00 / 0:00')
        controls.addWidget(self.time)
        self.mute = QPushButton('Mute')
        self.mute.setCheckable(True)
        self.mute.toggled.connect(self.audio.setMuted)
        controls.addWidget(self.mute)
        self.volume = PlaybackSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(50)
        self.volume.setFixedWidth(110)
        self.volume.setAccessibleName('Volume')
        self.volume.valueChanged.connect(self.set_volume)
        controls.addWidget(self.volume)
        self.volume_label = QLabel()
        self.volume_label.setMinimumWidth(42)
        controls.addWidget(self.volume_label)
        self.audio.volumeChanged.connect(self.sync_volume)
        self.audio.mutedChanged.connect(self.sync_volume)
        self.sync_volume()
        preview_layout.addLayout(controls)
        actions = QHBoxLayout()
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(lambda: self.refresh())
        actions.addWidget(refresh)
        folder = QPushButton('Open folder ↗')
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory))))
        actions.addWidget(folder)
        actions.addStretch()
        self.upload = QPushButton('Upload to Loom')
        self.upload.clicked.connect(self.upload_selected)
        actions.addWidget(self.upload)
        self.copy = QPushButton('Copy path')
        self.copy.clicked.connect(self.copy_selected_path)
        actions.addWidget(self.copy)
        self.rename = QPushButton('Rename')
        self.rename.clicked.connect(self.rename_selected)
        actions.addWidget(self.rename)
        self.delete = QPushButton('Delete recording')
        self.delete.clicked.connect(self.delete_selected)
        actions.addWidget(self.delete)
        layout.addLayout(actions)
        self.files.currentItemChanged.connect(self.select)
        self.player.playbackStateChanged.connect(lambda state: self.toggle.setText(
            'Pause' if state == QMediaPlayer.PlayingState else 'Play'))
        self.player.durationChanged.connect(self.update_position)
        self.player.positionChanged.connect(self.update_position)
        self.player.seekableChanged.connect(self.seek.setEnabled)
        self.player.errorOccurred.connect(self.failed)
        self.refresh()

    def refresh(self, selected=None):
        selected = Path(selected) if selected else (self.selected_path() or Path(self.player.source().toLocalFile()))
        self.release()
        self.files.clear()
        self.update_actions()
        self.toggle.setEnabled(False)
        self.seek.setEnabled(False)
        try:
            if not self.directory.is_dir():
                raise FileNotFoundError(f'Recording folder is missing: {self.directory}')
            paths = recording_files(self.directory)
        except OSError as exc:
            self.count.setText('Library unavailable')
            self.placeholder.setText('Cannot open your library\nCheck the folder and try Refresh.')
            self.message.setText(f'Could not read recordings: {exc}')
            return
        self.placeholder.setText('Select a recording\nYour playback appears here' if paths else 'No recordings yet\nMake your first recording to see it here.')
        self.message.setText('Select a recording to play.' if paths else 'No recordings yet. Saved MP4 and MKV videos appear here.')
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue  # A file may disappear between scanning and displaying it.
            date = datetime.fromtimestamp(stat.st_mtime)
            day = 'Today' if date.date() == datetime.now().date() else date.strftime('%b %d, %Y')
            size = stat.st_size
            size_text = f'{size / 1024 ** 3:.1f} GB' if size >= 1024 ** 3 else f'{size / 1024 ** 2:.1f} MB'
            item = QListWidgetItem(f'{recording_title(path)}\n{day} · {date:%H:%M}  •  {size_text}  •  {path.suffix[1:].upper()}')
            item.setSizeHint(QSize(0, 92))
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            self.files.addItem(item)
        self.filter_files(self.search.text())
        for index in range(self.files.count()):
            item = self.files.item(index)
            if Path(item.data(Qt.UserRole)) == selected:
                if not item.isHidden():
                    self.files.setCurrentItem(item)
                break
        else:
            if selected != Path('.') and not selected.is_file():
                self.message.setText('This recording is missing. Refresh the list.')

    def filter_files(self, text):
        visible = 0
        for index in range(self.files.count()):
            item = self.files.item(index)
            hidden = text.casefold() not in (item.text() + ' ' + Path(item.data(Qt.UserRole)).name).casefold()
            item.setHidden(hidden)
            visible += not hidden
        current = self.files.currentItem()
        if current is not None and current.isHidden():
            self.files.setCurrentItem(None)
        self.update_actions()
        self.count.setText(f'{visible} recording{"s" if visible != 1 else ""} · Newest first')
        if not visible and self.files.count():
            self.placeholder.setText('No matching recordings\nTry a different name or clear your search.')
            if self.player.source().isEmpty():
                self.stage.setCurrentWidget(self.placeholder)
            self.message.setText('No matching recordings. Try another search.')
        elif self.player.source().isEmpty() and self.files.count():
            self.placeholder.setText('Select a recording\nYour playback appears here')
            self.message.setText('Select a recording to play.')
        elif not self.player.source().isEmpty():
            self.stage.setCurrentWidget(self.video)
            self.message.setText(recording_title(self.player.source().toLocalFile()))

    def set_volume(self, value):
        self.audio.setVolume(value / 100)
        if value > 0:
            self.audio.setMuted(False)

    def sync_volume(self, *_):
        value = round(self.audio.volume() * 100)
        with QSignalBlocker(self.volume):
            self.volume.setValue(value)
        with QSignalBlocker(self.mute):
            self.mute.setChecked(self.audio.isMuted())
        self.mute.setText('Unmute' if self.audio.isMuted() else 'Mute')
        self.volume_label.setText('Muted' if self.audio.isMuted() else f'{value}%')

    def selected_path(self):
        item = self.files.currentItem()
        return Path(item.data(Qt.UserRole)) if item is not None and not item.isHidden() else None

    def update_actions(self):
        path = self.selected_path()
        exists = path is not None and path.is_file()
        self.upload.setText('Prepare MP4' if path and path.suffix == '.mkv' else 'Upload to Loom')
        self.upload.setEnabled(exists and not self.deletion_blocked(path))
        self.copy.setEnabled(exists)
        self.rename.setEnabled(exists and not self.deletion_blocked(path))
        self.delete.setEnabled(exists and not self.deletion_blocked(path))

    def rename_selected(self):
        path = self.selected_path()
        self.update_actions()
        if path is None or not path.is_file() or self.deletion_blocked(path):
            return
        title, accepted = QInputDialog.getText(self, 'Rename recording', 'Title:',
            QLineEdit.Normal, recording_title(path))
        if not accepted:
            return
        # The dialog runs an event loop. Saving/uploading may have started meanwhile.
        if self.deletion_blocked(path):
            self.message.setText('This recording is in use. Try again when saving or uploading finishes.')
            self.update_actions()
            return
        self.release()
        try:
            renamed = rename_recording(path, title)
        except (OSError, ValueError) as exc:
            self.select(self.files.currentItem())
            self.message.setText(f'Could not rename {path.name}: {exc}')
            self.update_actions()
            return
        if renamed != path:
            self.recording_renamed.emit(str(path), str(renamed))
        # Keep the result visible if the old search no longer matches its title.
        if self.search.text().casefold() not in (recording_title(renamed) + ' ' + renamed.name).casefold():
            self.search.clear()
        self.refresh(renamed)
        self.message.setText(recording_title(renamed))

    def upload_selected(self):
        path = self.selected_path()
        self.update_actions()
        if path is not None and path.is_file() and not self.deletion_blocked(path):
            self.upload_requested.emit(str(path))

    def copy_selected_path(self):
        path = self.selected_path()
        self.update_actions()
        if path is not None and path.is_file():
            QApplication.clipboard().setText(str(path))
            self.message.setText('File path copied. This file is on your computer.')

    def delete_selected(self):
        path = self.selected_path()
        self.update_actions()
        if path is None or not path.is_file() or self.deletion_blocked(path):
            return
        answer = QMessageBox.question(self, 'Delete recording?',
            f'Permanently delete this recording?\n\n{path}\n\nThis cannot be undone.',
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if answer != QMessageBox.Yes:
            return
        # Recheck after the modal dialog, which can process application events.
        if self.deletion_blocked(path):
            self.message.setText('This recording is in use. Try again when saving or uploading finishes.')
            self.update_actions()
            return
        self.release()
        try:
            path.unlink()
        except OSError as exc:
            self.message.setText(f'Could not delete {path.name}: {exc}')
            self.update_actions()
            return
        self.refresh()
        self.message.setText(f'Deleted {path.name}.')
        self.recording_deleted.emit(str(path))

    def reject(self):
        self.release()
        self.back_requested.emit()

    def hideEvent(self, event):
        self.release()
        super().hideEvent(event)

    def select(self, item, previous=None):
        self.release()
        self.toggle.setEnabled(False)
        self.update_actions()
        if item is None:
            return
        path = Path(item.data(Qt.UserRole))
        if not path.is_file():
            self.message.setText('This recording is missing. Refresh the list.')
            return
        self.message.setText(recording_title(path))
        self.toggle.setEnabled(True)
        self.stage.setCurrentWidget(self.video)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif not self.player.source().isEmpty():
            if self.player.mediaStatus() == QMediaPlayer.EndOfMedia:
                self.player.setPosition(0)
            self.player.play()

    def update_position(self, *_):
        duration, position = self.player.duration(), self.player.position()
        with QSignalBlocker(self.seek):
            self.seek.setRange(0, duration)
            if not self.seek.isSliderDown():
                self.seek.setValue(position)
        self.time.setText(f'{timestamp(position)} / {timestamp(duration)}')

    def failed(self, error, message):
        self.player.stop()
        self.toggle.setEnabled(False)
        self.seek.setEnabled(False)
        self.placeholder.setText('This recording could not be played\nTry another video or refresh the list.')
        self.stage.setCurrentWidget(self.placeholder)
        self.message.setText(f'Could not play this recording: {message}')

    def release(self, *_):
        self.stage.setCurrentWidget(self.placeholder)
        self.toggle.setEnabled(False)
        self.player.stop()
        self.player.setSource(QUrl())
        self.seek.setEnabled(False)
        self.update_position()
