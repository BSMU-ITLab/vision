from __future__ import annotations

import math
import warnings
from enum import Enum
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
from PySide6.QtCore import Signal

from bsmu.vision.core.bbox import BBox
from bsmu.vision.core.data import Data
from bsmu.vision.core.data.level_selector import BalancedLevelSelector

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtCore import QObject

    from bsmu.vision.core.constants import PlaneAxis
    from bsmu.vision.core.data.level_selector import LevelSelector
    from bsmu.vision.core.data.tiled_backend import TiledBackend
    from bsmu.vision.core.palette import Palette


MASK_TYPE = np.uint8
MASK_MAX = np.iinfo(MASK_TYPE).max


class SpatialAttrs:
    def __init__(self, origin, spacing, direction) -> None:
        # https://discourse.itk.org/t/images-in-physical-space-in-python/2124/17
        self.origin = origin
        self.spacing = spacing
        self.direction = direction

    @classmethod
    def default_for_ndim(cls, ndim: int) -> SpatialAttrs:
        origin = np.zeros(ndim)
        spacing = np.ones(ndim)
        direction = np.identity(ndim)
        return cls(origin, spacing, direction)


class Raster(Data):
    n_dims = 2  # Number of dimensions excluding channel dimension (2 for FlatImage, 3 for VolumeImage)

    pixels_modified = Signal(BBox)
    shape_changed = Signal(object, object)  # old_shape: tuple[int] | None, new_shape: tuple[int] | None

    def __init__(
            self,
            array: np.ndarray = None,
            palette: Palette = None,
            path: Path = None,
            spatial: SpatialAttrs = None,
            backend: TiledBackend = None,
            level_selector: LevelSelector = None,
            parent: QObject | None = None,
    ) -> None:
        super().__init__(path, parent)

        assert (
            palette is None or array is None or array.dtype == np.uint8
        ), 'Indexed images (with palette) have to be of np.uint8 type'

        self.array = array
        self._palette = palette
        self.spatial = spatial or SpatialAttrs.default_for_ndim(self.n_dims)
        self._backend = backend
        if backend is not None:
            self._level_selector = level_selector or BalancedLevelSelector()
        else:
            self._level_selector = None

        self._check_array_palette_matching()

    @property
    def is_tiled(self) -> bool:
        """True if this raster reads data on-demand from a backend."""
        return self._backend is not None

    @property
    def backend(self) -> TiledBackend | None:
        return self._backend

    @property
    def pixels(self) -> np.ndarray | None:
        if self.array is None and self.is_tiled:
            raise RuntimeError(
                'This is a tiled raster (WSI). '
                'Pixels are not loaded into memory. Use read_region() instead.'
            )
        return self.array

    @pixels.setter
    def pixels(self, value: np.ndarray | None) -> None:
        if self.is_tiled:
            raise RuntimeError(
                'Cannot set pixels on a tiled raster. '
                'WSI data is read-only and managed by the backend.'
            )
        if self.array is not value:
            old_shape = self.shape_or_none
            self.array = value

            new_shape = self.shape_or_none
            if old_shape != new_shape:
                self.shape_changed.emit(old_shape, new_shape)

    @property
    def is_pixels_valid(self) -> bool:
        """True if pixel data is available (in memory or via backend)."""
        return self.is_tiled or self.array is not None

    @property
    def shape(self) -> tuple:
        if self.array is not None:
            return self.array.shape
        if self.is_tiled:
            w, h = self._backend.slide_size
            n_ch = self._backend.n_channels
            if n_ch == 1:
                return h, w
            return h, w, n_ch
        raise RuntimeError('No data source: neither array nor backend is set')

    @property
    def shape_or_none(self) -> tuple | None:
        if self.array is None and not self.is_tiled:
            return None
        return self.shape

    @property
    def n_channels(self) -> int:
        if self.array is not None:
            return 1 if len(self.array.shape) == self.n_dims else self.array.shape[self.n_dims]
        if self.is_tiled:
            return self._backend.n_channels
        raise RuntimeError('No data source')

    def read_region(self, bbox: BBox, target_downsample: float = 1.0) -> np.ndarray:
        """
        Read a region in level-0 pixel coordinates.

        For in-memory rasters: extracts from ``self.array`` (target_downsample ignored).
        For tiled rasters: reads from backend at the optimal level.

        Args:
            bbox: Bounding box in level-0 pixel coordinates.
            target_downsample: Desired resolution scale (tiled only).
                               1.0 = full resolution, 8.0 = 8x smaller.
        """
        if not self.is_tiled:
            # In-memory raster: simple array slice (numpy clamps automatically)
            return bbox.pixels(self.array)

        # Tiled raster: choose level via strategy, convert coords, read
        level = self._level_selector.best_level(self._backend, target_downsample)
        level_ds = self._backend.level_downsample(level)

        x = int(bbox.left / level_ds)
        y = int(bbox.top / level_ds)
        w = int(math.ceil(bbox.width / level_ds))
        h = int(math.ceil(bbox.height / level_ds))

        return self._backend.read_region(level, x, y, w, h)

    def bboxed_pixels(self, bbox: BBox) -> np.ndarray:
        if self.is_tiled:
            raise RuntimeError(
                'bboxed_pixels() is not supported for tiled rasters. Use read_region() instead.'
            )
        return bbox.pixels(self.array)

    def modify_bboxed_pixels(self, bbox: BBox, new_pixels: np.ndarray) -> None:
        if self.is_tiled:
            raise RuntimeError('Tiled raster is read-only. Cannot modify pixels.')
        self.bboxed_pixels(bbox)[...] = new_pixels

    @classmethod
    def zeros_like(
            cls,
            other: Raster,
            create_mask: bool = False,
            palette: Palette = None,
            mask_downsample: float = 1.0,
    ) -> Raster:
        # Determine the spatial shape of the source (excluding the channel dimension)
        if other.is_tiled:
            spatial_shape = tuple(reversed(other._backend.slide_size))
        else:
            spatial_shape = other.array.shape[:cls.n_dims]

        if create_mask:
            mask_shape = tuple(max(1, round(s / mask_downsample)) for s in spatial_shape)
            pixels = np.zeros(mask_shape, dtype=MASK_TYPE)

            # Derive spacing from actual dimensions so the physical extent matches the source
            # (rounding may make the effective downsample differ from the requested one)
            spacing_ratios = np.array(spatial_shape, dtype=np.float64) / np.array(mask_shape, dtype=np.float64)
            result_spacing = other.spatial.spacing * spacing_ratios
        else:
            if other.is_tiled:
                raise RuntimeError(
                    'zeros_like with create_mask=False is not supported for tiled rasters.'
                )
            pixels = np.zeros_like(other.array)
            result_spacing = other.spatial.spacing.copy()

        spatial = SpatialAttrs(
            origin=other.spatial.origin.copy(),
            spacing=result_spacing,
            direction=other.spatial.direction.copy(),
        )

        palette = palette or other.palette
        return cls(pixels, palette, spatial=spatial)

    @classmethod
    def zeros_mask_like(cls, other: Raster, palette: Palette = None, mask_downsample: float = 1.0) -> Raster:
        return cls.zeros_like(other, create_mask=True, palette=palette, mask_downsample=mask_downsample)

    def with_new_pixels(self, new_pixels: np.ndarray) -> Raster:
        """Return a new instance with the same metadata but different pixel data."""
        if self.is_tiled:
            raise RuntimeError('Cannot create new pixels for a tiled raster.')
        return type(self)(
            array=new_pixels,
            palette=self.palette,
            path=self.path,
            spatial=self.spatial,
            parent=self.parent(),
        )

    def map_spatial_to_pixel_coords(self, spatial_pos: np.ndarray) -> np.ndarray:
        """Convert spatial (e.g., mm) coordinates to continuous pixel coordinates."""
        return (spatial_pos - self.spatial.origin) / self.spatial.spacing

    def map_spatial_to_pixel_indices(self, spatial_pos: np.ndarray) -> np.ndarray:
        """Convert spatial coordinates to nearest pixel indices (int)."""
        return self.map_spatial_to_pixel_coords(spatial_pos).round().astype(np.int_)

    def map_pixel_coords_to_spatial(self, pixel_coords: np.ndarray) -> np.ndarray:
        """Convert continuous pixel coordinates to spatial coordinates."""
        return pixel_coords * self.spatial.spacing + self.spatial.origin

    def map_spatial_vector_to_pixel_vector(self, spatial_vector: np.ndarray) -> np.ndarray:
        return spatial_vector / self.spatial.spacing

    def map_pixel_vector_to_spatial_vector(self, pixel_vector: np.ndarray) -> np.ndarray:
        return pixel_vector * self.spatial.spacing

    def map_spatial_vector_to_pixel_vector_rounded(self, spatial_vector: np.ndarray) -> np.ndarray:
        return self.map_spatial_vector_to_pixel_vector(spatial_vector).round().astype(np.int_)

    @property
    def palette(self) -> Palette:
        return self._palette

    @palette.setter
    def palette(self, palette) -> None:
        if self._palette != palette:
            self._palette = palette
            self._check_array_palette_matching()

    @property
    def is_indexed(self) -> bool:
        return self.palette is not None

    @property
    def colored_array(self) -> np.ndarray:
        if self.is_tiled:
            raise RuntimeError('colored_array is not supported for tiled rasters.')
        return self.apply_palette_to_indexed_array(self.array, self.palette.array)

    @property
    def colored_premultiplied_array(self) -> np.ndarray:
        if self.is_tiled:
            raise RuntimeError('colored_premultiplied_array is not supported for tiled rasters.')
        return self.apply_palette_to_indexed_array(self.array, self.palette.premultiplied_array)

    def colored_premultiplied_array_in_bbox(self, bbox: BBox) -> np.ndarray:
        if self.is_tiled:
            raise RuntimeError('colored_premultiplied_array_in_bbox is not supported for tiled rasters.')
        return self.apply_palette_to_indexed_array(self.bboxed_pixels(bbox), self.palette.premultiplied_array)

    @staticmethod
    def apply_palette_to_indexed_array(indexed_array: np.ndarray, palette_array: np.ndarray) -> np.ndarray:
        # We can use "fancy indexing" of numpy to get colored array, but cv.LUT works faster
        # return self.palette_array[indexed_array]

        # cv.LUT needs next image shape: (w, h, c)
        # And needs LUT shape: (1, 256, c), where c - number of channels (we use 4 channels)
        # So we need to convert our image with (w, h) shape to (w, h, 4) (use 4 identical channels)
        # We do not use np.stack, cause methods of OpenCV are faster
        rgba_image = cv.cvtColor(indexed_array, cv.COLOR_GRAY2RGBA)
        # COLOR_GRAY2RGBA will assign 255 for alpha-channel, but we need the same alpha-value, like other channels
        # Use cv.mixChannels as a faster alternative for: rgba_image[..., 3] = rgba_image[..., 0]
        cv.mixChannels([rgba_image], [rgba_image], [0, 3])

        # Change LUT shape from (256, 4) to (1, 256, 4)
        lut_with_added_axis = np.expand_dims(palette_array, axis=0)
        return cv.LUT(rgba_image, lut_with_added_axis)

    def emit_pixels_modified(self, bbox: BBox = None) -> None:
        if bbox is None or not bbox.empty:
            self.pixels_modified.emit(bbox)

    def zeros(self, palette: Palette = None) -> Raster:
        return self.zeros_like(self, palette=palette)

    def zeros_mask(self, palette: Palette = None, mask_downsample: float = 1.0) -> Raster:
        return self.zeros_mask_like(self, palette=palette, mask_downsample=mask_downsample)

    def close(self) -> None:
        """Release backend resources. After this, the Raster is no longer usable for reading."""
        if self._backend is not None:
            self._backend.close()

    def _check_array_palette_matching(self) -> None:
        if self.array is None:
            return  # Tiled raster or empty raster - skip check
        assert (
            (not self.is_indexed) or self.n_channels == 1
        ), f'Indexed image (shape: {self.array.shape}) (with palette) has to contain only one channel'

    def __repr__(self) -> str:
        if self.is_tiled:
            return f'{self.__class__.__name__}(tiled, backend={self._backend!r})'
        return f'{self.__class__.__name__}(shape={self.shape_or_none})'


class VolumeImage(Raster):
    n_dims = 3

    def __init__(
            self,
            array: np.ndarray = None,
            palette: Palette = None,
            path: Path = None,
            spatial: SpatialAttrs = None,
    ) -> None:
        warnings.warn('`VolumeImage` is deprecated; use `Raster.raster_3d` instead.', DeprecationWarning, stacklevel=2)
        super().__init__(array, palette, path, spatial)

    def slice_pixels(self, plane_axis: PlaneAxis, slice_number: int) -> np.ndarray:
        # Do not use np.take, because that will copy data
        plane_slice_indexing = [slice(None)] * 3
        plane_slice_indexing[plane_axis] = slice_number
        return self.array[tuple(plane_slice_indexing)]

    def center_slice_number(self, plane_axis: PlaneAxis) -> int:
        return math.floor(self.array.shape[plane_axis] / 2)


class MaskDrawMode(Enum):
    REDRAW_ALL = 1, "Completely replace the existing mask with the new mask."
    OVERLAY_FOREGROUND = 2, (
        "Apply the new mask only where its own pixels are equal to foreground value, "
        "preserving the existing mask elsewhere."
    )
    FILL_BACKGROUND = 3, (
        "Apply the new mask only on the background pixels of the existing mask, "
        "leaving other pixels unchanged."
    )

    def __init__(self, value: int, description: str) -> None:
        super().__init__(value)
        self._description = description

    @property
    def description(self) -> str:
        return self._description
