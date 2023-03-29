from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import skimage.io
import slideio

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.plugins.loaders.image.base import ImageFileLoaderPlugin, ImageFileLoader
from pathlib import Path
from bsmu.vision.core.data import Data
from bsmu.vision.core.path import is_ascii_path

# if TYPE_CHECKING:
#     from pathlib import Path


class WholeSlideImageFileLoaderPlugin(ImageFileLoaderPlugin):
    def __init__(self):
        super().__init__(WholeSlideImageFileLoader)


class WholeSlideImageFileLoader(ImageFileLoader):
    _FORMATS = ('svs', 'afi', 'scn', 'czi', 'zvi', 'ndpi', 'tiff', 'tif')

    def __init__(self):
        super().__init__()

        self._slideio_driver_by_file_extension = {
            '.svs': 'SVS',
            '.afi': 'AFI',
            '.scn': 'SCN',
            '.czi': 'CZI',
            '.zvi': 'ZVI',
            '.ndpi': 'NDPI',
            '.tiff': 'GDAL',
            '.tif': 'GDAL',
        }

    def _load_file(self, path: Path, palette=None, as_gray=False, **kwargs):
        logging.info('Load Whole-Slide Image')

        # multi_image_level = 1
        # pixels = skimage.io.MultiImage(
        #     str(path), as_gray=as_gray or palette is not None, key=multi_image_level, **kwargs)[0]
        # flat_image = FlatImage(pixels, palette, path)
        # if palette is not None:
        #     flat_image.pixels = np.rint(flat_image.pixels).astype(np.uint8)
        # return flat_image




        # from ctypes import CDLL
        #
        # print('file', __file__)
        # p = Path(__file__).parents[7] / r'biocell\libss\openslide-win64-20171122\bin\libopenslide-0.dll'
        # print('p', p)
        # # my_cdll = CDLL(r'D:\Projects\vision\biocell\libss\openslide-win64-20171122\bin\libopenslide-0.dll')
        # CDLL(str(p))
        #
        # import openslide
        #
        # slide = openslide.OpenSlide(path)
        #
        # data = Data(path)
        # data.slide = slide
        # return data


        # data = Data(path)
        # return data

        if not is_ascii_path(path):
            logging.error(
                'Current version of SlideIO library cannot open file if non-ASCII characters present in path name')
            return None

        file_extension = path.suffix
        slideio_driver = self._slideio_driver_by_file_extension[file_extension]
        slide = slideio.open_slide(str(path), slideio_driver)
        scene = slide.get_scene(0)
        full_resolution_width = scene.rect[2]
        # region = scene.read_block(size=(round(full_resolution_width / 7.53), 0))
        region = scene.read_block(size=(round(full_resolution_width / 8), 0))

        if palette is not None:
            region = region[..., 0]

        return FlatImage(region, palette=palette, path=path)
