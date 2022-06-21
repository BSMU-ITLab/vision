from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import skimage.io

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.plugins.loaders.image.base import ImageFileLoaderPlugin, ImageFileLoader

if TYPE_CHECKING:
    from pathlib import Path


class WholeSlideImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self):
        super().__init__(WholeSlideImageFileLoader)


class WholeSlideImageFileLoader(ImageFileLoader):
    _FORMATS = ('tiff', 'svs')

    def _load_file(self, path: Path, palette=None, as_gray=False, **kwargs):
        print('Load Whole-Slide Image')

        multi_image_level = 1
        pixels = skimage.io.MultiImage(
            str(path), as_gray=as_gray or palette is not None, key=multi_image_level, **kwargs)[0]
        flat_image = FlatImage(pixels, palette, path)
        if palette is not None:
            flat_image.pixels = np.rint(flat_image.pixels).astype(np.uint8)
        return flat_image
