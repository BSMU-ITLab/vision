from __future__ import annotations

from bsmu.vision.io.raster.nifti import NiftiRasterFileReader
from bsmu.vision.plugins.io.raster import RasterFileReaderPlugin


class NiftiRasterFileReaderPlugin(RasterFileReaderPlugin):
    def __init__(self):
        super().__init__(NiftiRasterFileReader)
