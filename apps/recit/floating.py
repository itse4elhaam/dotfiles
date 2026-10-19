"""Native camera window and the small state machine for pointer-follow zoom."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import Qt, Signal, QPoint, QRectF, QTimer
from PySide6.QtGui import QBitmap, QCursor, QImage, QPainterPath, QRegion
from PySide6.QtWidgets import QWidget, QMenu, QApplication


class ZoomMotion:
    """Elapsed-time smoothing keeps zoom speed independent of the timer rate."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.factor = 1.0
        self.x = self.y = .5
        self.enabled = False
        self.last_time = time.monotonic()

    def step(self, target_factor, x, y, now=None):
        now = time.monotonic() if now is None else now
        dt = min(.1, max(0.0, now - self.last_time))
        self.last_time = now
        target = min(3.0, max(1.0, target_factor)) if self.enabled else 1.0
        alpha = 1.0 - math.exp(-dt / .12)
        if self.enabled and self.factor == 1.0:
            self.x, self.y = x, y
        self.factor += (target - self.factor) * alpha
        # Start the first zoom at the pointer, avoiding a distracting pan from centre.
        if self.factor < 1.02:
            self.x, self.y = x, y
        else:
            self.x += (x - self.x) * alpha
            self.y += (y - self.y) * alpha
        if abs(target - self.factor) < .002:
            self.factor = target
        self.x, self.y = min(1., max(0., self.x)), min(1., max(0., self.y))
        return self.factor, self.x, self.y


class CameraBubble(QWidget):
    stop_requested = Signal()
    pause_requested = Signal()
    zoom_requested = Signal()
    open_requested = Signal()
    moved = Signal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setWindowTitle('RecIt · Camera widget')
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip('Drag to move · Right-click for recording controls\nCtrl + Shift + F8 toggles pointer zoom')
        self._drag_offset = None
        self._screen = None
        self.recording = False
        self.paused = False
        self.zoomed = False

    def paintEngine(self):
        return None

    def showEvent(self, event):
        super().showEvent(event)
        if QApplication.platformName() == 'xcb':
            QTimer.singleShot(0, self.pin_to_workspaces)

    def pin_to_workspaces(self):
        if not self.isVisible():
            return
        # EWMH's all-desktops value keeps the camera visible when changing workspaces.
        from Xlib import X, Xatom, display, protocol
        connection = display.Display()
        try:
            window = connection.create_resource_object('window', int(self.winId()))
            desktop_atom = connection.intern_atom('_NET_WM_DESKTOP')
            window.change_property(desktop_atom, Xatom.CARDINAL, 32, [0xFFFFFFFF])
            connection.screen().root.send_event(protocol.event.ClientMessage(
                window=window, client_type=desktop_atom, data=(32, [0xFFFFFFFF, 2, 0, 0, 0])),
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            connection.flush()
        finally:
            connection.close()

    def arrange(self, screen, fraction, position, shape, mask_path=None, mirror_mask=False):
        self._screen = screen
        bounds = screen.availableGeometry()
        side = round(min(bounds.width(), bounds.height()) * fraction)
        side = max(100, min(side, round(min(bounds.width(), bounds.height()) * .5)))
        self.setFixedSize(side, side)
        margin = 20
        x = bounds.left() + margin if 'left' in position else bounds.right() - side - margin + 1
        y = bounds.top() + margin if 'top' in position else bounds.bottom() - side - margin + 1
        self.move(x, y)
        self.apply_shape(shape, mask_path, mirror_mask)

    def apply_shape(self, shape, mask_path=None, mirror_mask=False):
        rect = QRectF(0, 0, self.width(), self.height())
        if shape == 'square':
            self.clearMask()
            return
        if shape == 'custom':
            image = QImage(mask_path or '')
            if image.isNull():
                raise ValueError('The custom camera shape image cannot be opened.')
            image = image.scaled(self.width(), self.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            if mirror_mask:
                image = image.mirrored(True, False)
            region = QRegion(QBitmap.fromImage(image.createAlphaMask()))
            if region.isEmpty():
                raise ValueError('The custom camera shape is completely transparent.')
            self.setMask(region)
            return
        path = QPainterPath()
        if shape == 'circle':
            path.addEllipse(rect)
        else:
            path.addRoundedRect(rect, self.width() * .16, self.height() * .16)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            point = event.globalPosition().toPoint() - self._drag_offset
            if self._screen:
                bounds = self._screen.availableGeometry()
                point.setX(max(bounds.left(), min(bounds.right() - self.width() + 1, point.x())))
                point.setY(max(bounds.top(), min(bounds.bottom() - self.height() + 1, point.y())))
            self.move(point)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = None
            self.setCursor(Qt.OpenHandCursor)
            self.moved.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('Open RecIt', self.open_requested.emit)
        if self.recording:
            menu.addAction('Stop and save · Ctrl+Shift+F9', self.stop_requested.emit)
            menu.addAction('Resume' if self.paused else 'Pause', self.pause_requested.emit)
        action = menu.addAction('Zoom out' if self.zoomed else 'Zoom to pointer · Ctrl+Shift+F8', self.zoom_requested.emit)
        action.setEnabled(self.recording)
        menu.exec(event.globalPos())
