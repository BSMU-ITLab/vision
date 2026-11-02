from __future__ import annotations

from bsmu.vision.io.raster.wsi.reader import WholeSlideRasterFileReader
from bsmu.vision.plugins.io.raster import RasterFileReaderPlugin


class WholeSlideRasterFileReaderPlugin(RasterFileReaderPlugin):
    def __init__(self):
        super().__init__(WholeSlideRasterFileReader)
