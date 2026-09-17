from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QPainter, QTransform
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from bsmu.vision.actors.layer.tiled.tile_cache import TileCache
    from bsmu.vision.core.data.tiled_backend import TiledBackend


logger = logging.getLogger(__name__)

_MAX_EXPECTED_TILE_COUNT = 200
_TILE_COUNT_WARNING_INTERVAL_S = 5.0


class TileLayerItem(QGraphicsItem):
    """Graphics item that renders tiles from a cache for a specific zoom level."""

    def __init__(
        self,
        backend: TiledBackend,
        cache: TileCache,
        is_fallback_layer: bool = False,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)

        self._backend = backend
        self._cache = cache
        self._is_fallback_layer = is_fallback_layer

        self._current_level: int | None = None
        self._bounding_rect = QRectF()  # In level-local coordinates (before transform)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        self._last_tile_count_warning_s = 0.0

    @property
    def current_level(self) -> int | None:
        return self._current_level

    def set_current_level(self, level: int | None) -> None:
        """Switch to a new zoom level and update transformation."""
        if self._current_level == level:
            return

        self.prepareGeometryChange()
        self._current_level = level

        if level is None:
            self._bounding_rect = QRectF()
            self.setTransform(QTransform())
        else:
            info = self._backend.level_info(level)
            lw, lh = info.size
            ds_x, ds_y = info.downsample_xy

            # Local level coordinates
            self._bounding_rect = QRectF(0, 0, lw, lh)

            # Transform level-local coords to full-res scene coords
            self.setTransform(QTransform.fromScale(ds_x, ds_y))

        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounding_rect

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Render visible tiles for the current level."""
        if self._current_level is None:
            return

        exposed = option.exposedRect
        if exposed.isEmpty():
            return

        level = self._current_level
        level_info = self._backend.level_info(level)
        level_tile_w, level_tile_h = level_info.tile_size

        # exposedRect is in level-local coordinates
        col0 = max(0, int(math.floor(exposed.left() / level_tile_w)))
        row0 = max(0, int(math.floor(exposed.top() / level_tile_h)))

        cols, rows = self._backend.tile_grid_shape(level)
        col1 = min(cols, int(math.floor(exposed.right() / level_tile_w)) + 1)
        row1 = min(rows, int(math.floor(exposed.bottom() / level_tile_h)) + 1)

        # SmoothPixmapTransform keeps objects (e.g. cells) smooth when zoomed in
        # and prevents tile jitter during zoom/pan with drawPixmap
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        tile_count = (row1 - row0) * (col1 - col0)
        if tile_count > _MAX_EXPECTED_TILE_COUNT:
            now_s = time.monotonic()
            if now_s - self._last_tile_count_warning_s >= _TILE_COUNT_WARNING_INTERVAL_S:
                logger.warning(
                    'Painting %d tiles at L%d (expected at most %d) - '
                    'likely a too-detailed level was selected.',
                    tile_count, level, _MAX_EXPECTED_TILE_COUNT,
                )
                self._last_tile_count_warning_s = now_s

        for row in range(row0, row1):
            for col in range(col0, col1):
                x, y, w, h = self._backend.tile_bounds(level, col, row)
                if w <= 0 or h <= 0:
                    continue

                if self._is_fallback_layer:
                    tile = self._cache.peek(level, col, row)
                else:
                    tile = self._cache.get(level, col, row)

                if tile is not None and tile.pixmap is not None:
                    tile_rect = QRect(x, y, w, h)
                    painter.drawPixmap(tile_rect, tile.pixmap)
