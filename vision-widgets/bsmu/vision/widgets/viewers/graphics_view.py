from __future__ import annotations

from functools import partial

from PySide2.QtCore import Qt, QObject, Signal, QTimeLine, QEvent
from PySide2.QtGui import QPainter, QFont, QColor
from PySide2.QtWidgets import QGraphicsView


SMOOTH_ZOOM_DURATION = 100
SMOOTH_ZOOM_UPDATE_INTERVAL = 10


class GraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, zoomable: bool = True):
        super().__init__()

        self.setScene(scene)

        self.zoomable = zoomable
        if self.zoomable:
            self.enable_zooming()

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self._cur_scale = self._calculate_scale()

        self.scale_font = QFont()
        self.scale_font.setPointSize(16)

        # Without FullViewportUpdate mode, scale text will not be properly updated when scrolling,
        # Because QGraphicsView::scrollContentsBy contains scroll optimization to update only part of the viewport.
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

    def enable_zooming(self):
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)

        view_smooth_zoom = _ViewSmoothZoom(self, self)
        view_smooth_zoom.zoom_finished.connect(self._update_scale)
        self.viewport().installEventFilter(view_smooth_zoom)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

        painter = QPainter(self.viewport())
        painter.setPen(QColor(123, 184, 234))
        painter.setFont(self.scale_font)
        painter.drawText(self.viewport().rect(), Qt.AlignHCenter | Qt.AlignBottom, f'{self._cur_scale * 100:.0f}%')

    def _calculate_scale(self) -> float:
        cur_transform = self.transform()
        assert cur_transform.m11() == cur_transform.m22(), 'Scaled without keeping aspect ratio'
        return cur_transform.m11()

    def _update_scale(self):
        self._cur_scale = self._calculate_scale()


class _ViewSmoothZoom(QObject):
    zoom_finished = Signal()

    def __init__(self, view, parent: QObject = None):
        super().__init__(parent)

        self.view = view

        self.zoom_in_factor = 0.25
        self.zoom_out_factor = -self.zoom_in_factor

    def eventFilter(self, watched_obj, event):
        if event.type() == QEvent.Wheel:
            self.on_wheel_scrolled(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def on_wheel_scrolled(self, event):
        zoom_factor = self.zoom_in_factor if event.angleDelta().y() > 0 else self.zoom_out_factor
        zoom_factor = 1 + zoom_factor / (SMOOTH_ZOOM_DURATION / SMOOTH_ZOOM_UPDATE_INTERVAL)

        zoom = _Zoom(event.pos(), zoom_factor)
        zoom_time_line = _ZoomTimeLine(SMOOTH_ZOOM_DURATION, self)
        zoom_time_line.setUpdateInterval(SMOOTH_ZOOM_UPDATE_INTERVAL)
        zoom_time_line.valueChanged.connect(partial(self.zoom_view, zoom))
        zoom_time_line.finished.connect(self.zoom_finished)
        zoom_time_line.start()

    def zoom_view(self, zoom, time_line_value):  # PySide signal doesn't work without one more parameter from signal (time_line_value)
        old_pos = self.view.mapToScene(zoom.pos)
        self.view.scale(zoom.factor, zoom.factor)

        new_pos = self.view.mapToScene(zoom.pos)

        # Move the scene's view to old position
        delta = new_pos - old_pos
        self.view.translate(delta.x(), delta.y())


class _Zoom:  # TODO: Use Python 3.7 dataclasses
    def __init__(self, pos, factor):
        self.pos = pos
        self.factor = factor


class _ZoomTimeLine(QTimeLine):
    def __init__(self, duration: int = 1000, parent: QObject = None):
        super().__init__(duration, parent)

        self.finished.connect(self.deleteLater)
