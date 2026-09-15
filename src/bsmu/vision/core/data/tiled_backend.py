from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LevelInfo:
    """Metadata for a single zoom level of a pyramidal image."""
    level: int
    width: int
    height: int
    magnification: float
    downsample: float    # Geometric mean of downsample_x and downsample_y
    downsample_x: float  # Ratio of base width to this level's width
    downsample_y: float  # Ratio of base height to this level's height
    tile_width: int
    tile_height: int
    tile_count: int

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def tile_size(self) -> tuple[int, int]:
        return self.tile_width, self.tile_height

    @property
    def downsample_xy(self) -> tuple[float, float]:
        return self.downsample_x, self.downsample_y


class TiledBackend(ABC):
    """
    Abstract interface for reading pyramidal / tiled image data.

    Concrete implementations (SlideIO, OpenSlide, TiffFile, ...) handle
    the specific file format. The backend operates in level-local pixel
    coordinates.

    Thread-safety note
    ------------------
    ``read_region`` / ``read_tile`` may be called from background threads
    (e.g. a tile loader). Implementations must ensure that concurrent
    reads are safe.
    """

    @property
    @abstractmethod
    def level_count(self) -> int:
        """Total number of zoom levels in the pyramid."""

    @property
    @abstractmethod
    def slide_size(self) -> tuple[int, int]:
        """(width, height) of the base level (level 0) in pixels."""

    @property
    @abstractmethod
    def n_channels(self) -> int:
        """Number of channels per pixel (1 for grayscale, 3 for RGB, etc.)."""

    @abstractmethod
    def level_info(self, level: int) -> LevelInfo:
        """Return metadata for the given zoom level."""

    @abstractmethod
    def _read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        """
        Internal method to read a rectangular region.

        Implementations can safely assume that x, y, w, h are valid,
        non-negative, and strictly within the level boundaries.
        """

    @abstractmethod
    def read_overview(self) -> np.ndarray:
        """Read a low-resolution overview of the entire slide."""

    @abstractmethod
    def close(self) -> None:
        """Release file handles and other resources."""

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        """
        Read a rectangular region from level in level-local pixel coords.

        This is the safe public API. It clamps the rect to level boundaries
        and handles zero-size requests before delegating to `_read_region`.
        """
        info = self.level_info(level)

        # Clamp to level boundaries
        x = max(0, min(x, info.width))
        y = max(0, min(y, info.height))
        w = min(w, info.width - x)
        h = min(h, info.height - y)

        if w <= 0 or h <= 0:
            return self._zeros_for_shape(max(0, h), max(0, w))

        return self._read_region(level, x, y, w, h)

    def level_size(self, level: int) -> tuple[int, int]:
        return self.level_info(level).size

    def level_downsample(self, level: int) -> float:
        return self.level_info(level).downsample

    def level_downsample_xy(self, level: int) -> tuple[float, float]:
        return self.level_info(level).downsample_xy

    def tile_bounds(self, level: int, col: int, row: int) -> tuple[int, int, int, int]:
        """Return ``(x, y, w, h)`` for a tile, clamped to level boundaries."""
        info = self.level_info(level)
        x = col * info.tile_width
        y = row * info.tile_height
        w = min(info.tile_width, max(0, info.width - x))
        h = min(info.tile_height, max(0, info.height - y))
        return x, y, w, h

    def tile_grid_shape(self, level: int) -> tuple[int, int]:
        """Return ``(num_cols, num_rows)`` for the tile grid of *level*."""
        info = self.level_info(level)
        cols = math.ceil(info.width / info.tile_width)
        rows = math.ceil(info.height / info.tile_height)
        return cols, rows

    def read_tile(self, level: int, col: int, row: int) -> np.ndarray:
        """Read a single tile by grid coordinates."""
        x, y, w, h = self.tile_bounds(level, col, row)
        if w <= 0 or h <= 0:
            return self._zeros_for_shape(max(0, h), max(0, w))
        return self._read_region(level, x, y, w, h)

    def _zeros_for_shape(self, h: int, w: int) -> np.ndarray:
        """Create a zero array matching the channel count."""
        if self.n_channels > 1:
            return np.zeros((h, w, self.n_channels), dtype=np.uint8)
        return np.zeros((h, w), dtype=np.uint8)

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}('
            f'size={self.slide_size}, '
            f'channels={self.n_channels}, '
            f'levels={self.level_count})'
        )
