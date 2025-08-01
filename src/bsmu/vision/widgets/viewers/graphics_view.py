from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QObject, Signal, QTimeLine, QEvent, QRect, QRectF, QPointF
from PySide6.QtGui import QPainter, QFont, QColor, QPainterPath, QPen, QFontMetrics
from PySide6.QtWidgets import QGraphicsView

from bsmu.vision.core.settings import Settings

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintEvent, QResizeEvent, QMouseEvent
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
    zoom_finished = Signal()
    scrollable_reset = Signal()

    def __init__(self, scene: QGraphicsScene, settings: GraphicsViewSettings):
        super().__init__()

        self.setScene(scene)

        self._is_using_base_cursor: bool = True

        self._view_pan: _ViewPan | None = None
        self._is_scrollable: bool | None = None

        self._settings = settings
        if self._settings.zoomable:
            self.enable_zooming()
        self.enable_panning()

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

    @property
    def is_scrollable(self) -> bool:
        if self._is_scrollable is None:
            transformed_scene_rect = self.transform().mapRect(self.sceneRect())
            viewport_rect = self.viewport().rect()

            can_scroll_horizontally = transformed_scene_rect.width() > viewport_rect.width()
            can_scroll_vertically = transformed_scene_rect.height() > viewport_rect.height()

            self._is_scrollable = can_scroll_horizontally or can_scroll_vertically
        return self._is_scrollable

    @property
    def is_using_base_cursor(self) -> bool:
        return self._is_using_base_cursor

    @is_using_base_cursor.setter
    def is_using_base_cursor(self, value: bool):
        if self._is_using_base_cursor != value:
            self._is_using_base_cursor = value
            if self._is_using_base_cursor:
                self._update_cursor()

    def _update_cursor(self):
        if self._view_pan.is_active:
            self._view_pan.update_cursor()

    def enable_zooming(self):
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)

        view_smooth_zoom = _ViewSmoothZoom(self, self._settings.zoom_settings, self)
        view_smooth_zoom.zoom_finished.connect(self._on_zoom_finished)
        view_smooth_zoom.zoom_finished.connect(self.zoom_finished)
        self.viewport().installEventFilter(view_smooth_zoom)

    def enable_panning(self):
        # We can use |setDragMode| method, but that will not allow to add some inertia after drag
        # (like during drag and scroll on mobile phones)
        # self.setDragMode(QGraphicsView.ScrollHandDrag)

        if self._view_pan is None:
            self._view_pan = _ViewPan(self, self)
        self._view_pan.activate()

    def disable_panning(self):
        if self._view_pan is not None:
            self._view_pan.deactivate()

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

    def set_cursor(self, cursor_shape: Qt.CursorShape):
        self.viewport().setCursor(cursor_shape)

    def _reset_scrollable(self):
        if self._is_scrollable is not None:
            self._is_scrollable = None
            self.scrollable_reset.emit()

    def _calculate_scale(self) -> float:
        cur_transform = self.transform()
        assert cur_transform.m11() == cur_transform.m22(), 'Scaled without keeping aspect ratio'
        return cur_transform.m11()

    def _update_scale(self):
        self._cur_scale = self._calculate_scale()

    def _on_zoom_finished(self):
        self._update_scale()
        self._reset_scrollable()
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


class _ViewPan(QObject):
    def __init__(self, view: GraphicsView, parent: QObject = None):
        super().__init__(parent)

        self._view = view

        self._old_pos = None

        self._is_active = False

        self._view.scrollable_reset.connect(self.update_cursor)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_panning(self) -> bool:
        return self._old_pos is not None

    def activate(self):
        if self._is_active:
            return

        self._view.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.update_cursor()
        self._view.viewport().installEventFilter(self)

        self._is_active = True

    def deactivate(self):
        if not self._is_active:
            return

        self._view.viewport().removeEventFilter(self)

        self._reset()

        self._is_active = False

    def eventFilter(self, watched_obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._old_pos = self.event_pos(event)
            self.update_cursor()
            return False
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self.is_panning:
            self._old_pos = None
            self.update_cursor()
            return False
        elif event.type() == QEvent.MouseMove and event.buttons() == Qt.LeftButton and self.is_panning:
            new_pos = self.event_pos(event)
            delta = self._view.mapToScene(new_pos.toPoint()) - self._view.mapToScene(self._old_pos.toPoint())
            self._view.translate(delta.x(), delta.y())
            self._old_pos = new_pos
            return False
        else:
            return super().eventFilter(watched_obj, event)

    @staticmethod
    def event_pos(event: QMouseEvent):
        return event.position()

    def _reset(self):
        self._old_pos = None
        self._view.viewport().unsetCursor()

    def _set_cursor(self, cursor_shape: Qt.CursorShape):
        self._view.set_cursor(cursor_shape)

    def update_cursor(self):
        if not self._view.is_using_base_cursor:
            return

        if self._view.is_scrollable:
            cursor_shape = Qt.ClosedHandCursor if self.is_panning else Qt.OpenHandCursor
        else:
            cursor_shape = Qt.ArrowCursor
        self._set_cursor(cursor_shape)
