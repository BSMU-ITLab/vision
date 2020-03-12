from __future__ import annotations

from bsmu.vision_core.data import Data
from PySide2.QtCore import Signal
import numpy as np


class Image(Data):
    pixels_modified = Signal()

    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None, spatial: SpatialAttrs = None):
        super().__init__(path)

        self.array = array
        self._palette = palette
        self.spatial = spatial

        self._check_array_palette_matching()

    @classmethod
    def zeros_like(cls, other_image: Image, palette: Palette = None):
        pixels = np.zeros_like(other_image.array)
        palette = palette or other_image.palette  # TODO: check, maybe we need copy of |other_image.palette|
        spatial = other_image.spatial  # TODO: check, maybe we need copy of |other_image.spatial|
        return cls(pixels, palette, spatial=spatial)

    def emit_pixels_modified(self):
        self.pixels_modified.emit()

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
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None, spatial: SpatialAttrs = None):
        super().__init__(array, palette, path, spatial)

    def _check_array_palette_matching(self):
        assert (self.palette is None) or (len(self.array.shape) == 2), \
            f'Flat indexed image (shape: {self.array.shape}) (with palette) has to contain no channels'


class VolumeImage(Image):
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None, spatial: SpatialAttrs = None):
        super().__init__(array, palette, path, spatial)

    def _check_array_palette_matching(self):
        assert (self.palette is None) or (len(self.array.shape) == 3), \
            f'Volume indexed image (shape: {self.array.shape}) (with palette) has to contain no channels.'


class SpatialAttrs:
    def __init__(self, origin, spacing, direction):
        # https://discourse.itk.org/t/images-in-physical-space-in-python/2124/17
        self.origin = origin
        self.spacing = spacing
        self.direction = direction
