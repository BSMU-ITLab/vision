from __future__ import annotations

from bsmu.vision.io.raster.common import CommonRasterFileReader
from bsmu.vision.plugins.readers.image import ImageFileReaderPlugin


class CommonImageFileReaderPlugin(ImageFileReaderPlugin):
    def __init__(self):
        super().__init__(CommonRasterFileReader)
