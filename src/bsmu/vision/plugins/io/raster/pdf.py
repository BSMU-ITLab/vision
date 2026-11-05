from __future__ import annotations

from bsmu.vision.io.raster.pdf import PdfRasterFileReader, PdfReaderConfig
from bsmu.vision.plugins.io.raster import RasterFileReaderPlugin


class PdfRasterFileReaderPlugin(RasterFileReaderPlugin):
    def __init__(self):
        super().__init__(PdfRasterFileReader)

    def _enable(self):
        super()._enable()

        # TODO: it's a temporary workaround to pass the config into reader class.
        #  Remove this, when config will be passed into all processor classes.
        PdfRasterFileReader.config = PdfReaderConfig.from_dict(self.config.full_data)
