from __future__ import annotations

import skimage.io

from bsmu.vision_image_file_loader import ImageFileLoaderPlugin
from bsmu.vision_image_file_loader import ImageFileLoader
from bsmu.vision_core.image import FlatImage


class SimpleImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, SimpleImageFileLoader)


class SimpleImageFileLoader(ImageFileLoader):
    _FORMATS = ('png', 'jpg')

    def _load_file(self, path: Path):
        print('Load Simple Image')
        return FlatImage(skimage.io.imread(str(path)), path)
