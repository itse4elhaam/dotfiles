"""Recorder layout checks with mocked capture and no device access."""
import unittest

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QScrollArea, QComboBox, QPushButton, QCheckBox, QSlider, QWidget, QLabel

import app as glint
import test_app

qt = test_app.qt


class RecorderLayoutChecks(unittest.TestCase):
    setUp = test_app.AppChecks.setUp
    tearDown = test_app.AppChecks.tearDown

    def test_long_device_names_fit_sidebar_viewport(self):
        qt.setStyleSheet(glint.STYLE)
        window = self.window
        window.camera.addItem('MX Brio 705 for Business Ultra HD Camera', '/dev/video-long')
        window.camera.setCurrentIndex(window.camera.count() - 1)
        window.microphone.addItem('sof-hda-dsp Headphones Stereo Microphone', 'long-source')
        window.microphone.setCurrentIndex(window.microphone.count() - 1)
        window.capture_window.addItem('A very long application window title ' * 4, 123)
        path = self.root / 'RecIt-2026-10-22-103734-268818.mp4'
        path.touch()
        window.set_last(path)
        for mode in ('screen', 'camera'):
            window.set_mode(mode, configure=False)
            for width, height in ((960, 760), (1120, 840), (1920, 1080)):
                with self.subTest(mode=mode, width=width, height=height):
                    window.resize(width, height)
                    window.show()
                    qt.processEvents()
                    panel = window.controls_panel
                    viewport = panel.viewport()
                    side = panel.widget()
                    self.assertEqual(window.width(), width)
                    self.assertEqual(side.width(), viewport.width())
                    self.assertGreater(viewport.width(), 240)
                    if mode == 'screen' and height == 760:
                        self.assertTrue(panel.verticalScrollBar().isVisible())
                    for control in side.findChildren(QWidget):
                        if not isinstance(control, (QComboBox, QPushButton, QCheckBox, QSlider)):
                            continue
                        if control.isHidden() or not control.isVisibleTo(side):
                            continue
                        panel.ensureWidgetVisible(control)
                        qt.processEvents()
                        top_left = control.mapTo(viewport, QPoint())
                        self.assertGreaterEqual(top_left.x(), 0)
                        self.assertLessEqual(top_left.x() + control.width(), viewport.width(),
                                             control.objectName() or type(control).__name__)
                        self.assertTrue(viewport.rect().contains(
                            control.mapTo(viewport, control.rect().topLeft())))
                        self.assertTrue(viewport.rect().contains(
                            control.mapTo(viewport, control.rect().bottomRight())))
                    self.assertGreaterEqual(window.preview.height(), 360)

    def test_recorder_has_no_latest_recording_card(self):
        window = self.window
        path = self.root / 'RecIt-2026-10-22-103734-268818.mp4'
        path.write_bytes(b'synthetic metadata fixture')
        window.set_last(path)
        for width, height in ((1120, 840), (960, 760)):
            window.resize(width, height)
            window.show()
            qt.processEvents()
            self.assertIsInstance(window.controls_panel, QScrollArea)
            self.assertNotIn('YOUR LAST RECORDING',
                             [label.text() for label in window.recorder_page.findChildren(QLabel)])
            for attribute in ('recent', 'recent_name', 'play_button', 'upload_button', 'copy_button'):
                self.assertFalse(hasattr(window, attribute), attribute)
            self.assertGreaterEqual(window.preview.height(), 360)
        window.focus_button.setChecked(True)
        self.assertTrue(window.controls_panel.isHidden())
        self.assertTrue(window.record_button.isVisible())

    def test_footer_stays_visible_when_scrolling_expanding_and_returning(self):
        qt.setStyleSheet(glint.STYLE)
        window = self.window
        for width, height in ((1120, 840), (960, 760)):
            for mode, expanded in (('screen', False), ('camera', False), ('camera', True)):
                with self.subTest(size=(width, height), mode=mode, expanded=expanded):
                    window.set_mode(mode, configure=False)
                    window.focus_button.setChecked(expanded)
                    window.resize(width, height)
                    window.show()
                    qt.processEvents()
                    scrollbar = window.controls_panel.verticalScrollBar()
                    for position in (scrollbar.minimum(), scrollbar.maximum()):
                        scrollbar.setValue(position)
                        qt.processEvents()
                        for button in (window.library_button, window.sharing_button):
                            self.assertTrue(button.isVisible())
                            self.assertFalse(window.controls_panel.isAncestorOf(button))
                            self.assertTrue(window.rect().contains(
                                button.mapTo(window, button.rect().bottomRight())))
                            self.assertLess(button.mapTo(window, QPoint()).x(), width // 2)
                        self.assertGreaterEqual(window.preview.height(), 360)
                        self.assertGreater(window.library_button.mapTo(window, QPoint()).y(),
                                           height - 80)
                    if expanded:
                        self.assertLess(window.preview.mapTo(window, QPoint()).x(), 60)
                    else:
                        self.assertGreaterEqual(window.navigation_footer.mapTo(window, QPoint()).y(),
                                                window.controls_panel.mapTo(window, QPoint()).y()
                                                + window.controls_panel.height())
                    window.library_button.click()
                    qt.processEvents()
                    self.assertTrue(window.in_library())
                    window.recordings.back.click()
                    qt.processEvents()
                    self.assertIs(window.pages.currentWidget(), window.recorder_page)
                    self.assertTrue(window.library_button.isVisible())
                    self.assertEqual(window.focus_button.isChecked(), expanded)
        window.focus_button.setChecked(False)
        qt.processEvents()
        self.assertTrue(window.controls_panel.isVisible())

    def test_stop_has_distinct_visual_state_without_lifecycle_changes(self):
        button = self.window.record_button
        button.setText('■  Stop and save')
        self.assertTrue(button.property('stopping'))
        button.setText('●  Start recording')
        self.assertFalse(button.property('stopping'))


if __name__ == '__main__':
    unittest.main()
