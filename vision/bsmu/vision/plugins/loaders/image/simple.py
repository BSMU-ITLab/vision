from __future__ import annotations

import skimage.io

from bsmu.vision.plugins.loaders.image.base import ImageFileLoaderPlugin, ImageFileLoader
from bsmu.vision_core.image import FlatImage


class SimpleImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, SimpleImageFileLoader)


class SimpleImageFileLoader(ImageFileLoader):
    _FORMATS = ('png', 'jpg')

    def _load_file(self, path: Path, **kwargs):
        print('Load Simple Image')
        return FlatImage(skimage.io.imread(str(path), **kwargs), None, path)
