from __future__ import annotations

import numpy as np
import skimage.io

from bsmu.vision.plugins.loaders.image.base import ImageFileLoaderPlugin, ImageFileLoader
from bsmu.vision_core.image import FlatImage


class SimpleImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, SimpleImageFileLoader)


class SimpleImageFileLoader(ImageFileLoader):
    _FORMATS = ('png', 'jpg')

    def _load_file(self, path: Path, palette=None, as_gray=False, **kwargs):
        print('Load Simple Image')
        flat_image = FlatImage(skimage.io.imread(str(path), as_gray=as_gray or palette is not None, **kwargs),
                               None, path)
        if palette is not None:
            flat_image.array = np.rint(flat_image.array).astype(np.uint8)
        flat_image.palette = palette
        return flat_image
