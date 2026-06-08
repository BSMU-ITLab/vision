from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QGraphicsScene

from bsmu.vision.actors import GraphicsActor
from bsmu.vision.actors.shape import VectorElementActor
from bsmu.vision.core.settings import Settings
from bsmu.vision.widgets.viewers.data import DataT, DataViewer
from bsmu.vision.widgets.viewers.graphics_view import GraphicsView, GraphicsViewSettings, ZoomSettings

if TYPE_CHECKING:
    from typing import Callable, Iterator

    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtWidgets import QGraphicsItem, QWidget

    from bsmu.vision.core.config import UnitedConfig
    from bsmu.vision.widgets.viewers.graphics_view import NormalizedViewRegion


SCREEN_TOLERANCE = 8.0


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
        self._graphics_view.zoom_changed.connect(self._on_view_zoom_changed)

        super().__init__(data, parent)

        self.set_content_widget(self._graphics_view)

    @property
    def viewport(self):
        return self._graphics_view.viewport()

    def add_actor(self, actor: GraphicsActor):
        actor.setParent(self)
        actor.adjust_to_view_scale(self._graphics_view.current_scale)
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

    def _get_view_scale(self) -> float:
        """Returns the maximum isotropic scale of the current view transform."""
        transform = self._graphics_view.transform()
        return max(transform.m11(), transform.m22())

    def screen_to_scene_tolerance(self, screen_tolerance: float = SCREEN_TOLERANCE) -> float:
        """Convert screen/pixel tolerance to scene units using isotropic scaling."""
        scale = self._get_view_scale()
        if scale <= 0.0:
            return screen_tolerance  # Safe fallback
        return screen_tolerance / scale

    def _vector_actors_near(
            self,
            scene_pos: QPointF | QPoint,
            scene_tolerance: float,
            mode: Qt.ItemSelectionMode = Qt.ItemSelectionMode.IntersectsItemShape,
            order: Qt.SortOrder = Qt.SortOrder.DescendingOrder,
    ) -> Iterator[VectorElementActor]:
        """Yield vector actors (shapes or nodes) near `scene_pos` within a scene-space tolerance."""
        search_area = QRectF(
            scene_pos.x() - scene_tolerance,
            scene_pos.y() - scene_tolerance,
            scene_tolerance * 2,
            scene_tolerance * 2,
        )
        # `device_transform` is needed for ItemIgnoresTransformations items to hit-test correctly
        device_transform = self._graphics_view.viewportTransform()
        for item in self._graphics_scene.items(search_area, mode, order, device_transform):
            actor_weakref = item.data(GraphicsActor.ACTOR_KEY)
            if actor_weakref and isinstance(actor := actor_weakref(), VectorElementActor):
                yield actor

    def vector_actors_near(
            self,
            scene_pos: QPointF | QPoint,
            screen_tolerance: float = SCREEN_TOLERANCE,
            mode: Qt.ItemSelectionMode = Qt.ItemSelectionMode.IntersectsItemShape,
            order: Qt.SortOrder = Qt.SortOrder.DescendingOrder,
    ) -> list[VectorElementActor]:
        """Return vector actors (shapes or nodes) near `scene_pos` within a screen-space tolerance."""
        scene_tolerance = self.screen_to_scene_tolerance(screen_tolerance)
        return list(self._vector_actors_near(scene_pos, scene_tolerance, mode, order))

    def vector_actor_near(
            self,
            scene_pos: QPointF | QPoint,
            screen_tolerance: float = SCREEN_TOLERANCE,
            mode: Qt.ItemSelectionMode = Qt.ItemSelectionMode.IntersectsItemShape,
            order: Qt.SortOrder = Qt.SortOrder.DescendingOrder,
            predicate: Callable[[VectorElementActor], bool] | None = None,
    ) -> VectorElementActor | None:
        """Return the topmost or nearest vector actor to the scene position.

        Applies standard UX hit-testing rules using the provided screen-space tolerance:
        1. Immediate return if the cursor is inside an element (negative distance).
           Since iteration is top-down, the first match is guaranteed to be topmost.
        2. Otherwise, return the closest element whose edge is within the screen tolerance.
        """
        scene_tolerance = self.screen_to_scene_tolerance(screen_tolerance)
        epsilon = 1e-4  # Prevents float jitter from swapping equally close actors

        nearest_outside_actor: VectorElementActor | None = None
        min_dist = math.inf

        for actor in self._vector_actors_near(scene_pos, scene_tolerance, mode, order):
            if predicate is not None and not predicate(actor):
                continue

            visual_dist = actor.visual_distance_to_scene_pos(scene_pos)
            if visual_dist < 0:
                # Cursor is inside the element.
                # Top-down iteration guarantees this is the topmost element.
                return actor

            # Cursor is outside. Find the closest edge within tolerance.
            if visual_dist <= scene_tolerance and visual_dist < min_dist - epsilon:
                min_dist = visual_dist
                nearest_outside_actor = actor

        return nearest_outside_actor

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

    def _on_view_zoom_changed(self, view_scale: float) -> None:
        pass
