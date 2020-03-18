from __future__ import annotations

import numpy as np
from PySide2.QtCore import Signal

from bsmu.vision_core.data import Data


MASK_TYPE = np.uint8


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


class Image(Data):
    pixels_modified = Signal()

    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None, spatial: SpatialAttrs = None):
        super().__init__(path)

        self.array = array
        self._palette = palette
        self.spatial = spatial

        self._check_array_palette_matching()

    @classmethod
    def zeros_like(cls, other_image: Image, create_mask: bool = False, palette: Palette = None):
        pixels = np.zeros(other_image.array.shape[:2], dtype=MASK_TYPE) if create_mask \
            else np.zeros_like(other_image.array)
        palette = palette or other_image.palette  # TODO: check, maybe we need copy of |other_image.palette|
        spatial = other_image.spatial  # TODO: check, maybe we need copy of |other_image.spatial|
        return cls(pixels, palette, spatial=spatial)

    @classmethod
    def zeros_mask_like(cls, other_image: Image, palette: Palette = None):
        return cls.zeros_like(other_image, create_mask=True, palette=palette)

    def emit_pixels_modified(self):
        self.pixels_modified.emit()

    def pos_to_pixel_indexes(self, pos: np.ndarray) -> np.ndarray:
        return (pos - self.spatial.origin) / self.spatial.spacing

    def pos_to_pixel_indexes_rounded(self, pos: np.ndarray) -> np.ndarray:
        return self.pos_to_pixel_indexes(pos).round().astype(np.int_)

    def pixel_indexes_to_pos(self, pixel_indexes: np.ndarray) -> np.ndarray:
        return pixel_indexes * self.spatial.spacing + self.spatial.origin

    def spatial_size_to_indexed(self, spatial_size: np.ndarray):
        return spatial_size / self.spatial.spacing

    def spatial_size_to_indexed_rounded(self, spatial_size: np.ndarray):
        return self.spatial_size_to_indexed(spatial_size).round().astype(np.int_)

    @property
    def palette(self) -> Palette:
        return self._palette

    @palette.setter
    def palette(self, palette):
        if self._palette != palette:
            self._palette = palette
            self._check_array_palette_matching()

    @property
    def colored_array(self) -> ndarray:
        return self.palette.array[self.array]

    @property
    def colored_premultiplied_array(self) -> ndarray:
        return self.palette.premultiplied_array[self.array]

    def _check_array_palette_matching(self):
        pass


class FlatImage(Image):
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None,
                 spatial: SpatialAttrs = SpatialAttrs.default_for_ndim(2)):
        super().__init__(array, palette, path, spatial)

    def _check_array_palette_matching(self):
        assert (self.palette is None) or (len(self.array.shape) == 2), \
            f'Flat indexed image (shape: {self.array.shape}) (with palette) has to contain no channels'


class VolumeImage(Image):
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None,
                 spatial: SpatialAttrs = SpatialAttrs.default_for_ndim(3)):
        super().__init__(array, palette, path, spatial)

    def _check_array_palette_matching(self):
        assert (self.palette is None) or (len(self.array.shape) == 3), \
            f'Volume indexed image (shape: {self.array.shape}) (with palette) has to contain no channels.'
