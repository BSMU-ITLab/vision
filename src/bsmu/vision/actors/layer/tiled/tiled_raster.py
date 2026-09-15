from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QRect, QRectF, QTimer, Signal
from PySide6.QtGui import QImage, QTransform, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

from bsmu.vision.actors.layer import LayerActor
from bsmu.vision.actors.layer.tiled.tile_cache import TileCache, RenderTile
from bsmu.vision.actors.layer.tiled.tile_layer_item import TileLayerItem
from bsmu.vision.actors.layer.tiled.tile_loader import TileLoader
from bsmu.vision.core.converters.image import numpy_array_to_qimage
from bsmu.vision.core.data.level_selector import BalancedLevelSelector
from bsmu.vision.core.layers import RasterLayer

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from bsmu.vision.actors.layer.tiled.tile_loader import LoadedTile
    from bsmu.vision.core.data.tiled_backend import TiledBackend


class TiledRasterContainerItem(QGraphicsItem):
    """Non-rendering container that holds overview, fallback and current tile layers.
    Provides correct boundingRect so the scene knows the slide dimensions."""

    def __init__(self, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._bounding_rect = QRectF()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def set_slide_size(self, width: int, height: int) -> None:
        self.prepareGeometryChange()
        self._bounding_rect = QRectF(0, 0, width, height)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounding_rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None) -> None:
        pass


class TiledRasterLayerActor(LayerActor[RasterLayer, TiledRasterContainerItem]):
    """Actor for tiled (WSI) raster rendering with multi-level pyramid support."""

    TILE_UPDATE_INTERVAL_MS = 30
    PREFETCH_MARGIN = 1

    level_changed = Signal(int)

    def __init__(self, model: RasterLayer | None = None, parent: QObject | None = None) -> None:
        self._backend: TiledBackend | None = None
        self._cache = TileCache(max_memory_mb=512)
        self._loader: TileLoader | None = None
        self._level_selector = BalancedLevelSelector()
        self._inflight: set[tuple[int, int, int]] = set()

        self._overview_item: QGraphicsPixmapItem | None = None
        self._fallback_item: TileLayerItem | None = None
        self._current_item: TileLayerItem | None = None

        self._last_scene_rect: QRectF | None = None
        self._last_tile_request_ms = -math.inf

        self._tile_request_timer: QTimer | None = None

        super().__init__(model, parent)

        # Tile update throttling
        self._tile_request_timer = QTimer(self)
        self._tile_request_timer.setSingleShot(True)
        self._tile_request_timer.setInterval(self.TILE_UPDATE_INTERVAL_MS)
        self._tile_request_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tile_request_timer.timeout.connect(self._request_visible_tiles)

        if self._backend is not None:
            self._request_visible_tiles()

    def _create_graphics_item(self) -> TiledRasterContainerItem:
        return TiledRasterContainerItem()

    def _model_about_to_change(self, new_model: RasterLayer | None) -> None:
        if self.layer is not None:
            self._teardown()

        super()._model_about_to_change(new_model)

    def _model_changed(self) -> None:
        super()._model_changed()

        raster = self.data
        if raster is None or not raster.is_tiled:
            return
        self._setup(raster.backend)

    def update_visible_region(self, scene_rect: QRectF) -> None:
        """Called by the viewer when the visible viewport area changes."""
        self._last_scene_rect = scene_rect
        self._schedule_tile_update()

    def _on_view_scale_changed(self) -> None:
        """Called via adjust_to_view_scale when zoom changes."""
        self._auto_select_level()
        self._schedule_tile_update()

    def _setup(self, backend: TiledBackend) -> None:
        self._backend = backend
        container = self.graphics_item

        # Overview (background)
        overview = self._backend.read_overview()
        overview_qimage = numpy_array_to_qimage(overview, image_format=QImage.Format.Format_RGB888)
        overview_pixmap = QPixmap.fromImage(overview_qimage)
        self._overview_item = QGraphicsPixmapItem(overview_pixmap, container)
        slide_w, slide_h = self._backend.slide_size
        pm_w, pm_h = overview_pixmap.width(), overview_pixmap.height()
        self._overview_item.setTransform(QTransform.fromScale(slide_w / pm_w, slide_h / pm_h))
        self._overview_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._overview_item.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self._overview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._overview_item.setZValue(-2)

        self._fallback_item = TileLayerItem(self._backend, self._cache, is_fallback_layer=True, parent=container)
        self._fallback_item.setZValue(-1)
        self._fallback_item.setVisible(False)

        self._current_item = TileLayerItem(self._backend, self._cache, parent=container)

        container.set_slide_size(slide_w, slide_h)

        self._loader = TileLoader(self._backend, parent=self)
        self._loader.tile_ready.connect(self._on_tile_ready)
        self._loader.start()

        # Initial level selection and tile request
        self._auto_select_level()

    def _teardown(self) -> None:
        if self._loader is not None:
            self._loader.tile_ready.disconnect(self._on_tile_ready)
            self._loader.stop()
            self._loader.deleteLater()
            self._loader = None

        self._tile_request_timer.stop()
        self._cache.clear()
        self._inflight.clear()
        self._last_scene_rect = None

        # Remove child items from container
        for item in (self._overview_item, self._fallback_item, self._current_item):
            if item is not None and item.scene() is not None:
                item.scene().removeItem(item)
        self._overview_item = None
        self._fallback_item = None
        self._current_item = None
        self._backend = None

    def _auto_select_level(self) -> None:
        """Auto-select the best level based on current zoom."""
        if self._backend is None or self._current_item is None:
            return
        if self._current_view_scale <= 0:
            return
        target_ds = 1.0 / self._current_view_scale
        new_level = self._level_selector.resolve_level(
            self._backend, target_ds, self._current_item.current_level)
        self._switch_level(new_level)

    def _switch_level(self, new_level: int | None) -> None:
        """Apply a new level to the current item and promote the old level to fallback."""
        if new_level is None or self._backend is None:
            return
        new_level = max(0, min(new_level, self._backend.level_count - 1))
        old_level = self._current_item.current_level
        if new_level == old_level:
            return

        self._loader.clear_queue()
        self._inflight.clear()

        if old_level is not None:
            self._fallback_item.set_current_level(old_level)
            self._fallback_item.setVisible(True)
        else:
            self._fallback_item.setVisible(False)

        self._current_item.set_current_level(new_level)
        self.level_changed.emit(new_level)

    def _schedule_tile_update(self) -> None:
        """Schedule tile request, throttled by TILE_UPDATE_INTERVAL_MS."""
        now_ms = time.monotonic() * 1000.0
        if now_ms - self._last_tile_request_ms >= self.TILE_UPDATE_INTERVAL_MS:
            self._request_visible_tiles()
        else:
            if not self._tile_request_timer.isActive():
                self._tile_request_timer.start()

    def _request_visible_tiles(self) -> None:
        """Request tiles for the current visible area with prefetch margin."""
        self._tile_request_timer.stop()
        level = self._current_item.current_level if self._current_item else None
        if level is None or self._backend is None or self._last_scene_rect is None:
            return

        self._last_tile_request_ms = time.monotonic() * 1000.0

        local_rect = self._current_item.mapRectFromScene(self._last_scene_rect)
        level_info = self._backend.level_info(level)
        tile_w, tile_h = level_info.tile_size
        cols, rows = self._backend.tile_grid_shape(level)

        col0_visible = max(0, int(math.floor(local_rect.left() / tile_w)))
        row0_visible = max(0, int(math.floor(local_rect.top() / tile_h)))
        col1_visible = min(cols, int(math.floor(local_rect.right() / tile_w)) + 1)
        row1_visible = min(rows, int(math.floor(local_rect.bottom() / tile_h)) + 1)

        # Expand by prefetch margin
        col0 = max(0, col0_visible - self.PREFETCH_MARGIN)
        row0 = max(0, row0_visible - self.PREFETCH_MARGIN)
        col1 = min(cols, col1_visible + self.PREFETCH_MARGIN)
        row1 = min(rows, row1_visible + self.PREFETCH_MARGIN)

        to_request: list[tuple[int, int, int]] = []
        for r in range(row0, row1):
            for c in range(col0, col1):
                key = (level, c, r)
                if self._cache.contains_key(key):
                    self._inflight.discard(key)
                    continue
                if key in self._inflight:
                    continue
                to_request.append(key)

        if not to_request:
            return

        scene_center = self._last_scene_rect.center()
        to_request = self._sort_tiles_by_priority(to_request, scene_center, tile_w, tile_h)

        for key in to_request:
            self._inflight.add(key)
        self._loader.request_tiles(to_request)

    def _sort_tiles_by_priority(
        self, keys: list[tuple[int, int, int]], scene_center: QPointF, tile_w: int, tile_h: int,
    ) -> list[tuple[int, int, int]]:
        """Sort tiles by distance to viewport center (closest first)."""
        if not keys or self._current_item is None:
            return keys
        local_center = self._current_item.mapFromScene(scene_center)
        cx = local_center.x()
        cy = local_center.y()

        def priority(key: tuple[int, int, int]) -> float:
            _, col, row = key
            x = (col + 0.5) * tile_w
            y = (row + 0.5) * tile_h
            dx = x - cx
            dy = y - cy
            return dx * dx + dy * dy

        return sorted(keys, key=priority)

    def _on_tile_ready(self, loaded_tile: LoadedTile) -> None:
        """Handle a tile that was loaded in the background."""
        key = (loaded_tile.level, loaded_tile.col, loaded_tile.row)
        self._inflight.discard(key)

        pixmap = QPixmap.fromImage(loaded_tile.qimage)
        render_tile = RenderTile(pixmap=pixmap)
        self._cache.put(loaded_tile.level, loaded_tile.col, loaded_tile.row, render_tile)

        x, y, w, h = self._backend.tile_bounds(loaded_tile.level, loaded_tile.col, loaded_tile.row)
        rect = QRect(x, y, w, h)

        if loaded_tile.level == self._current_item.current_level:
            self._current_item.update(rect)
        elif self._fallback_item.isVisible() and loaded_tile.level == self._fallback_item.current_level:
            self._fallback_item.update(rect)
