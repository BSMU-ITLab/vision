from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2 as cv
import pypdfium2 as pdfium

from bsmu.vision.core.config import Config
from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.io.raster import RasterFileReader

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class PdfReaderConfig(Config):
    scale: float = 3.0   # Render scale (1.0 = 72 DPI)
    page_index: int = 0  # Zero-based index of the page to read


class PdfRasterFileReader(RasterFileReader):
    """Reader that rasterizes a PDF page into a 2D raster."""

    _FORMATS = ('pdf',)

    # TODO: it's a temporary workaround to pass config into class.
    #  Remove this, when config will be passed into all processor classes.
    # Overridden by PdfRasterFileReaderPlugin from the plugin config.
    config = PdfReaderConfig()

    def _read_file(self, path: Path, palette=None, as_gray=False, **kwargs) -> Raster:
        logging.info('Read PDF: %s', path.name)
        doc = pdfium.PdfDocument(str(path))
        try:
            if self.config.page_index >= len(doc):
                raise ValueError(
                    f'PDF {path.name} has {len(doc)} page(s), '
                    f'but page_index is {self.config.page_index}')
            page = doc[self.config.page_index]
            # Render into an opaque 3-channel BGR bitmap: any transparency is composited
            # onto the background, so the output is uniform regardless of PDF content.
            bitmap = page.render(scale=self.config.scale, force_bitmap_format=pdfium.raw.FPDFBitmap_BGR)
            pixels = cv.cvtColor(bitmap.to_numpy(), cv.COLOR_BGR2GRAY if as_gray else cv.COLOR_BGR2RGB)
        finally:
            doc.close()

        return Raster(pixels, path=path)
