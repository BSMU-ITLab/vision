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

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.constants import PlaneAxis
    from bsmu.vision.core.palette import Palette


MASK_TYPE = np.uint8
MASK_MAX = np.iinfo(MASK_TYPE).max


class SpatialAttrs:
    def __init__(self, origin, spacing, direction):
        # https://discourse.itk.org/t/images-in-physical-space-in-python/2124/17
        self.origin = origin
        self.spacing = spacing
        self.direction = direction

    @classmethod
    def default_for_ndim(cls, ndim: int):
        origin = np.zeros(ndim)
        spacing = np.ones(ndim)
        direction = np.identity(ndim)
        return cls(origin, spacing, direction)


class Raster(Data):
    n_dims = 2  # Number of dimensions excluding channel dimension (2 for FlatImage, 3 for VolumeImage)

    pixels_modified = Signal(BBox)
    shape_changed = Signal(object, object)  # old_shape: tuple[int] | None, new_shape: tuple[int] | None

    def __init__(
            self, array: np.ndarray = None, palette: Palette = None, path: Path = None, spatial: SpatialAttrs = None):
        super().__init__(path)

        assert palette is None or array.dtype == np.uint8, 'Indexed images (with palette) have to be of np.uint8 type'

        self.array = array
        self._palette = palette
        self.spatial = spatial or SpatialAttrs.default_for_ndim(self.n_dims)

        self._check_array_palette_matching()

    @classmethod
    def zeros_like(cls, other: Raster, create_mask: bool = False, palette: Palette = None) -> Raster:
        pixels = np.zeros(other.array.shape[:cls.n_dims], dtype=MASK_TYPE) if create_mask \
            else np.zeros_like(other.array)
        palette = palette or other.palette  # TODO: check, maybe we need copy of `other.palette`
        spatial = other.spatial  # TODO: check, maybe we need copy of `other.spatial`
        return cls(pixels, palette, spatial=spatial)

    @classmethod
    def zeros_mask_like(cls, other: Raster, palette: Palette = None) -> Raster:
        return cls.zeros_like(other, create_mask=True, palette=palette)

    @property
    def pixels(self) -> np.ndarray:
        return self.array

    @pixels.setter
    def pixels(self, value: np.ndarray):
        if self.array is not value:
            old_shape = self.shape_or_none
            self.array = value

            new_shape = self.shape_or_none
            if old_shape != new_shape:
                self.shape_changed.emit(old_shape, new_shape)

    @property
    def is_pixels_valid(self) -> bool:
        return self.pixels is not None

    @property
    def shape(self) -> tuple:
        return self.array.shape

    @property
    def shape_or_none(self) -> tuple | None:
        return None if self.array is None else self.shape

    def zeros(self, palette: Palette = None) -> Raster:
        return self.zeros_like(self, palette=palette)

    def zeros_mask(self, palette: Palette = None) -> Raster:
        return self.zeros_mask_like(self, palette=palette)

    def emit_pixels_modified(self, bbox: BBox = None):
        if bbox is None or not bbox.empty:
            self.pixels_modified.emit(bbox)

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

    def map_spatial_vector_to_pixel_vector_rounded(self, spatial_vector: np.ndarray):
        return self.map_spatial_vector_to_pixel_vector(spatial_vector).round().astype(np.int_)

    def bboxed_pixels(self, bbox: BBox) -> np.ndarray:
        return self.array[bbox.top:bbox.bottom, bbox.left:bbox.right]

    def modify_bboxed_pixels(self, bbox: BBox, new_pixels: np.ndarray):
        self.bboxed_pixels(bbox)[...] = new_pixels

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def is_indexed(self) -> bool:
        return self.palette is not None

    @palette.setter
    def palette(self, palette):
        if self._palette != palette:
            self._palette = palette
            self._check_array_palette_matching()

    @property
    def n_channels(self) -> int:
        return 1 if len(self.array.shape) == self.n_dims else self.array.shape[self.n_dims]

    @property
    def colored_array(self) -> np.ndarray:
        return self.apply_palette_to_indexed_array(self.array, self.palette.array)

    @property
    def colored_premultiplied_array(self) -> np.ndarray:
        return self.apply_palette_to_indexed_array(self.array, self.palette.premultiplied_array)

    def colored_premultiplied_array_in_bbox(self, bbox: BBox) -> np.ndarray:
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

    def _check_array_palette_matching(self):
        assert (not self.is_indexed) or self.n_channels == 1, \
            f'Indexed image (shape: {self.array.shape}) (with palette) has to contain only one channel'


class VolumeImage(Raster):
    n_dims = 3

    def __init__(self, array: np.ndarray = None, palette: Palette = None, path: Path = None, spatial: SpatialAttrs = None):
        warnings.warn('`VolumeImage` is deprecated; use `Raster.raster_3d` instead.', DeprecationWarning, stacklevel=2)
        super().__init__(array, palette, path, spatial)

    def slice_pixels(self, plane_axis: PlaneAxis, slice_number: int) -> np.ndarray:
        # Do not use np.take, because that will copy data
        plane_slice_indexing = [slice(None)] * 3
        plane_slice_indexing[plane_axis] = slice_number
        return self.array[tuple(plane_slice_indexing)]

    def center_slice_number(self, plane_axis: PlaneAxis):
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

    def __init__(self, value: int, description: str):
        super().__init__(value)
        self._description = description

    @property
    def description(self) -> str:
        return self._description
