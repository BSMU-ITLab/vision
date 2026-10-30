from __future__ import annotations

from bsmu.vision.io.raster.wsi.reader import WholeSlideRasterFileReader
from bsmu.vision.plugins.readers.image import ImageFileReaderPlugin


class WholeSlideImageFileReaderPlugin(ImageFileReaderPlugin):
    def __init__(self):
        super().__init__(WholeSlideRasterFileReader)
