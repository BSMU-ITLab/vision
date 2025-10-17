from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt, QObject, Signal, QTimeLine, QTimer, QEvent, QRect, QRectF, QPointF
from PySide6.QtGui import QPainter, QFont, QColor, QPainterPath, QPen, QFontMetrics, QWheelEvent, QMouseEvent
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


@dataclass
class NormalizedViewRegion:
    min_ratio: float
    center: QPointF


class GraphicsView(QGraphicsView):
    zoom_finished = Signal()
    pan_finished = Signal()
    scrollable_invalidated = Signal()
    scrollable_changed = Signal(bool)

    def __init__(self, scene: QGraphicsScene, settings: GraphicsViewSettings):
        super().__init__()

        self.setScene(scene)

        self._is_using_base_cursor: bool = True

        self._view_pan: _ViewPan | None = None
        self._is_scrollable: bool = False  # Last computed scrollability state
        self._is_scrollable_valid: bool = True  # False if scrollability must be recomputed

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

        self._viewport_rect_in_scene: QRectF | None = None

        self._min_ratio: float | None = None
        self._anchor_rect: QRectF | None = None
        self._aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio

        self._is_fitting_in_anchor_rect = False
        self._is_scene_rect_changing = False

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Without FullViewportUpdate mode, scale text will not be properly updated when scrolling,
        # Because QGraphicsView::scrollContentsBy contains scroll optimization to update only part of the viewport.
        # self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # Now we override the scrollContentsBy method instead of changing the mode to FullViewportUpdate

    @property
    def is_scrollable(self) -> bool:
        # Returns the last computed scrollability state.
        # Note: may be stale if _is_scrollable_valid is False.
        return self._is_scrollable

    def _update_scrollable(self):
        h = self.horizontalScrollBar()
        v = self.verticalScrollBar()
        can_scroll_horizontally = h.maximum() > h.minimum()
        can_scroll_vertically = v.maximum() > v.minimum()
        new_is_scrollable = can_scroll_horizontally or can_scroll_vertically
        self._is_scrollable_valid = True
        if self._is_scrollable != new_is_scrollable:
            self._is_scrollable = new_is_scrollable
            self.scrollable_changed.emit(self._is_scrollable)

    def _invalidate_scrollable(self):
        if self._is_scrollable_valid:
            self._is_scrollable_valid = False
            self.scrollable_invalidated.emit()
            # Defer the update until the next event loop cycle,
            # ensuring that Qt has updated the scrollbars before we recompute.
            QTimer.singleShot(0, self._update_scrollable)

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
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

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
            self._view_pan.pan_finished.connect(self._on_pan_finished)
            self._view_pan.pan_finished.connect(self.pan_finished)
        self._view_pan.activate()

    def disable_panning(self):
        if self._view_pan is not None:
            self._view_pan.deactivate()

    def set_scrollable_scene_rect(self, rect: QRectF):
        self._is_scene_rect_changing = True
        self.setSceneRect(rect)
        self._is_scene_rect_changing = False

        self._invalidate_scrollable()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(123, 184, 234))
        painter.setPen(QPen(Qt.GlobalColor.white, 0.5))

        scale_text = f'{self._cur_scale * 100:.0f}%'
        scale_text_bounding_rect = self._scale_font_metrics.boundingRect(scale_text)
        viewport_rect = self.viewport().rect()
        # Align the scale text to (Qt.AlignHCenter | Qt.AlignBottom)
        pad = 2
        self._scale_text_rect = QRect(
            int(viewport_rect.width() / 2 - scale_text_bounding_rect.width() / 2),
            viewport_rect.height() - scale_text_bounding_rect.height() - 6,
            scale_text_bounding_rect.width(),
            scale_text_bounding_rect.height()
        ).adjusted(-pad, -pad, pad, pad)  # Add pads to update when scrolling without artifacts

        # Use QPainterPath to draw text with outline
        path = QPainterPath()
        path.addText(self._scale_text_rect.bottomLeft(), self._scale_font, scale_text)
        painter.drawPath(path)

    def resizeEvent(self, resize_event: QResizeEvent):
        self._fit_in_anchor_rect()

        super().resizeEvent(resize_event)

    def scrollContentsBy(self, dx: int, dy: int):
        super().scrollContentsBy(dx, dy)

        # Update old (to clear text) and new rectangles (to draw) with the scale text
        self.viewport().update(self._scale_text_rect)
        self.viewport().update(self._scale_text_rect.translated(dx, dy))

        self._refresh_viewport_region()

    def fit_in_view(self, rect: QRectF, aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio):
        self._anchor_rect = rect
        self._aspect_ratio_mode = aspect_ratio_mode
        self._fit_in_anchor_rect()
        self._update_viewport_rect_in_scene()

    def capture_normalized_view_region(self) -> NormalizedViewRegion | None:
        if self._should_display_full_scene():
            return None  # Or we can return NormalizedViewRegion(1.0, QPointF(0.5, 0.5))

        if self._min_ratio is None:
            self._min_ratio = self._calculate_min_ratio()

        viewport_center_in_scene = self._viewport_rect_in_scene.center()
        normalized_center = QPointF(
            viewport_center_in_scene.x() / self.sceneRect().width(),
            viewport_center_in_scene.y() / self.sceneRect().height()
        )
        return NormalizedViewRegion(self._min_ratio, normalized_center)

    def restore_normalized_view_region(self, normalized_view_region: NormalizedViewRegion | None):
        scene_rect = self.sceneRect()
        if normalized_view_region is None:
            self._anchor_rect = scene_rect
        else:
            center = QPointF(normalized_view_region.center.x() * scene_rect.width(),
                             normalized_view_region.center.y() * scene_rect.height())
            self._anchor_rect = self._build_anchor_rect(normalized_view_region.min_ratio, center)

        self._fit_in_anchor_rect()

        if normalized_view_region is None:
            self._viewport_rect_in_scene = None
        else:
            self._update_viewport_rect_in_scene()

    def _on_pan_finished(self):
        self._refresh_viewport_region()

    def set_cursor(self, cursor_shape: Qt.CursorShape):
        self.viewport().setCursor(cursor_shape)

    def _calculate_scale(self) -> float:
        cur_transform = self.transform()
        assert cur_transform.m11() == cur_transform.m22(), 'Scaled without keeping aspect ratio'
        return cur_transform.m11()

    def _update_scale(self):
        self._cur_scale = self._calculate_scale()

    def _on_zoom_finished(self):
        self._update_scale()
        self._invalidate_scrollable()

        self._refresh_viewport_region()

    def _refresh_viewport_region(self):
        if self._is_fitting_in_anchor_rect or self._is_scene_rect_changing:
            return

        scene_rect = self.sceneRect()
        if scene_rect.isEmpty():
            return

        self._update_viewport_rect_in_scene()
        self._min_ratio = None
        self._anchor_rect = None

    def _update_viewport_rect_in_scene(self):
        viewport_rect = self.viewport().rect()
        self._viewport_rect_in_scene = self.mapToScene(viewport_rect).boundingRect()

    def _should_display_full_scene(self) -> bool:
        return self._viewport_rect_in_scene is None

    def _calculate_min_ratio(self) -> float:
        width_ratio = self._viewport_rect_in_scene.width() / self.sceneRect().width()
        height_ratio = self._viewport_rect_in_scene.height() / self.sceneRect().height()
        return min(width_ratio, height_ratio)

    def _build_anchor_rect(self, min_ratio: float, center: QPointF) -> QRectF:
        scene_rect = self.sceneRect()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()

        new_width = scene_width * min_ratio
        new_height = scene_height * min_ratio

        # Build rectangle centered at `center`
        top_left = QPointF(
            center.x() - new_width / 2,
            center.y() - new_height / 2
        )
        bottom_right = QPointF(
            center.x() + new_width / 2,
            center.y() + new_height / 2
        )
        return QRectF(top_left, bottom_right)

    def _determine_anchor_rect(self) -> QRectF | None:
        """Decide which anchor rect should be used based on current state."""
        scene_rect = self.sceneRect()
        if scene_rect.isEmpty():
            return None

        if self._should_display_full_scene():
            return scene_rect

        self._min_ratio = self._calculate_min_ratio()
        return self._build_anchor_rect(self._min_ratio, self._viewport_rect_in_scene.center())

    def _fit_in_anchor_rect(self):
        self._is_fitting_in_anchor_rect = True

        if self._anchor_rect is None:
            self._anchor_rect = self._determine_anchor_rect()

        if self._anchor_rect is not None:
            self.fitInView(self._anchor_rect, self._aspect_ratio_mode)
            self._update_scale()

        self._is_fitting_in_anchor_rect = False


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

    def __init__(self, view: QGraphicsView, settings: ZoomSettings, parent: QObject = None):
        super().__init__(parent)

        self._view = view

        self._settings = settings

    def eventFilter(self, watched_obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            wheel_event = cast(QWheelEvent, event)
            self._on_wheel_scrolled(wheel_event)
            return True

        return super().eventFilter(watched_obj, event)

    def _on_wheel_scrolled(self, event: QWheelEvent):
        angle_in_degrees = event.angleDelta().y() / 8
        zoom_factor = angle_in_degrees / 60 * self._settings.zoom_factor
        zoom_factor = 1 + zoom_factor / (SMOOTH_ZOOM_DURATION / SMOOTH_ZOOM_UPDATE_INTERVAL)

        zoom = _Zoom(event.position(), zoom_factor)
        zoom_time_line = _ZoomTimeLine(SMOOTH_ZOOM_DURATION, self)
        zoom_time_line.setUpdateInterval(SMOOTH_ZOOM_UPDATE_INTERVAL)
        zoom_time_line.valueChanged.connect(partial(self._zoom_view, zoom))
        zoom_time_line.finished.connect(self.zoom_finished)
        zoom_time_line.start()

    def _zoom_view(self, zoom: _Zoom, _time_line_value: float):
        # The PySide signal requires an extra parameter (_time_line_value),
        # even though it is not used in this method.
        old_pos = self._view.mapToScene(zoom.pos.toPoint())
        self._view.scale(zoom.factor, zoom.factor)

        new_pos = self._view.mapToScene(zoom.pos.toPoint())

        # Move the scene's view to old position
        delta = new_pos - old_pos
        self._view.translate(delta.x(), delta.y())


@dataclass
class _Zoom:
    pos: QPointF
    factor: float


class _ZoomTimeLine(QTimeLine):
    def __init__(self, duration: int = 1000, parent: QObject = None):
        super().__init__(duration, parent)

        self.finished.connect(self.deleteLater)


class _ViewPan(QObject):
    pan_finished = Signal()

    def __init__(self, view: GraphicsView, parent: QObject = None):
        super().__init__(parent)

        self._view = view

        self._old_pos = None

        self._is_active = False

        self._view.scrollable_changed.connect(self.update_cursor)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_panning(self) -> bool:
        return self._old_pos is not None

    def activate(self):
        if self._is_active:
            return

        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.update_cursor()
        self._view.viewport().installEventFilter(self)

        self._is_active = True

    def deactivate(self):
        if not self._is_active:
            return

        self._view.viewport().removeEventFilter(self)

        self._reset()

        self._is_active = False

    def eventFilter(self, watched_obj: QObject, event: QEvent) -> bool:
        if not isinstance(event, QMouseEvent):
            return super().eventFilter(watched_obj, event)

        match event.type():
            case QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton and self._view.is_scrollable:
                    self._old_pos = self.event_pos(event)
                    self.update_cursor()
                    return False
            case QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self.is_panning:
                    self._old_pos = None
                    self.update_cursor()
                    self.pan_finished.emit()
                    return False
            case QEvent.Type.MouseMove:
                if self.is_panning:
                    new_pos = self.event_pos(event)
                    delta = self._view.mapToScene(new_pos.toPoint()) - self._view.mapToScene(self._old_pos.toPoint())
                    self._view.translate(delta.x(), delta.y())
                    self._old_pos = new_pos
                    return False

        return super().eventFilter(watched_obj, event)

    @staticmethod
    def event_pos(event: QMouseEvent) -> QPointF:
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
            cursor_shape = Qt.CursorShape.ClosedHandCursor if self.is_panning else Qt.CursorShape.OpenHandCursor
        else:
            cursor_shape = Qt.CursorShape.ArrowCursor
        self._set_cursor(cursor_shape)
