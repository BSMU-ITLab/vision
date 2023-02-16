from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QObject, Signal, QTimeLine, QEvent, QRect, QRectF, QPointF
from PySide6.QtGui import QPainter, QFont, QColor, QPainterPath, QPen, QFontMetrics
from PySide6.QtWidgets import QGraphicsView

from bsmu.vision.core.settings import Settings

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintEvent, QResizeEvent
    from PySide6.QtWidgets import QGraphicsScene


SMOOTH_ZOOM_DURATION = 100
SMOOTH_ZOOM_UPDATE_INTERVAL = 10


class GraphicsViewSettings(Settings):
    def __init__(self, zoomable: bool = True, zoom_settings: ZoomSettings = None):
        super().__init__()

        self._zoomable = zoomable
        self._zoom_settings = zoom_settings

    @property
    def zoomable(self) -> bool:
        return self._zoomable

    @property
    def zoom_settings(self) -> ZoomSettings:
        return self._zoom_settings


class GraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, settings: GraphicsViewSettings):
        super().__init__()

        self.setScene(scene)

        self._settings = settings
        if self._settings.zoomable:
            self.enable_zooming()

        self._cur_scale = self._calculate_scale()

        self._scale_font = QFont()
        self._scale_font.setPointSize(16)
        self._scale_font.setBold(True)
        self._scale_font_metrics = QFontMetrics(self._scale_font)
        self._scale_text_rect = QRect()

        self._viewport_anchors = None
        self._reset_viewport_anchors()
        self._viewport_anchoring = False

        self._viewport_anchoring_scheduled = False
        scene.sceneRectChanged.connect(self._reset_viewport_anchors)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Without FullViewportUpdate mode, scale text will not be properly updated when scrolling,
        # Because QGraphicsView::scrollContentsBy contains scroll optimization to update only part of the viewport.
        # self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # Now we override the scrollContentsBy method instead of changing the mode to FullViewportUpdate

    def enable_zooming(self):
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)

        view_smooth_zoom = _ViewSmoothZoom(self, self._settings.zoom_settings, self)
        view_smooth_zoom.zoom_finished.connect(self._on_zoom_finished)
        self.viewport().installEventFilter(view_smooth_zoom)

    def set_visualized_scene_rect(self, rect: QRectF):
        self.setSceneRect(rect)

        self._update_viewport_anchors()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

        if self._viewport_anchoring_scheduled:
            self._anchor_viewport()
            self._viewport_anchoring_scheduled = False

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(123, 184, 234))
        painter.setPen(QPen(Qt.white, 0.5))

        scale_text = f'{self._cur_scale * 100:.0f}%'
        scale_text_bounding_rect = self._scale_font_metrics.boundingRect(scale_text)
        viewport_rect = self.viewport().rect()
        # Align the scale text to (Qt.AlignHCenter | Qt.AlignBottom)
        pad = 2
        self._scale_text_rect = QRect(viewport_rect.width() / 2 - scale_text_bounding_rect.width() / 2,
                                      viewport_rect.height() - scale_text_bounding_rect.height() - 6,
                                      scale_text_bounding_rect.width(), scale_text_bounding_rect.height())\
            .adjusted(-pad, -pad, pad, pad)  # add pads to update when scrolling without artifacts

        # Use QPainterPath to draw text with outline
        path = QPainterPath()
        path.addText(self._scale_text_rect.bottomLeft(), self._scale_font, scale_text)
        painter.drawPath(path)

    def scrollContentsBy(self, dx: int, dy: int):
        super().scrollContentsBy(dx, dy)

        # Update old (to clear text) and new rectangles (to draw) with the scale text
        self.viewport().update(self._scale_text_rect)
        self.viewport().update(self._scale_text_rect.translated(dx, dy))

        self._update_viewport_anchors()

    def _calculate_scale(self) -> float:
        cur_transform = self.transform()
        assert cur_transform.m11() == cur_transform.m22(), 'Scaled without keeping aspect ratio'
        return cur_transform.m11()

    def _update_scale(self):
        self._cur_scale = self._calculate_scale()

    def _on_zoom_finished(self):
        self._update_scale()
        self._update_viewport_anchors()

    def _update_viewport_anchors(self):
        if self._viewport_anchoring:
            return

        scene_rect = self.sceneRect()
        if scene_rect.isEmpty():
            return

        scene_size = np.array([scene_rect.width(), scene_rect.height()])

        viewport_rect = self.viewport().rect()
        top_left_viewport_point = self.mapToScene(viewport_rect.topLeft())
        bottom_right_viewport_point = self.mapToScene(viewport_rect.bottomRight())

        self._viewport_anchors[0] = np.array([top_left_viewport_point.x(), top_left_viewport_point.y()]) / scene_size
        self._viewport_anchors[1] = \
            np.array([bottom_right_viewport_point.x(), bottom_right_viewport_point.y()]) / scene_size

    def resizeEvent(self, resize_event: QResizeEvent):
        self._schedule_viewport_anchoring()

    def _schedule_viewport_anchoring(self):
        self._viewport_anchoring_scheduled = True

    def _reset_viewport_anchors(self):
        self._viewport_anchors = np.array([[0, 0], [1, 1]], dtype=float)
        self._schedule_viewport_anchoring()

    def _anchor_viewport(self):
        self._viewport_anchoring = True

        scene_rect = self.sceneRect()
        scene_size = np.array([scene_rect.width(), scene_rect.height()])

        viewport_rect_angle_point_coords = self._viewport_anchors * scene_size
        viewport_rect = QRectF(QPointF(*viewport_rect_angle_point_coords[0]),
                               QPointF(*viewport_rect_angle_point_coords[1]))
        self.fit_in_view(viewport_rect, Qt.KeepAspectRatio)

        self._viewport_anchoring = False

    def fit_in_view(self, rect: QRectF, aspect_ratio_mode: Qt.AspectRatioMode = Qt.IgnoreAspectRatio):
        self.fitInView(rect, aspect_ratio_mode)

        self._update_scale()
        self._update_viewport_anchors()


class ZoomSettings(Settings):
    zoom_factor_changed = Signal(float)

    def __init__(self, zoom_factor: float = 1):
        super().__init__()

        self._zoom_factor = zoom_factor

    @property
    def zoom_factor(self) -> float:
        return self._zoom_factor

    @zoom_factor.setter
    def zoom_factor(self, value: float):
        if self._zoom_factor != value:
            self._zoom_factor = value
            self.zoom_factor_changed.emit(self._zoom_factor)


class _ViewSmoothZoom(QObject):
    zoom_finished = Signal()

    def __init__(self, view, settings: ZoomSettings, parent: QObject = None):
        super().__init__(parent)

        self.view = view

        self._settings = settings

    def eventFilter(self, watched_obj, event):
        if event.type() == QEvent.Wheel:
            self.on_wheel_scrolled(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def on_wheel_scrolled(self, event):
        angle_in_degrees = event.angleDelta().y() / 8
        zoom_factor = angle_in_degrees / 60 * self._settings.zoom_factor
        zoom_factor = 1 + zoom_factor / (SMOOTH_ZOOM_DURATION / SMOOTH_ZOOM_UPDATE_INTERVAL)

        zoom = _Zoom(event.position(), zoom_factor)
        zoom_time_line = _ZoomTimeLine(SMOOTH_ZOOM_DURATION, self)
        zoom_time_line.setUpdateInterval(SMOOTH_ZOOM_UPDATE_INTERVAL)
        zoom_time_line.valueChanged.connect(partial(self.zoom_view, zoom))
        zoom_time_line.finished.connect(self.zoom_finished)
        zoom_time_line.start()

    def zoom_view(self, zoom, time_line_value):  # PySide signal doesn't work without one more parameter from signal (time_line_value)
        old_pos = self.view.mapToScene(zoom.pos.toPoint())
        self.view.scale(zoom.factor, zoom.factor)

        new_pos = self.view.mapToScene(zoom.pos.toPoint())

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
