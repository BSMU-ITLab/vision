from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import slideio

from bsmu.vision.core.data.tiled_backend import LevelInfo, TiledBackend


logger = logging.getLogger(__name__)

_OVERVIEW_MAX_PIXEL_AREA = 2_000_000
_DOWNSAMPLE_REL_TOL = 0.02
_DOWNSAMPLE_ABS_TOL = 1e-6


class SlideIoBackend(TiledBackend):
    """Concrete :class:`TiledBackend` that reads WSI via SlideIO."""

    DEFAULT_TILE_SIZE: int = 256

    def __init__(
        self,
        slide_path: str | Path,
        driver: str = 'SVS',
        tile_size: int | None = None,
    ) -> None:
        self._slide_path = Path(slide_path)
        if not self._slide_path.exists():
            raise FileNotFoundError(f'Slide not found: {self._slide_path}')

        self._tile_size = tile_size or self.DEFAULT_TILE_SIZE
        self._slide = slideio.open_slide(str(self._slide_path), driver)

        if self._slide.num_scenes == 0:
            raise ValueError('Slide contains no scenes')

        self._scene = self._slide.get_scene(0)
        self._slide_size: tuple[int, int] = (self._scene.size[0], self._scene.size[1])
        self._n_channels: int = self._scene.num_channels
        self._level_count: int = self._scene.num_zoom_levels
        self._levels: list[LevelInfo] = []
        self._initialize_levels()
        self._log_metadata()

    @property
    def level_count(self) -> int:
        return self._level_count

    @property
    def slide_size(self) -> tuple[int, int]:
        return self._slide_size

    @property
    def n_channels(self) -> int:
        return self._n_channels

    def level_info(self, level: int) -> LevelInfo:
        if not (0 <= level < self._level_count):
            raise IndexError(f'Level {level} out of range [0, {self._level_count})')
        return self._levels[level]

    def _read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        """
        Actual reading logic via SlideIO.
        Assumes x, y, w, h are already validated and clamped to level boundaries.
        """
        try:
            image = self._scene.read_block_from_level(level, rect=(x, y, w, h))
        except Exception as e:
            logger.error(
                'read_block_from_level failed at L%d rect(%d,%d,%d,%d): %s',
                level, x, y, w, h, e,
            )
            return self._zeros_for_shape(h, w)

        if image is None or image.size == 0:
            return self._zeros_for_shape(h, w)

        # Safety padding if SlideIO returns unexpected dimensions
        # (still useful as a fallback, though theoretically shouldn't happen with correct clamping)
        return self._pad_if_needed(image, w, h, context=f'L{level} rect({x},{y},{w},{h})')

    def read_overview(self) -> np.ndarray:
        """Read a low-resolution overview of the entire slide."""
        lowest = self._level_count - 1
        info = self.level_info(lowest)
        w, h = info.size
        pixel_area = w * h

        if pixel_area <= _OVERVIEW_MAX_PIXEL_AREA:
            return self._scene.read_block_from_level(lowest)

        # Further downscale if the lowest level is still too large
        scale = math.sqrt(pixel_area / _OVERVIEW_MAX_PIXEL_AREA)
        new_w = int(w // scale)
        new_h = int(h // scale)
        return self._scene.read_block(
            rect=(0, 0, self._slide_size[0], self._slide_size[1]),
            size=(new_w, new_h),
        )

    def close(self) -> None:
        self._slide = None
        self._scene = None

    @property
    def slide_path(self) -> Path:
        return self._slide_path

    @property
    def tile_size(self) -> int:
        return self._tile_size

    def _initialize_levels(self) -> None:
        """Parse and store metadata for all zoom levels."""
        for level in range(self._level_count):
            info = self._scene.get_zoom_level_info(level)
            w, h = info.size.width, info.size.height

            try:
                level_tile_w = info.tile_size.width
                level_tile_h = info.tile_size.height
            except AttributeError:
                logger.warning(
                    'Level %d: native tile size not found, falling back to default %d',
                    level, self._tile_size,
                )
                level_tile_w = self._tile_size
                level_tile_h = self._tile_size

            downsample_x = self._slide_size[0] / float(w)
            downsample_y = self._slide_size[1] / float(h)

            if not math.isclose(
                downsample_x, downsample_y,
                rel_tol=_DOWNSAMPLE_REL_TOL,
                abs_tol=_DOWNSAMPLE_ABS_TOL,
            ):
                logger.warning(
                    'Level %d: non-uniform downsample: ds_x=%.6f, ds_y=%.6f',
                    level, downsample_x, downsample_y,
                )

            downsample, _ = self._resolve_level_downsample(
                level_index=level,
                info_scale=info.scale,
                downsample_x=downsample_x,
                downsample_y=downsample_y,
            )

            if level > 0:
                prev_ds = self._levels[-1].downsample
                if downsample <= prev_ds * 1.001:
                    logger.warning(
                        'Level %d: downsample %.6f is not larger than previous %.6f',
                        level, downsample, prev_ds,
                    )

            self._levels.append(LevelInfo(
                level=level,
                width=w,
                height=h,
                magnification=info.magnification,
                downsample=downsample,
                downsample_x=downsample_x,
                downsample_y=downsample_y,
                tile_width=level_tile_w,
                tile_height=level_tile_h,
                tile_count=info.tile_count,
            ))

    def _resolve_level_downsample(
        self,
        level_index: int,
        info_scale: object,
        downsample_x: float,
        downsample_y: float,
    ) -> tuple[float, float | None]:
        """
        Resolve the downsample factor for a level.

        Returns ``(computed_downsample, info_downsample_or_None)``.
        The computed downsample (geometric mean of x/y) is always preferred
        for rendering because it is derived from actual pixel dimensions.
        """
        computed_ds = math.sqrt(downsample_x * downsample_y)

        try:
            info_scale_f = float(info_scale)
        except (TypeError, ValueError):
            info_scale_f = math.nan

        if not math.isfinite(info_scale_f) or info_scale_f <= 0.0:
            logger.warning(
                'Level %d: invalid info.scale=%r. Using computed ds=%.6f',
                level_index, info_scale, computed_ds,
            )
            return computed_ds, None

        info_ds = 1.0 / info_scale_f
        if not math.isfinite(info_ds) or info_ds <= 0.0:
            logger.warning(
                'Level %d: invalid info downsample=%r. Using computed ds=%.6f',
                level_index, info_ds, computed_ds,
            )
            return computed_ds, None

        if not math.isclose(
            info_ds, computed_ds,
            rel_tol=_DOWNSAMPLE_REL_TOL,
            abs_tol=_DOWNSAMPLE_ABS_TOL,
        ):
            logger.warning(
                'Level %d: downsample mismatch. '
                'info.scale=%.6f -> ds=%.6f, computed ds=%.6f. Using computed.',
                level_index, info_scale_f, info_ds, computed_ds,
            )

        return computed_ds, info_ds

    def _pad_if_needed(self, image: np.ndarray, expected_w: int, expected_h: int, *, context: str = '') -> np.ndarray:
        """Zero-pad *image* if SlideIO returned a block smaller than requested."""
        ih, iw = image.shape[:2]
        if ih == expected_h and iw == expected_w:
            return image

        logger.warning(
            'Size mismatch %s: expected %dx%d, got %dx%d. Padding.',
            context, expected_w, expected_h, iw, ih,
        )
        padded = self._zeros_for_shape(expected_h, expected_w)
        copy_h = min(ih, expected_h)
        copy_w = min(iw, expected_w)
        padded[:copy_h, :copy_w] = image[:copy_h, :copy_w]
        return padded

    def _log_metadata(self) -> None:
        """Log WSI summary at INFO and detailed breakdown at DEBUG."""

        l0_magnification = self._levels[0].magnification if self._levels else None
        magnification_str = f'{l0_magnification:.1f}x' if l0_magnification else 'N/A'

        logger.info(
            'WSI loaded: %s | %dx%d px | %s | %d ch | %d levels',
            self._slide_path.name,
            self._slide_size[0], self._slide_size[1],
            magnification_str,
            self._n_channels,
            self._level_count,
        )

        if not logger.isEnabledFor(logging.DEBUG):
            return

        logger.debug('--- WSI Metadata: %s ---', self._slide_path.name)
        logger.debug('  MPP: %s', self._scene.resolution)

        logger.debug('  Zoom Levels:')
        for line in self._format_level_table():
            logger.debug('    %s', line)

        logger.debug('------------------------')

    def _format_level_table(self) -> list[str]:
        """Format zoom level info as aligned table rows."""
        rows = [('L', 'size', 'mag', 'ds', 'ds xy', 'tile', 'tiles')]
        for li in self._levels:
            magnification = f'{li.magnification:.1f}x' if li.magnification else 'N/A'
            rows.append((
                f'L{li.level}',
                f'{li.width}x{li.height}',
                magnification,
                f'{li.downsample:.6f}',
                f'(x:{li.downsample_x:.6f}, y:{li.downsample_y:.6f})',
                f'{li.tile_width}x{li.tile_height}',
                f'{li.tile_count}',
            ))

        if not rows:
            return []

        # Column widths based on actual data
        col_count = len(rows[0])
        widths = [max(len(row[i]) for row in rows) for i in range(col_count)]

        lines = []
        for row in rows:
            cells = [cell.ljust(w) for cell, w in zip(row, widths)]
            lines.append(' | '.join(cells))

        return lines

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}('
            f'path={self._slide_path.name}, '
            f'size={self._slide_size}, '
            f'channels={self._n_channels}, '
            f'levels={self._level_count}, '
            f'tile_size={self._tile_size})'
        )
