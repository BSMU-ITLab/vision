from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.io.raster import RasterFileReader
from bsmu.vision.io.raster.wsi.slideio_backend import SlideIoBackend

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.palette import Palette

logger = logging.getLogger(__name__)


class WholeSlideRasterFileReader(RasterFileReader):
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

    def _read_file(self, path: Path, palette: Palette | None = None, as_gray: bool = False, **kwargs) -> Raster:
        logger.info('Reading Whole-Slide Image: %s', path.name)

        file_extension = path.suffix.lower()
        driver = self._file_extension_to_slideio_driver.get(file_extension)
        if driver is None:
            raise ValueError(f'Unsupported WSI format: {file_extension}')

        # Create backend (parses metadata, does not read pixels)
        backend = SlideIoBackend(slide_path=path, driver=driver)
        logger.info('WSI backend created: %s', backend)

        # Create Raster without array, with backend
        return Raster(array=None, palette=palette, path=path, backend=backend)
