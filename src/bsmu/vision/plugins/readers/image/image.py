from __future__ import annotations

from typing import TYPE_CHECKING, Type

from bsmu.vision.plugins.readers.file import FileReaderPlugin

if TYPE_CHECKING:
    from bsmu.vision.core.io.raster import RasterFileReader


class ImageFileReaderPlugin(FileReaderPlugin):
    def __init__(self, file_reader_cls: Type[RasterFileReader]):
        super().__init__(file_reader_cls)
