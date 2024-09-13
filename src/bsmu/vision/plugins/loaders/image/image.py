from __future__ import annotations

import abc
from typing import Type

from bsmu.vision.plugins.loaders.file import FileLoaderPlugin, FileLoader


class ImageFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, file_loader_cls: Type[FileLoader]):
        super().__init__(file_loader_cls)


class ImageFileLoader(FileLoader):
    @abc.abstractmethod  # Method was added to fix current PySide bug, when inspect.isabstract returns False
    # for classes without explicit abstract methods
    # https://bugreports.qt.io/browse/PYSIDE-1767
    def _load_file(self, path: Path, **kwargs) -> Data:
        pass
