from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QGraphicsScene

from bsmu.vision.actors import GraphicsActor
from bsmu.vision.actors.shape import VectorActor
from bsmu.vision.core.settings import Settings
from bsmu.vision.widgets.viewers.data import DataT, DataViewer
from bsmu.vision.widgets.viewers.graphics_view import GraphicsView, GraphicsViewSettings, ZoomSettings

if TYPE_CHECKING:
    from typing import Callable, Iterator

    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtWidgets import QGraphicsItem, QWidget

    from bsmu.vision.core.config import UnitedConfig
    from bsmu.vision.widgets.viewers.graphics_view import NormalizedViewRegion


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
        self._graphics_scene = QGraphicsScene()

        self._is_syncing_scene_rect = False
        self._top_level_actors: list[GraphicsActor] = []
        self._top_level_bounding_rect: QRectF | None = None

        self._settings = settings
        self._graphics_view = GraphicsView(self._graphics_scene, self._settings.graphics_view_settings)

        super().__init__(data, parent)

        self.set_content_widget(self._graphics_view)

    @property
    def viewport(self):
        return self._graphics_view.viewport()

    def add_actor(self, actor: GraphicsActor):
        actor.setParent(self)
        self._graphics_scene.addItem(actor.graphics_item)

        if actor.graphics_item.parentItem() is None:
            assert actor not in self._top_level_actors, f'The {actor} is already a top-level actor'
            self._top_level_actors.append(actor)
            actor.scene_bounding_rect_changed.connect(self._on_top_level_actor_scene_bounding_rect_changed)

    def remove_actor(self, actor: GraphicsActor):
        if actor.graphics_item.parentItem() is None:
            self._top_level_actors.remove(actor)
            actor.scene_bounding_rect_changed.disconnect(self._on_top_level_actor_scene_bounding_rect_changed)

        self._graphics_scene.removeItem(actor.graphics_item)
        actor.setParent(None)

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

    def map_viewport_to_actor(self, viewport_pos: QPoint, actor: GraphicsActor) -> QPointF:
        scene_pos = self.map_viewport_to_scene(viewport_pos)
        return actor.map_from_scene(scene_pos)

    def map_viewport_to_scene(self, viewport_pos: QPoint) -> QPointF:
        return self._graphics_view.mapToScene(viewport_pos)

    def map_scene_to_viewport(self, scene_pos: QPointF) -> QPoint:
        return self._graphics_view.mapFromScene(scene_pos)

    def map_global_to_scene(self, global_pos: QPoint) -> QPointF:
        viewport_pos = self.viewport.mapFromGlobal(global_pos)
        return self.map_viewport_to_scene(viewport_pos)

    def map_to_actor(self, pos: QPoint, actor: GraphicsActor) -> QPointF:
        # From viewer pos to self._graphics_view pos
        graphics_view_pos = self._graphics_view.mapFrom(self, pos)
        # From self._graphics_view pos to self.viewport pos
        viewport_pos = self.viewport.mapFrom(self._graphics_view, graphics_view_pos)
        return self.map_viewport_to_actor(viewport_pos, actor)

    def _vector_actors_near(
            self,
            scene_pos: QPointF | QPoint,
            screen_tolerance: float = 5.0,
            mode: Qt.ItemSelectionMode = Qt.ItemSelectionMode.IntersectsItemShape,
            order: Qt.SortOrder = Qt.SortOrder.DescendingOrder,
    ) -> Iterator[VectorActor]:
        """Yield vector actors (shapes or nodes) near `scene_pos` within a screen-space tolerance."""
        transform = self._graphics_view.transform()
        scale_x = transform.m11()
        scale_y = transform.m22()
        if scale_x == 0 or scale_y == 0:
            return

        scene_tolerance_x = screen_tolerance / scale_x
        scene_tolerance_y = screen_tolerance / scale_y
        search_area = QRectF(
            scene_pos.x() - scene_tolerance_x, scene_pos.y() - scene_tolerance_y,
            scene_tolerance_x * 2, scene_tolerance_y * 2,
        )
        for item in self._graphics_scene.items(search_area, mode, order):
            actor_weakref = item.data(GraphicsActor.ACTOR_KEY)
            if actor_weakref and isinstance(actor := actor_weakref(), VectorActor):
                yield actor

    def vector_actors_near(
            self,
            scene_pos: QPointF | QPoint,
            screen_tolerance: float = 5.0,
            mode: Qt.ItemSelectionMode = Qt.ItemSelectionMode.IntersectsItemShape,
            order: Qt.SortOrder = Qt.SortOrder.DescendingOrder,
    ) -> list[VectorActor]:
        """Return vector actors (shapes or nodes) near `scene_pos` within a screen-space tolerance."""
        return list(self._vector_actors_near(scene_pos, screen_tolerance, mode, order))

    def vector_actor_near(
            self,
            scene_pos: QPointF | QPoint,
            screen_tolerance: float = 5.0,
            mode: Qt.ItemSelectionMode = Qt.ItemSelectionMode.IntersectsItemShape,
            order: Qt.SortOrder = Qt.SortOrder.DescendingOrder,
            predicate: Callable[[VectorActor], bool] | None = None,
    ) -> VectorActor | None:
        """
        Return the first vector actor (shape or node) near `scene_pos` within a screen-space tolerance,
        optionally filtered by `predicate`.
        """
        for actor in self._vector_actors_near(scene_pos, screen_tolerance, mode, order):
            if predicate is None or predicate(actor):
                return actor
        return None

    @property
    def top_level_bounding_rect(self) -> QRectF:
        if self._top_level_bounding_rect is None:
            self._top_level_bounding_rect = self._calculate_top_level_bounding_rect()
        return self._top_level_bounding_rect

    def _on_top_level_actor_scene_bounding_rect_changed(self) -> None:
        self._top_level_bounding_rect = None
        self._sync_scene_rect_with_bounding_rect()

    def _calculate_top_level_bounding_rect(self) -> QRectF:
        union_rect = QRectF()
        for item in self._graphics_scene.items():
            # Parent is None for top-level items
            if item.parentItem() is not None:
                continue

            union_rect = union_rect.united(item.sceneBoundingRect())

        return union_rect

    def fit_content_in(self) -> None:
        self._graphics_view.fit_in_view(self.top_level_bounding_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def capture_normalized_view_region(self) -> NormalizedViewRegion | None:
        return self._graphics_view.capture_normalized_view_region()

    def restore_normalized_view_region(self, normalized_view_region: NormalizedViewRegion | None) -> None:
        self._graphics_view.restore_normalized_view_region(normalized_view_region)

    def _sync_scene_rect_with_bounding_rect(self, rect: QRectF | None = None) -> None:
        if self._is_syncing_scene_rect:
            return

        self._is_syncing_scene_rect = True

        if rect is None:
            rect = self.top_level_bounding_rect
        self._graphics_view.set_scrollable_scene_rect(rect)

        self._is_syncing_scene_rect = False
