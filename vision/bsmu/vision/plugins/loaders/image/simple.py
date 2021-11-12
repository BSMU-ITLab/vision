from __future__ import annotations

import numpy as np
import skimage.io

from bsmu.vision.plugins.loaders.image.base import ImageFileLoaderPlugin, ImageFileLoader
from bsmu.vision.core.image.base import FlatImage


class SimpleImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self):
        super().__init__(SimpleImageFileLoader)


class SimpleImageFileLoader(ImageFileLoader):
    _FORMATS = ('png', 'jpg', 'bmp')

    def _load_file(self, path: Path, palette=None, as_gray=False, **kwargs):
        print('Load Simple Image')
        pixels = skimage.io.imread(str(path), as_gray=as_gray or palette is not None, **kwargs)
        flat_image = FlatImage(pixels, palette, path)
        if palette is not None:
            flat_image.array = np.rint(flat_image.array).astype(np.uint8)
        return flat_image
