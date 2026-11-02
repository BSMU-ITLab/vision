from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pydicom

from bsmu.vision.core.image import VolumeImage
from bsmu.vision.core.io.raster import RasterFileReader

if TYPE_CHECKING:
    from pathlib import Path


class MultiFrameDicomRasterFileReader(RasterFileReader):
    _FORMATS = ('dcm',)

    def _read_file(self, path: Path, **kwargs) -> VolumeImage:
        logging.info('Read Multi-frame DICOM')

        dataset = pydicom.dcmread(str(path))
        return VolumeImage(dataset.pixel_array, path=path)
