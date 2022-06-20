from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import skimage.io

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.plugins.loaders.image.base import ImageFileLoaderPlugin, ImageFileLoader

if TYPE_CHECKING:
    from pathlib import Path


class SimpleImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self):
        super().__init__(SimpleImageFileLoader)


class SimpleImageFileLoader(ImageFileLoader):
    _FORMATS = ('png', 'jpg', 'jpeg', 'bmp', 'tiff', 'svs')

    def _load_file(self, path: Path, palette=None, as_gray=False, **kwargs):
        print('Load Simple Image')
        pixels = skimage.io.imread(str(path), as_gray=as_gray or palette is not None, **kwargs)
        flat_image = FlatImage(pixels, palette, path)
        if palette is not None:
            flat_image.array = np.rint(flat_image.array).astype(np.uint8)
        return flat_image
