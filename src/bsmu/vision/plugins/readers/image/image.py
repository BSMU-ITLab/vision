from __future__ import annotations

import abc
from typing import Type

from bsmu.vision.plugins.readers.file import FileReaderPlugin, FileReader


class ImageFileReaderPlugin(FileReaderPlugin):
    def __init__(self, file_reader_cls: Type[FileReader]):
        super().__init__(file_reader_cls)


class ImageFileReader(FileReader):
    @abc.abstractmethod  # Method was added to fix current PySide bug, when inspect.isabstract returns False
    # for classes without explicit abstract methods
    # https://bugreports.qt.io/browse/PYSIDE-1767
    def _read_file(self, path: Path, **kwargs) -> Data:
        pass
