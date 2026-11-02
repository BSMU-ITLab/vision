from __future__ import annotations

from bsmu.vision.core.io.raster import RasterFileReader, RasterFileWriter
from bsmu.vision.plugins.io.file import FileReaderPlugin, FileWriterPlugin


class RasterFileReaderPlugin(FileReaderPlugin):
    def __init__(self, file_reader_cls: type[RasterFileReader]):
        super().__init__(file_reader_cls)


class RasterFileWriterPlugin(FileWriterPlugin):
    def __init__(self, file_writer_cls: type[RasterFileWriter]):
        super().__init__(file_writer_cls)
