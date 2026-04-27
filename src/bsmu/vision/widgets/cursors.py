from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon, QCursor

if TYPE_CHECKING:
    from pathlib import Path


DEFAULT_CURSOR_SIZE = 32
DEFAULT_HOTSPOT_X = 0.5
DEFAULT_HOTSPOT_Y = 0.5


@dataclass(frozen=True)
class CursorConfig:
    icon_file_name: str = ''
    # Normalized hotspot coordinates (range: [0.0; 1.0]), relative to SVG width and height
    hot_x: float = DEFAULT_HOTSPOT_X
    hot_y: float = DEFAULT_HOTSPOT_Y
    size: int = DEFAULT_CURSOR_SIZE


@lru_cache(maxsize=64)
def _create_cursor_cached(icon_file_name: str, hot_x: float, hot_y: float, size: int) -> QCursor:
    """Internal cached implementation. Works only with primitives for reliable hashing."""
    icon = QIcon(icon_file_name)
    if icon.isNull():
        raise FileNotFoundError(f'Cursor icon not found: {icon_file_name}')

    pixmap = icon.pixmap(size)
    # Note: For non-square icons, use `pixmap.width()` and `pixmap.height()` instead of `size`
    # to ensure accurate hotspot positioning.
    return QCursor(pixmap, hotX=int(hot_x * size), hotY=int(hot_y * size))


def create_cursor(
        icon_path: Path | str,
        *,
        hot_x: float = DEFAULT_HOTSPOT_X,
        hot_y: float = DEFAULT_HOTSPOT_Y,
        size: int = DEFAULT_CURSOR_SIZE
) -> QCursor:
    return _create_cursor_cached(str(icon_path), hot_x, hot_y, size)


def create_cursor_from_config(config: CursorConfig) -> QCursor:
    return _create_cursor_cached(config.icon_file_name, config.hot_x, config.hot_y, config.size)
