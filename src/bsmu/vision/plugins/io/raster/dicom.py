from __future__ import annotations

from bsmu.vision.io.raster.dicom import MultiFrameDicomRasterFileReader
from bsmu.vision.plugins.io.raster import RasterFileReaderPlugin


class MultiFrameDicomRasterFileReaderPlugin(RasterFileReaderPlugin):
    def __init__(self):
        super().__init__(MultiFrameDicomRasterFileReader)
