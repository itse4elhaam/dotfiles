"""Shape, drag, and zoom checks without live capture."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from floating import CameraBubble, ZoomMotion

qt = QApplication.instance() or QApplication([])


class FloatingChecks(unittest.TestCase):
    def test_circle_clips_corners(self):
        bubble = CameraBubble()
        bubble.resize(200, 200)
        bubble.apply_shape('circle')
        self.assertTrue(bubble.mask().contains(QPoint(100, 100)))
        self.assertFalse(bubble.mask().contains(QPoint(2, 2)))
        bubble.apply_shape('square')
        self.assertTrue(bubble.mask().isEmpty())  # No clipping for a square.
        bubble.close()

    def test_bubble_starts_inside_selected_screen_at_bottom(self):
        bubble = CameraBubble()
        screen = qt.primaryScreen()
        bubble.arrange(screen, .23, 'bottom-right', 'circle')
        self.assertTrue(screen.availableGeometry().contains(bubble.geometry()))
        self.assertLess(screen.availableGeometry().bottom() - bubble.geometry().bottom(), 25)
        bubble.close()

    def test_zoom_starts_at_pointer_and_eases_back(self):
        motion = ZoomMotion()
        motion.enabled = True
        now = motion.last_time
        value, x, y = motion.step(2., .9, .1, now + .016)
        self.assertGreater(value, 1.)
        self.assertLess(value, 2.)
        self.assertAlmostEqual(x, .9)
        self.assertAlmostEqual(y, .1)
        for i in range(1, 100):
            value, _, _ = motion.step(2., .9, .1, now + .016 * (i + 1))
        self.assertEqual(value, 2.)
        motion.enabled = False
        for i in range(100, 200):
            value, _, _ = motion.step(2., .9, .1, now + .016 * (i + 1))
        self.assertEqual(value, 1.)

    def test_zoom_clamps_bad_input(self):
        motion = ZoomMotion()
        motion.enabled = True
        for i in range(100):
            value, x, y = motion.step(20, 4, -3, motion.last_time + .05)
        self.assertEqual(value, 3.)
        self.assertEqual((x, y), (1., 0.))


if __name__ == '__main__':
    unittest.main()
