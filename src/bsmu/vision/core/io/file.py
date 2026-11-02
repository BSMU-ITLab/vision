"""Base contracts for reading and writing data files."""
from __future__ import annotations

import abc
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.data import Data

if TYPE_CHECKING:
    from bsmu.vision.core.task import Task

from typing import Iterator


def iter_file_suffixes(path: Path) -> Iterator[str]:
    """Yield all suffixes after dots, from longest to shortest.

    Example: ``image.nii.gz`` yields ``image.nii.gz``, ``nii.gz``, ``gz``.
    """
    name = path.name.lower()
    while True:
        yield name

        dot_index = name.find('.')
        if dot_index == -1:
            break

        name = name[dot_index + 1:]  # dot_index + 1 to remove dot


def _matches_file_format(path: Path, formats: tuple[str, ...]) -> bool:
    """Return True if `path` matches one of `formats`."""
    return any(suffix in formats for suffix in iter_file_suffixes(path))


class FileReaderMeta(type(QObject), abc.ABCMeta):
    _FORMATS: ClassVar[tuple[str, ...]] = ()

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        if not inspect.isabstract(cls) and not cls.formats:
            raise NotImplementedError('Subclass must define _FORMATS attribute')

        return cls

    @property
    def formats(cls) -> tuple[str, ...]:
        return cls._FORMATS

    @property
    def processed_keys(cls) -> tuple[str, ...]:
        return cls.formats


class FileWriterMeta(type(QObject), abc.ABCMeta):
    _FORMATS: ClassVar[tuple[str, ...]] = ()

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        if not inspect.isabstract(cls) and not cls.formats:
            raise NotImplementedError('Subclass must define _FORMATS attribute')

        return cls

    @property
    def formats(cls) -> tuple[str, ...]:
        return cls._FORMATS


class FileReader(QObject, metaclass=FileReaderMeta):
    file_read = Signal(Data)

    @classmethod
    def can_read(cls, path: Path) -> bool:
        """Return True if a file with `path` can be read by this reader."""
        return _matches_file_format(path, cls._FORMATS)

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


class FileWriter(QObject, metaclass=FileWriterMeta):
    file_written = Signal(Path)

    @classmethod
    def can_write(cls, path: Path) -> bool:
        """Return True if a file with `path` can be written by this writer."""
        return _matches_file_format(path, cls._FORMATS)

    def write_to_file(self, data: Data, path: Path, mkdir: bool = False, **kwargs) -> None:
        if mkdir:
            path.parent.mkdir(parents=True, exist_ok=True)

        self._write_to_file(data, path, **kwargs)
        self.file_written.emit(path)

    @abc.abstractmethod
    def _write_to_file(self, data: Data, path: Path, **kwargs) -> None:
        pass
