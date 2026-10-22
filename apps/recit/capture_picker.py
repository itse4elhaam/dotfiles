"""Capture identities and a text-only picker; no thumbnail capture."""
from dataclasses import dataclass, replace
import re

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QPushButton, QDialogButtonBox)


@dataclass(frozen=True)
class CaptureTarget:
    kind: str
    monitor: str = ''
    obs_index: int = -1
    bounds: tuple = ()  # X11 physical pixels, including physical desktop origin.
    window_id: int | None = None
    region: tuple | None = None  # Monitor-local physical pixels: x, y, width, height.

    def validate(self):
        if self.kind not in ('screen', 'window', 'region', 'tab'):
            raise ValueError('Unknown capture target.')
        if self.kind == 'window' and (type(self.window_id) is not int or not 0 < self.window_id <= 0xFFFFFFFF):
            raise ValueError('Select an open window.')
        if self.kind in ('screen', 'region'):
            if not self.monitor or self.obs_index < 0 or len(self.bounds) != 4 or min(self.bounds[2:]) <= 0:
                raise ValueError('Select an available monitor.')
        if self.kind == 'region':
            validate_region(self.region, self.bounds[2:])
        return self

    def pointer(self, px, py):
        x, y, w, h = self.bounds
        if self.region:
            rx, ry, w, h = self.region
            x, y = x + rx, y + ry
        return max(0., min(1., (px-x)/w)), max(0., min(1., (py-y)/h))


def validate_region(region, dimensions):
    if (not isinstance(region, tuple) or len(region) != 4
            or any(type(n) is not int for n in region)):
        raise ValueError('Select a region on one monitor.')
    x, y, w, h = region
    if min(x, y) < 0 or min(w, h) <= 0 or x+w > dimensions[0] or y+h > dimensions[1]:
        raise ValueError('The region must be wholly inside the selected monitor.')


def monitor_targets(options, screens):
    """OBS 27 labels contain connector, physical dimensions and X11 origin.

    Match by connector plus dimensions, never Qt enumeration order. Numeric
    Xinerama labels may match only a unique physical rectangle. Qt X11 geometry
    origins remain native coordinates while sizes are device-independent.
    """
    result = []
    for name, index in options:
        match = re.fullmatch(r'Screen (.+) \((\d+)x(\d+) @ (-?\d+),(-?\d+)\)', name)
        if not match:
            continue
        connector, w, h, x, y = match.groups()
        bounds = tuple(map(int, (x, y, w, h)))
        matches = []
        for screen in screens:
            geo, ratio = screen.geometry(), screen.devicePixelRatio()
            dims = round(geo.width()*ratio), round(geo.height()*ratio)
            if dims == bounds[2:] and (connector == screen.name() or
                    (connector.isdecimal() and (geo.x(), geo.y()) == bounds[:2])):
                matches.append(screen)
        if len(matches) == 1:
            result.append((CaptureTarget('screen', matches[0].name(), index, bounds), matches[0]))
    return result


def drag_region(start, end, ratio, dimensions):
    x1, x2 = sorted((round(start.x()*ratio), round(end.x()*ratio)))
    y1, y2 = sorted((round(start.y()*ratio), round(end.y()*ratio)))
    x1, x2 = max(0, x1), min(dimensions[0], x2)
    y1, y2 = max(0, y1), min(dimensions[1], y2)
    region = x1, y1, x2-x1, y2-y1
    validate_region(region, dimensions)
    return region


class RegionOverlay(QDialog):
    def __init__(self, target, screen, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.target, self.monitor_screen = target, screen
        self.start_point = self.end_point = None
        self.region = None
        self.setWindowTitle('Drag a region. Escape cancels.')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(screen.geometry())
        self.setModal(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = self.end_point = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_point is not None:
            self.end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self.start_point is None:
            return
        try:
            self.region = drag_region(self.start_point, event.position().toPoint(),
                self.monitor_screen.devicePixelRatio(), self.target.bounds[2:])
        except ValueError:
            self.start_point = self.end_point = None
            self.update()
            return
        self.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        painter.setPen(QPen(QColor('#9ddbc4'), 2))
        message = 'Drag to select a region on this monitor. Escape cancels.'
        if self.start_point is not None:
            painter.drawRect(QRect(self.start_point, self.end_point).normalized())
            try:
                r = drag_region(self.start_point, self.end_point,
                    self.monitor_screen.devicePixelRatio(), self.target.bounds[2:])
                message = f'{r[2]} × {r[3]} pixels · Release to choose · Escape cancels'
            except ValueError:
                pass
        painter.drawText(QPoint(20, 30), message)


class CapturePicker(QDialog):
    def __init__(self, engine, catalog, current=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose what to record')
        self.resize(540, 240)
        self.target = None
        self.current = current
        self.catalog = catalog
        self.engine = engine
        self.monitors = []
        layout = QVBoxLayout(self)
        self.kind, self.choices = QComboBox(), QComboBox()
        for title, kind in [('Screen', 'screen'), ('Window', 'window'), ('Region', 'region'), ('Browser tab', 'tab')]:
            self.kind.addItem(title, kind)
        layout.addWidget(self.kind)
        layout.addWidget(self.choices)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        row = QHBoxLayout()
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.choose)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)
        self.kind.currentIndexChanged.connect(self.refresh)
        self.kind.setCurrentIndex(max(0, self.kind.findData(current.kind if current else 'screen')))
        self.refresh()

    def refresh(self):
        self.monitors = monitor_targets(self.engine.screen_options(), QApplication.screens())
        previous = self.choices.currentData()
        self.choices.clear()
        kind = self.kind.currentData()
        self.choices.addItem('Choose a target…', None)
        if kind == 'window':
            try:
                for title, wid in self.catalog.list():
                    self.choices.addItem(title, CaptureTarget('window', window_id=wid))
            except Exception:
                self.note.setText('Window list unavailable. Refresh to try again.')
                return
        elif kind in ('screen', 'region'):
            for target, screen in self.monitors:
                self.choices.addItem(f'{target.monitor} · {target.bounds[2]} × {target.bounds[3]}', target)
        self.choices.setVisible(kind != 'tab')
        self.note.setText('Browser owns recording in the optional Chrome companion. Download WebM, then import it in Recordings. Native Record, zoom, filters and hotkeys do not control it.' if kind == 'tab' else
            'Region: choose a monitor, then drag. No live thumbnails are taken.' if kind == 'region' else
            'Keep the selected window open and unminimized.' if kind == 'window' else 'Record one monitor.')
        desired = previous or self.current
        if desired and kind == 'region':
            desired = replace(desired, kind='screen', region=None)
        self.choices.setCurrentIndex(next((i for i in range(self.choices.count())
            if self.choices.itemData(i) == desired), 0))

    def choose(self):
        kind = self.kind.currentData()
        target = CaptureTarget('tab') if kind == 'tab' else self.choices.currentData()
        if target is None:
            self.note.setText('Choose a target first.')
            return
        if kind == 'region':
            screen = next(s for t, s in self.monitors if t == target)
            overlay = RegionOverlay(target, screen, self)
            if overlay.exec() != QDialog.Accepted:
                return
            target = replace(target, kind='region', region=overlay.region)
        self.target = target.validate()
        self.accept()
