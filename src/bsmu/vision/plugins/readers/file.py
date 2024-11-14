from __future__ import annotations

import abc
import inspect
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins.processor import ProcessorPlugin

if TYPE_CHECKING:
    from typing import Type
    from pathlib import Path

    from bsmu.vision.core.task import Task


class FileReaderPlugin(ProcessorPlugin):
    def __init__(self, file_reader_cls: Type[FileReader]):
        super().__init__(file_reader_cls)


class FileReaderMeta(type(QObject), abc.ABCMeta):
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


class FileReader(QObject, metaclass=FileReaderMeta):
    file_read = Signal(Data)

    @classmethod
    def can_read(cls, path: Path) -> bool:
        """
        Returns True if a file with the `path` can be read by this reader.
        Start to check file extension from the biggest part after the first dot,
        e.g. for NiftiFile.nii.gz
        at first check 'nii.gz', then check 'gz'
        """
        file_extension = path.name.lower()
        while True:
            if file_extension in cls._FORMATS:
                return True

            dot_index = file_extension.find('.')
            if dot_index == -1:
                return False

            file_extension = file_extension[dot_index + 1:]  # dot_index + 1 to remove dot

    def read_file(self, path: Path, **kwargs) -> Data:
        data = self._read_file(path, **kwargs)
        self.file_read.emit(data)
        return data

    def read_file_async(self, path: Path, **kwargs) -> Task:
        return ThreadPool.call_async(
            self.read_file,
            path,
            **kwargs,
        )

    @abc.abstractmethod
    def _read_file(self, path: Path, **kwargs) -> Data:
        pass
