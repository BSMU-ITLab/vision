from __future__ import annotations

import abc
import inspect
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins.processor.base import ProcessorPlugin

if TYPE_CHECKING:
    from typing import Type
    from pathlib import Path


class FileLoaderPlugin(ProcessorPlugin):
    def __init__(self, file_loader_cls: Type[FileLoader]):
        super().__init__(file_loader_cls)


class FileLoaderMeta(type(QObject), abc.ABCMeta):
    _FORMATS = ()

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        if not inspect.isabstract(cls) and not cls.formats:
            raise NotImplementedError('Subclass must define _FORMATS attribute')

        return cls

    @property
    def formats(cls) -> tuple:
        return cls._FORMATS

    @property
    def processed_keys(cls) -> tuple:
        return cls.formats


class FileLoader(QObject, metaclass=FileLoaderMeta):
    file_loaded = Signal(Data)

    def load_file(self, path: Path, **kwargs) -> Data:
        data = self._load_file(path, **kwargs)
        self.file_loaded.emit(data)
        return data

    @abc.abstractmethod
    def _load_file(self, path: Path, **kwargs) -> Data:
        pass
