from __future__ import annotations

import abc
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Type


class FileWriterPlugin(Plugin):
    def __init__(self, file_writer_cls: Type[FileWriter]):
        super().__init__()

        self._file_writer_cls = file_writer_cls


class FileWriterMeta(type(QObject), abc.ABCMeta):
    _FORMATS = ()

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        if not inspect.isabstract(cls) and not cls.formats:
            raise NotImplementedError('Subclass must define _FORMATS attribute')

        return cls

    @property
    def formats(cls) -> tuple:
        return cls._FORMATS


class FileWriter(QObject, metaclass=FileWriterMeta):
    file_written = Signal(Path)

    def write_to_file(self, data: Data, path: Path, mkdir=False, **kwargs):
        if mkdir:
            path.parent.mkdir(parents=True, exist_ok=True)

        self._write_to_file(data, path, **kwargs)
        self.file_written.emit(path)

    @abc.abstractmethod
    def _write_to_file(self, data: Data, path: Path, **kwargs):
        pass
