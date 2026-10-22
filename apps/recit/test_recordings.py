"""Offscreen playback checks using generated media, never capture devices."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import subprocess
import tempfile
import time
from pathlib import Path
import unittest

from PySide6.QtCore import Qt, QPoint
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QApplication, QMessageBox, QStyle, QStyleOptionSlider
from PySide6.QtTest import QTest
from unittest.mock import patch
from recordings import Recordings

qt = QApplication.instance() or QApplication([])


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qt.processEvents()
        if predicate():
            return True
        time.sleep(.01)
    return False


class PlaybackChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dialog = Recordings(self.root)
        # No audio output device is attached in these tests. Synthetic media is silent.
        self.dialog.player.setAudioOutput(None)

    def tearDown(self):
        self.dialog.reject()
        self.dialog.deleteLater()
        qt.processEvents()
        self.temp.cleanup()

    def clip(self, name):
        path = self.root / name
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                        '-i', 'testsrc2=size=160x90:rate=10', '-t', '3', '-an',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)
        return path

    def test_empty_missing_directory_and_missing_file(self):
        self.assertEqual(self.dialog.files.count(), 0)
        self.assertIn('No recordings', self.dialog.message.text())
        path = self.root / 'gone.mp4'
        path.touch()
        self.dialog.refresh()
        path.unlink()
        self.dialog.files.setCurrentRow(0)
        self.assertIn('missing', self.dialog.message.text())
        self.assertTrue(self.dialog.player.source().isEmpty())
        self.dialog.refresh(path)
        self.assertIn('missing', self.dialog.message.text())
        self.dialog.directory = self.root / 'missing'
        self.dialog.refresh()
        self.assertIn('Could not read', self.dialog.message.text())

    def test_decode_pause_seek_switch_and_cleanup(self):
        older = self.clip('older.mp4')
        newer = self.clip('newer.mkv')
        os.utime(older, (1, 1))
        (self.root / 'ignored.txt').touch()
        sink = QVideoSink()
        frames = []
        sink.videoFrameChanged.connect(lambda frame: frames.append(frame) if frame.isValid() else None)
        self.dialog.player.setVideoSink(sink)
        self.dialog.refresh()
        self.assertEqual(self.dialog.files.count(), 2)
        self.assertEqual(self.dialog.files.item(0).data(Qt.UserRole), str(newer))
        self.dialog.files.setCurrentRow(0)
        self.assertTrue(wait_for(lambda: len(frames) > 1 and self.dialog.player.duration() > 0))
        self.dialog.toggle_play()
        self.assertEqual(self.dialog.player.playbackState(), QMediaPlayer.PausedState)
        self.assertTrue(self.dialog.seek.isEnabled())
        self.dialog.resize(1100, 750)
        self.dialog.show()
        qt.processEvents()
        QTest.mouseClick(self.dialog.seek, Qt.LeftButton,
            pos=QPoint(self.dialog.seek.width() // 2, self.dialog.seek.height() // 2))
        self.assertTrue(wait_for(lambda: abs(self.dialog.player.position() - 1500) < 250))
        self.dialog.seek.setFocus()
        self.dialog.seek.setSingleStep(500)
        QTest.keyClick(self.dialog.seek, Qt.Key_Home)
        for _ in range(3):
            QTest.keyClick(self.dialog.seek, Qt.Key_Right)
        self.assertTrue(wait_for(lambda: abs(self.dialog.player.position() - 1500) < 200))
        self.assertIn('/ 0:03', self.dialog.time.text())
        self.dialog.volume.setValue(25)
        self.assertAlmostEqual(self.dialog.audio.volume(), .25)
        self.dialog.toggle_play()
        self.assertEqual(self.dialog.player.playbackState(), QMediaPlayer.PlayingState)
        count = len(frames)
        self.dialog.files.setCurrentRow(1)
        self.assertEqual(self.dialog.player.source().toLocalFile(), str(older))
        self.assertTrue(wait_for(lambda: len(frames) > count))
        self.dialog.reject()
        self.assertEqual(self.dialog.player.playbackState(), QMediaPlayer.StoppedState)
        self.assertTrue(self.dialog.player.source().isEmpty())

    def test_search_filters_names_and_recovers_from_no_results(self):
        (self.root / 'A long project walkthrough.mp4').touch()
        (self.root / 'Second take.mkv').touch()
        self.dialog.refresh()
        self.dialog.search.setText('WALKTHROUGH')
        visible = [self.dialog.files.item(i) for i in range(2) if not self.dialog.files.item(i).isHidden()]
        self.assertEqual(len(visible), 1)
        self.assertIn('Today', visible[0].text())
        self.assertIn('MB', visible[0].text())
        self.dialog.search.setText('no such recording')
        self.assertIn('No matching', self.dialog.message.text())
        self.dialog.search.clear()
        self.assertEqual(self.dialog.count.text(), '2 recordings · Newest first')
        self.assertIn('Select a recording', self.dialog.message.text())

    def test_corrupt_clip_reports_error(self):
        (self.root / 'broken.mp4').write_bytes(b'not video')
        self.dialog.refresh()
        self.dialog.files.setCurrentRow(0)
        self.assertTrue(wait_for(lambda: 'Could not play' in self.dialog.message.text()))
        self.assertFalse(self.dialog.toggle.isEnabled())


class RecordingActionsChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old = self.root / 'Earlier take.mp4'
        self.new = self.root / 'Latest take.mkv'
        self.old.touch()
        self.new.touch()
        os.utime(self.old, (1, 1))
        self.dialog = Recordings(self.root)
        self.dialog.resize(1100, 750)
        self.dialog.show()
        qt.processEvents()

    def tearDown(self):
        self.dialog.reject()
        self.dialog.close()
        self.dialog.deleteLater()
        qt.processEvents()
        self.temp.cleanup()

    def test_volume_actual_output_mouse_keyboard_zero_and_mute(self):
        self.assertIs(self.dialog.player.audioOutput(), self.dialog.audio)
        volume = self.dialog.volume
        QTest.mouseClick(volume, Qt.LeftButton, pos=QPoint(volume.width() * 3 // 4, volume.height() // 2))
        self.assertGreater(self.dialog.audio.volume(), .65)
        self.assertLess(self.dialog.audio.volume(), .85)
        option = QStyleOptionSlider()
        volume.initStyleOption(option)
        handle = volume.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, volume)
        QTest.mousePress(volume, Qt.LeftButton, pos=handle.center())
        QTest.mouseMove(volume, QPoint(volume.width() // 3, volume.height() // 2))
        QTest.mouseRelease(volume, Qt.LeftButton, pos=QPoint(volume.width() // 3, volume.height() // 2))
        self.assertLess(self.dialog.audio.volume(), .5)
        self.assertGreater(self.dialog.audio.volume(), .2)
        QTest.keyClick(volume, Qt.Key_End)
        self.assertAlmostEqual(self.dialog.audio.volume(), 1)
        QTest.keyClick(volume, Qt.Key_Left)
        self.assertAlmostEqual(self.dialog.audio.volume(), .99, places=5)
        QTest.keyClick(volume, Qt.Key_Home)
        self.assertEqual(self.dialog.audio.volume(), 0)
        self.assertEqual(self.dialog.volume_label.text(), '0%')
        QTest.mouseClick(self.dialog.mute, Qt.LeftButton)
        self.assertTrue(self.dialog.audio.isMuted())
        self.assertEqual(self.dialog.volume_label.text(), 'Muted')
        QTest.keyClick(volume, Qt.Key_Right)
        self.assertFalse(self.dialog.audio.isMuted())
        self.assertEqual(self.dialog.volume_label.text(), '1%')
        self.dialog.audio.setVolume(.4)
        self.dialog.audio.setMuted(True)
        self.assertEqual(volume.value(), 40)
        self.assertTrue(self.dialog.mute.isChecked())
        QTest.mouseClick(self.dialog.mute, Qt.LeftButton)
        self.assertFalse(self.dialog.audio.isMuted())
        self.assertEqual(self.dialog.volume_label.text(), '40%')

    def test_copy_selection_search_refresh_and_missing(self):
        self.assertFalse(self.dialog.copy.isEnabled())
        self.assertFalse(self.dialog.delete.isEnabled())
        self.dialog.files.setCurrentRow(1)
        QTest.mouseClick(self.dialog.copy, Qt.LeftButton)
        self.assertEqual(qt.clipboard().text(), str(self.old))
        self.dialog.refresh()
        self.assertEqual(self.dialog.selected_path(), self.old)
        self.dialog.search.setText('Latest')
        self.assertIsNone(self.dialog.selected_path())
        self.assertTrue(self.dialog.player.source().isEmpty())
        self.assertFalse(self.dialog.copy.isEnabled())
        self.assertFalse(self.dialog.delete.isEnabled())
        self.dialog.search.clear()
        self.dialog.files.setCurrentRow(0)
        QTest.mouseClick(self.dialog.copy, Qt.LeftButton)
        self.assertEqual(qt.clipboard().text(), str(self.new))
        self.new.unlink()
        self.dialog.copy_selected_path()
        self.assertFalse(self.dialog.copy.isEnabled())
        self.assertFalse(self.dialog.delete.isEnabled())

    def test_upload_selection_recovery_filter_missing_and_busy(self):
        requested = []
        self.dialog.upload_requested.connect(requested.append)
        self.assertFalse(self.dialog.upload.isEnabled())
        for index, path, text in ((0, self.new, 'Prepare MP4'), (1, self.old, 'Upload to Loom')):
            self.dialog.files.setCurrentRow(index)
            self.assertEqual(self.dialog.upload.text(), text)
            self.dialog.upload.click()
            self.assertEqual(requested[-1], str(path))
        self.dialog.deletion_blocked = lambda path: True
        self.dialog.update_actions()
        self.assertFalse(self.dialog.upload.isEnabled())
        self.dialog.upload_selected()
        self.assertEqual(len(requested), 2)
        self.dialog.deletion_blocked = lambda path: False
        self.dialog.search.setText('Latest')
        self.dialog.upload_selected()
        self.assertFalse(self.dialog.upload.isEnabled())
        self.dialog.search.clear()
        self.dialog.files.setCurrentRow(1)
        self.old.unlink()
        self.dialog.upload_selected()
        self.assertFalse(self.dialog.upload.isEnabled())
        self.assertEqual(len(requested), 2)

    def test_delete_cancel_failure_release_and_last(self):
        deleted = []
        self.dialog.recording_deleted.connect(deleted.append)
        self.dialog.files.setCurrentRow(1)
        with patch('recordings.QMessageBox.question', return_value=QMessageBox.Cancel) as confirm:
            QTest.mouseClick(self.dialog.delete, Qt.LeftButton)
        self.assertIn(str(self.old), confirm.call_args.args[2])
        self.assertTrue(self.old.exists())
        self.assertEqual(self.dialog.files.count(), 2)
        with patch('recordings.QMessageBox.question', return_value=QMessageBox.Yes), patch.object(Path, 'unlink', side_effect=PermissionError('Permission denied')):
            self.dialog.delete_selected()
        self.assertEqual(self.dialog.files.count(), 2)
        self.assertIn('Permission denied', self.dialog.message.text())
        self.assertEqual(deleted, [])
        unlink = Path.unlink
        def checked_unlink(path):
            self.assertTrue(self.dialog.player.source().isEmpty())
            self.assertEqual(self.dialog.player.playbackState(), QMediaPlayer.StoppedState)
            unlink(path)
        with patch('recordings.QMessageBox.question', return_value=QMessageBox.Yes), patch.object(Path, 'unlink', checked_unlink):
            self.dialog.delete_selected()
        self.assertEqual(deleted, [str(self.old)])
        self.assertTrue(self.new.exists())
        self.assertFalse(self.dialog.delete.isEnabled())
        self.dialog.files.setCurrentRow(0)
        with patch('recordings.QMessageBox.question', return_value=QMessageBox.Yes):
            self.dialog.delete_selected()
        self.assertEqual(self.dialog.files.count(), 0)
        self.assertFalse(self.dialog.copy.isEnabled())
        self.assertFalse(self.dialog.delete.isEnabled())
        self.assertEqual(deleted, [str(self.old), str(self.new)])

    def test_busy_guard_rechecked_after_confirmation(self):
        self.dialog.deletion_blocked = lambda path: True
        self.dialog.files.setCurrentRow(0)
        self.assertFalse(self.dialog.delete.isEnabled())
        with patch('recordings.QMessageBox.question') as confirm:
            self.dialog.delete_selected()
            confirm.assert_not_called()
        self.dialog.deletion_blocked = lambda path: False
        self.dialog.update_actions()
        def confirm_and_lock(*args):
            self.dialog.deletion_blocked = lambda path: True
            return QMessageBox.Yes
        with patch('recordings.QMessageBox.question', side_effect=confirm_and_lock):
            self.dialog.delete_selected()
        self.assertTrue(self.new.exists())
        self.assertIn('in use', self.dialog.message.text())

    def test_splitter_resizes_without_decorative_line(self):
        self.assertEqual(self.dialog.body.handleWidth(), 12)
        self.assertIn('QSplitter::handle { background: transparent; }', self.dialog.styleSheet())
        before = self.dialog.body.sizes()
        self.dialog.body.setSizes([before[0] + 50, before[1] - 50])
        self.assertGreater(self.dialog.body.sizes()[0], before[0])


class LatestRecordingDeletionChecks(unittest.TestCase):
    def test_delete_signal_updates_last_file_and_busy_protects_files(self):
        import app
        from contextlib import ExitStack
        from PySide6.QtCore import QSettings
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            older = root / 'older.mp4'
            latest = root / 'latest.mp4'
            older.touch()
            latest.touch()
            os.utime(older, (1, 1))
            for target, name, value in (
                (app.Window, 'initialize', None), (app.Hotkeys, 'start', None),
                (app, 'cameras', []), (app, 'microphones', []),
                (app, 'QSettings', QSettings(str(root / 'prefs.ini'), QSettings.IniFormat)),
            ):
                stack.enter_context(patch.object(target, name, return_value=value))
            stack.enter_context(patch.object(app, 'VIDEOS', root))
            stack.enter_context(patch.object(app, 'STATE', root))
            window = app.Window()
            try:
                window.open_recordings(latest)
                library = window.recordings
                self.assertEqual(window.last_file, latest)
                for state in ('recording', 'counting', 'busy'):
                    setattr(window, state, True)
                    library.update_actions()
                    self.assertFalse(library.delete.isEnabled())
                    with patch('recordings.QMessageBox.question') as confirm:
                        library.delete_selected()
                        confirm.assert_not_called()
                    setattr(window, state, False)
                library.update_actions()
                with patch('recordings.QMessageBox.question', return_value=QMessageBox.Yes):
                    library.delete_selected()
                self.assertEqual(window.last_file, older)
                library.files.setCurrentRow(0)
                with patch('recordings.QMessageBox.question', return_value=QMessageBox.Yes):
                    library.delete_selected()
                self.assertIsNone(window.last_file)
                for button in (library.copy, library.delete, library.upload):
                    self.assertFalse(button.isEnabled())
            finally:
                window.close()
                qt.processEvents()
