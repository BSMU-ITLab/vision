from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtGui import QImage, QPixmap


@dataclass
class RenderTile:
    """Tile data prepared for rendering."""
    numpy_image: np.ndarray | None = None
    qimage: QImage | None = None  # Shallow ref; keep numpy_image alive
    pixmap: QPixmap | None = None  # If present, numpy/qimage can be dropped to save RAM

    def nbytes(self) -> int:
        """Calculate approximate memory footprint."""
        result = 0
        if self.pixmap is not None:
            result += self.pixmap.width() * self.pixmap.height() * (self.pixmap.depth() // 8)
        if self.numpy_image is not None:
            result += self.numpy_image.nbytes
        # QImage is a shallow reference, so we don't count it
        return result


class TileCache:
    """
    LRU cache for rendered tiles.

    NOTE: Currently used only from the GUI thread.
    If you call methods from different threads, add a lock.
    """

    def __init__(self, max_memory_mb: float = 512.0) -> None:
        self._max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self._current_memory_bytes = 0
        self._cache: OrderedDict[tuple[int, int, int], RenderTile] = OrderedDict()

    def get(self, level: int, col: int, row: int) -> RenderTile | None:
        """Retrieve tile and mark as recently used."""
        key = (level, col, row)
        tile = self._cache.get(key)
        if tile is not None:
            self._cache.move_to_end(key)
        return tile

    def peek(self, level: int, col: int, row: int) -> RenderTile | None:
        """Read without updating LRU order (for fallback layers)."""
        key = (level, col, row)
        return self._cache.get(key)

    def put(self, level: int, col: int, row: int, tile: RenderTile) -> None:
        """Store tile in cache, evicting LRU items if necessary."""
        key = (level, col, row)
        tile_bytes = tile.nbytes()

        # Remove old tile if key already exists
        old_tile = self._cache.pop(key, None)
        if old_tile is not None:
            self._current_memory_bytes -= old_tile.nbytes()

        # Evict LRU until we have room
        while self._cache and self._current_memory_bytes + tile_bytes > self._max_memory_bytes:
            _, evicted = self._cache.popitem(last=False)
            self._current_memory_bytes -= evicted.nbytes()

        self._cache[key] = tile
        self._current_memory_bytes += tile_bytes

    def contains(self, level: int, col: int, row: int) -> bool:
        """Check if tile exists in cache."""
        key = (level, col, row)
        return key in self._cache

    def contains_key(self, key: tuple[int, int, int]) -> bool:
        """Check if tile key exists in cache."""
        return key in self._cache

    def clear(self) -> None:
        """Remove all tiles and reset statistics."""
        self._cache.clear()
        self._current_memory_bytes = 0

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}('
            f'size={len(self._cache)}, '
            f'bytes={self._current_memory_bytes}/{self._max_memory_bytes})'
        )
