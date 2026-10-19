"""Opt-in full application lifecycle check. Captures real devices, deletes videos.
Run with --capture after closing RecIt. Requires the actual X11 desktop.
"""
import sys
import tempfile
import time
import subprocess
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer, QSettings
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
import app as glint


def run():
    qt = QApplication([])
    qt.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix='glint-ui-check-') as directory:
        root = Path(directory)
        with patch.object(glint, 'VIDEOS', root), patch.object(glint, 'STATE', root), patch.object(glint, 'QSettings', return_value=QSettings(str(root/'prefs.ini'), QSettings.IniFormat)):
            window = glint.Window()
            window.show()
            def wait(predicate, limit=15):
                deadline = time.monotonic() + limit
                while time.monotonic() < deadline:
                    qt.processEvents()
                    if predicate():
                        return
                    time.sleep(.01)  # QTest.qWait holds the GIL and starves OBS's Python draw callback.
                raise AssertionError(f'Timed out: {window.status.text()}')
            def tick(seconds):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    qt.processEvents()
                    time.sleep(.01)
            try:
                wait(lambda: window.engine and window.record_button.isEnabled())
                assert window.bubble.isVisible(), 'Camera widget must be visible before recording'
                tick(.3)  # Let the X11 window map before sending physical pointer input.
                before = window.bubble.pos()
                ratio = window.bubble.devicePixelRatioF()
                centre = window.bubble.geometry().center()
                subprocess.run(['xdotool', 'mousemove', str(round(centre.x()*ratio)), str(round(centre.y()*ratio)), 'mousedown', '1'], check=True)
                tick(.1)
                subprocess.run(['xdotool', 'mousemove', str(round((centre.x()-80)*ratio)), str(round((centre.y()-50)*ratio))], check=True)
                tick(.1)
                subprocess.run(['xdotool', 'mouseup', '1'], check=True)
                tick(.2)
                assert window.bubble.pos() != before, 'Native camera surface must accept dragging'
                print('Native camera dragging passed.', flush=True)
                window.toggle_record()
                wait(lambda: window.recording)
                assert window.bubble.isVisible(), 'Hiding main window must keep camera widget visible'
                assert not window.isVisible(), 'Main setup window must be hidden during screen capture'
                tick(3)
                print('SCREEN LIVE', window.engine.stats(), flush=True)
                bounds = qt.primaryScreen().geometry()
                QCursor.setPos(bounds.width()//3, bounds.height()//3)
                subprocess.run(['xdotool', 'key', 'ctrl+shift+F8'], check=True)
                tick(1.2)
                assert window.zoom_motion.factor == 2., 'Zoom must reach the requested level'
                QCursor.setPos(bounds.width()*2//3, bounds.height()//4)
                tick(.5)
                assert window.zoom_motion.x > .6, 'Zoom must follow the pointer'
                subprocess.run(['xdotool', 'key', 'ctrl+shift+F8'], check=True)
                tick(1.2)
                assert window.zoom_motion.factor == 1., 'Zoom must return to the full screen'
                print('Pointer zoom in/follow/out passed.', window.engine.stats(), flush=True)
                window.toggle_pause()
                assert window.paused
                tick(.4)
                window.stop()  # Save directly while paused.
                wait(lambda: not window.busy and not window.recording)
                assert window.last_file.suffix == '.mp4', window.status.text()
                print('SCREEN', window.last_file.name, window.engine.stats(), flush=True)
                window.set_mode('camera')
                wait(lambda: not window.configure_timer.isActive() and window.record_button.isEnabled())
                assert not window.bubble.isVisible(), 'Camera-only mode must not add a desktop bubble'
                window.toggle_record()
                wait(lambda: window.recording)
                tick(3)
                print('CAMERA LIVE', window.engine.stats(), flush=True)
                window.stop()
                wait(lambda: not window.busy and not window.recording)
                assert window.last_file.suffix == '.mp4', window.status.text()
                print('CAMERA', window.last_file.name, window.engine.stats(), flush=True)
                window.quality.setCurrentIndex(1)
                wait(lambda: window.engine and window.engine.width == 1920 and window.record_button.isEnabled())
                window.quality.setCurrentIndex(0)
                wait(lambda: window.engine and window.engine.width == 3840 and window.record_button.isEnabled())
                window.set_mode('screen')
                wait(lambda: not window.configure_timer.isActive() and window.record_button.isEnabled())
                window.toggle_record()
                window.cancel_countdown()
                assert not window.recording and not window.counting
                print('Quality restart and cancelled countdown passed.', flush=True)
                target = QWidget()
                target.setWindowTitle('RecIt window capture test')
                target.setStyleSheet('background: #276780;')
                target.resize(640, 360)
                target.show()
                tick(.4)
                window.capture_kind.setCurrentIndex(1)
                window.capture_window.addItem('Test window', int(target.winId()))
                window.capture_window.setCurrentIndex(window.capture_window.count()-1)
                wait(lambda: not window.configure_timer.isActive() and window.record_button.isEnabled())
                assert window.engine._window_id == int(target.winId())
                assert window.engine._camera_item, 'Window capture needs its own composited camera'
                assert window.bubble.isVisible()
                window.toggle_record()
                wait(lambda: window.recording)
                tick(1)
                window.toggle_zoom()
                tick(1.2)
                assert window.zoom_motion.factor == 2.
                print('WINDOW LIVE', window.engine.stats(), flush=True)
                target.resize(800, 480)
                tick(.7)
                expected = (round(800 * target.devicePixelRatioF()), round(480 * target.devicePixelRatioF()))
                assert window.engine.window_dimensions() == expected, (window.engine.window_dimensions(), expected)
                target.close()  # Losing the target must save, with a warning.
                wait(lambda: not window.recording and not window.busy)
                assert window.last_file.suffix == '.mp4'
                assert 'closed or was minimized' in window.status.text(), window.status.text()
                print('Selected-window resize/loss/save passed.', flush=True)
            finally:
                if window.recording:
                    window.stop()
                    wait(lambda: not window.busy)
                window.close()
                qt.processEvents()
    print('Full UI lifecycle passed. Temporary videos deleted.', flush=True)


if __name__ == '__main__':
    if '--capture' not in sys.argv:
        raise SystemExit('Pass --capture to authorize real screen/camera capture for this check.')
    run()
