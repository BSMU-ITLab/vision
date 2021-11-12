from __future__ import annotations

import abc
import inspect
from typing import Type

from PySide2.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugin.processor import ProcessorPlugin


class FileLoaderPlugin(ProcessorPlugin):
    def __init__(self, file_loader_cls: Type[FileLoader]):
        super().__init__(file_loader_cls)


class FileLoaderMeta(abc.ABCMeta, type(QObject)):
    _FORMATS = ()

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)

        if not inspect.isabstract(cls) and not cls.formats:
            raise NotImplementedError('Subclass must define formats attribute')

        return cls

    @property
    def formats(cls) -> tuple:
        return cls._FORMATS

    @property
    def processed_keys(cls) -> tuple:
        return cls.formats


class FileLoader(QObject, metaclass=FileLoaderMeta):
    #% _FORMATS = ()

    file_loaded = Signal(Data)

    @property
    def formats(self):
        return type(self).formats

    def load_file(self, path: Path, **kwargs) -> Data:
        data = self._load_file(path, **kwargs)
        self.file_loaded.emit(data)
        return data

    @abc.abstractmethod
    def _load_file(self, path: Path, **kwargs) -> Data:
        pass
