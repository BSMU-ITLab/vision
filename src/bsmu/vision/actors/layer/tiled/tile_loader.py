from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QThread, QMutex, QMutexLocker, QWaitCondition, Signal
from PySide6.QtGui import QImage

from bsmu.vision.core.converters.image import numpy_array_to_qimage

if TYPE_CHECKING:
    from PySide6.QtCore import QObject

    from bsmu.vision.core.data.tiled_backend import TiledBackend


logger = logging.getLogger(__name__)


@dataclass
class LoadedTile:
    """Tile data loaded from disk."""
    level: int
    col: int
    row: int
    numpy_image: np.ndarray
    qimage: QImage  # Shallow copy; keep numpy_image reference alive


class TileLoader(QThread):
    """
    Background thread for loading tiles from slide.

    Emits tile_ready signal when a tile is successfully loaded.
    """

    tile_ready = Signal(LoadedTile)

    def __init__(self, backend: TiledBackend, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._backend = backend

        self._queue: deque[tuple[int, int, int]] = deque()
        self._queued: set[tuple[int, int, int]] = set()
        self._current: tuple[int, int, int] | None = None

        self._mutex = QMutex()
        self._work_condition = QWaitCondition()

        self._stop_requested = False

    def start(self, priority: QThread.Priority = QThread.Priority.InheritPriority) -> None:
        """Start the loader thread."""
        if self.isRunning():
            return

        with QMutexLocker(self._mutex):
            self._stop_requested = False
        super().start(priority)

    def stop(self, timeout_ms: int = 5000) -> None:
        """Stop the loader thread gracefully."""
        with QMutexLocker(self._mutex):
            self._stop_requested = True
            self._work_condition.wakeAll()

        if self.isRunning():
            self.wait(timeout_ms)

    def request_tiles(self, tiles: list[tuple[int, int, int]]) -> None:
        """
        Request tiles to be loaded.

        Tiles should be pre-sorted by priority (most important first).
        """
        with QMutexLocker(self._mutex):
            added = False
            # appendleft reverses order, so iterate in reverse
            for key in reversed(tiles):
                if key == self._current:
                    continue
                if key in self._queued:
                    continue
                self._queue.appendleft(key)
                self._queued.add(key)
                added = True
            if added:
                self._work_condition.wakeAll()

    def run(self) -> None:
        """Main loop: wait for work and load tiles."""
        while True:
            with QMutexLocker(self._mutex):
                # Wait for work or stop signal
                while not self._stop_requested and not self._queue:
                    self._work_condition.wait(self._mutex)

                if self._stop_requested:
                    break

                key = self._queue.popleft()
                self._queued.discard(key)
                self._current = key

            level, col, row = key

            try:
                tile = self._backend.read_tile(level, col, row)
                self.tile_ready.emit(
                    LoadedTile(
                        level=level,
                        col=col,
                        row=row,
                        numpy_image=tile,
                        qimage=numpy_array_to_qimage(tile, image_format=QImage.Format.Format_RGB888),
                    )
                )
            except Exception as e:
                logger.error('TileLoader critical error at L%d(%d,%d): %s', level, col, row, e)
                # Fallback: emit black tile to prevent rendering gaps
                _, _, w, h = self._backend.tile_bounds(level, col, row)
                black = np.zeros((h, w, 3), dtype=np.uint8)
                self.tile_ready.emit(
                    LoadedTile(
                        level=level,
                        col=col,
                        row=row,
                        numpy_image=black,
                        qimage=numpy_array_to_qimage(black, image_format=QImage.Format.Format_RGB888),
                    )
                )
            finally:
                with QMutexLocker(self._mutex):
                    if self._current == key:
                        self._current = None

    def clear_queue(self) -> None:
        """Clear all pending tile requests."""
        with QMutexLocker(self._mutex):
            self._queue.clear()
            self._queued.clear()
