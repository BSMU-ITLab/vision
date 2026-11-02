from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.core.plugins import Plugin
from bsmu.vision.core.plugins.processor import ProcessorPlugin

if TYPE_CHECKING:
    from bsmu.vision.core.io import FileReader, FileWriter


class FileReaderPlugin(ProcessorPlugin):
    def __init__(self, file_reader_cls: type[FileReader]):
        super().__init__(file_reader_cls)


class FileWriterPlugin(Plugin):
    def __init__(self, file_writer_cls: type[FileWriter]):
        super().__init__()

        self._file_writer_cls = file_writer_cls
