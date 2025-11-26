from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsObject

from bsmu.vision.core.settings import Settings
from bsmu.vision.widgets.viewers.data import DataT, DataViewer
from bsmu.vision.widgets.viewers.graphics_view import GraphicsView, GraphicsViewSettings, ZoomSettings

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtWidgets import QGraphicsItem, QWidget

    from bsmu.vision.core.config import UnitedConfig
    from bsmu.vision.widgets.viewers.graphics_view import NormalizedViewRegion


class BaseGraphicsObject(QGraphicsObject):
    bounding_rect_changed = Signal(QRectF)

    def __init__(self, parent: QGraphicsItem = None):
        super().__init__(parent)

        self._bounding_rect_cache = None
        self._bounding_rect_cache_before_reset = None

    def boundingRect(self):
        if self._bounding_rect_cache is None:
            self._bounding_rect_cache = self._calculate_bounding_rect()
            if self._bounding_rect_cache != self._bounding_rect_cache_before_reset:
                self.bounding_rect_changed.emit(self._bounding_rect_cache)
        return self._bounding_rect_cache

    def _calculate_bounding_rect(self) -> QRectF:
        raise NotImplementedError(f'{self.__class__.__name__} must implement _calculate_bounding_rect')

    def _reset_bounding_rect_cache(self):
        if self._bounding_rect_cache is not None:
            self.prepareGeometryChange()
            self._bounding_rect_cache_before_reset = self._bounding_rect_cache
            self._bounding_rect_cache = None


class ImageViewerSettings(Settings):
    def __init__(self, graphics_view_settings: GraphicsViewSettings):
        super().__init__()

        self._graphics_view_settings = graphics_view_settings

    @property
    def graphics_view_settings(self) -> GraphicsViewSettings:
        return self._graphics_view_settings

    @classmethod
    def from_config(cls, config: UnitedConfig) -> ImageViewerSettings:
        return cls(
            GraphicsViewSettings(
                zoomable=config.value('zoomable', True),
                zoom_settings=ZoomSettings(config.value('zoom_factor', 1))
            )
        )


class GraphicsViewer(DataViewer[DataT]):
    def __init__(self, data: DataT = None, settings: ImageViewerSettings = None, parent: QWidget = None):
        super().__init__(data, parent)

        self._settings = settings

        self._is_syncing_scene_rect = False

        self._main_graphics_object = self._create_main_graphics_object()
        self._main_graphics_object.bounding_rect_changed.connect(
            self._on_main_graphics_object_bounding_rect_changed)
        # self._main_graphics_object.bounding_rect_changed.connect(
        #     self._graphics_scene.setSceneRect)

        self._graphics_scene = QGraphicsScene()
        self._graphics_view = GraphicsView(self._graphics_scene, self._settings.graphics_view_settings)

        self._graphics_scene.addItem(self._main_graphics_object)

        self.set_content_widget(self._graphics_view)

    @property
    def viewport(self):
        return self._graphics_view.viewport()

    def _create_main_graphics_object(self) -> BaseGraphicsObject:
        """Override this method in subclasses to create the specific graphics object"""
        raise NotImplementedError(f'{self.__class__.__name__} must implement _create_main_graphics_object')

    def add_graphics_item(self, item: QGraphicsItem):
        self._graphics_scene.addItem(item)

    def remove_graphics_item(self, item: QGraphicsItem):
        self._graphics_scene.removeItem(item)

    def enable_panning(self):
        self._graphics_view.enable_panning()

    def disable_panning(self):
        self._graphics_view.disable_panning()

    def _on_cursor_owner_changed(self):
        self._graphics_view.is_using_base_cursor = self._cursor_owner is None

    def map_viewport_to_content(self, viewport_pos: QPoint) -> QPointF:
        scene_pos = self._graphics_view.mapToScene(viewport_pos)
        return self._main_graphics_object.mapFromScene(scene_pos)

    def map_viewport_to_scene(self, viewport_pos: QPoint) -> QPointF:
        return self._graphics_view.mapToScene(viewport_pos)

    def map_scene_to_viewport(self, scene_pos: QPointF) -> QPoint:
        return self._graphics_view.mapFromScene(scene_pos)

    def map_global_to_scene(self, global_pos: QPoint) -> QPointF:
        viewport_pos = self.viewport.mapFromGlobal(global_pos)
        return self.map_viewport_to_scene(viewport_pos)

    def map_to_content(self, pos: QPoint) -> QPointF:
        # From viewer pos to self._graphics_view pos
        graphics_view_pos = self._graphics_view.mapFrom(self, pos)
        # From self._graphics_view pos to self.viewport pos
        viewport_pos = self.viewport.mapFrom(self._graphics_view, graphics_view_pos)
        return self.map_viewport_to_content(viewport_pos)

    def fit_content_in(self):
        self._graphics_view.fit_in_view(
            self._main_graphics_object.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def capture_normalized_view_region(self) -> NormalizedViewRegion | None:
        return self._graphics_view.capture_normalized_view_region()

    def restore_normalized_view_region(self, normalized_view_region: NormalizedViewRegion | None):
        self._sync_scene_rect_with_bounding_rect()
        self._graphics_view.restore_normalized_view_region(normalized_view_region)

    def _on_main_graphics_object_bounding_rect_changed(self, rect: QRectF):
        self._sync_scene_rect_with_bounding_rect(rect)

    def _sync_scene_rect_with_bounding_rect(self, rect: QRectF | None = None):
        if self._is_syncing_scene_rect:
            return

        self._is_syncing_scene_rect = True

        if rect is None:
            rect = self._main_graphics_object.boundingRect()
        self._graphics_view.set_scrollable_scene_rect(rect)

        self._is_syncing_scene_rect = False
