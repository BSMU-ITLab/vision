from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.image import FlatImage
from bsmu.vision.plugins.readers.image import ImageFileReader, ImageFileReaderPlugin
from bsmu.vision.plugins.readers.image.wsi.slideio_backend import SlideIoBackend

if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


class WholeSlideImageFileReaderPlugin(ImageFileReaderPlugin):
    def __init__(self):
        super().__init__(WholeSlideImageFileReader)


class WholeSlideImageFileReader(ImageFileReader):
    _FORMATS = ('svs', 'afi', 'scn', 'czi', 'zvi', 'ndpi', 'tiff', 'tif')

    def __init__(self):
        super().__init__()

        self._file_extension_to_slideio_driver = {
            '.svs': 'SVS',
            '.afi': 'AFI',
            '.scn': 'SCN',
            '.czi': 'CZI',
            '.zvi': 'ZVI',
            '.ndpi': 'NDPI',
            '.tiff': 'GDAL',
            '.tif': 'GDAL',
        }

    def _read_file(self, path: Path, palette=None, as_gray=False, **kwargs) -> Raster:
        logger.info('Reading Whole-Slide Image: %s', path.name)

        file_extension = path.suffix.lower()
        driver = self._file_extension_to_slideio_driver.get(file_extension)
        if driver is None:
            raise ValueError(f'Unsupported WSI format: {file_extension}')

        # Create backend (parses metadata, does not read pixels)
        backend = SlideIoBackend(slide_path=path, driver=driver)
        logger.info('WSI backend created: %s', backend)

        # Create Raster without array, with backend
        wsi_raster = FlatImage(  # TODO: return Raster here instead of FlatImage
            array=None,
            palette=palette,
            path=path,
            backend=backend,
        )

        return wsi_raster
