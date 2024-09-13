from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np

from bsmu.vision.core.image import FlatImage
from bsmu.vision.plugins.loaders.image import ImageFileLoaderPlugin, ImageFileLoader

if TYPE_CHECKING:
    from pathlib import Path


class SimpleImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self):
        super().__init__(SimpleImageFileLoader)


class SimpleImageFileLoader(ImageFileLoader):
    _FORMATS = ('png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif')

    def _load_file(self, path: Path, palette=None, as_gray=False, **kwargs):
        logging.info('Load Simple Image')

        # Do not use skimage, because:
        # a) OpenCV works a little faster
        # b) skimage can use different plugins (we do not know exactly which one will be used)
        # c) if PIL plugin is used, then we can get DecompressionBombWarning (or even exception) for big images
        # pixels = skimage.io.imread(str(path), as_gray=as_gray or palette is not None, **kwargs)

        # Do not use cv.imread, because it works only with ASCII characters in file path
        # pixels = cv.imread(str(path), cv.IMREAD_UNCHANGED)

        assert not as_gray, 'as_gray flag is unimplemented'
        # Use numpy.fromfile because it supports Unicode characters in file path
        pixels = cv.imdecode(np.fromfile(path, dtype=np.uint8), cv.IMREAD_UNCHANGED)
        channel_count = pixels.shape[-1] if pixels.ndim == 3 else 1
        match channel_count:
            case 3:
                convert_flag = cv.COLOR_BGR2RGB
            case 4:
                convert_flag = cv.COLOR_BGRA2RGBA
            case _:
                convert_flag = None
        if convert_flag is not None:
            pixels = cv.cvtColor(pixels, convert_flag)

        if palette is not None and pixels.dtype != np.uint8:
            logging.warning(f'Strange image with palette and {pixels.dtype} type')
            pixels = np.rint(pixels).astype(np.uint8)

        flat_image = FlatImage(pixels, palette, path)
        return flat_image
