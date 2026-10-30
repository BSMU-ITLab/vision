"""Contracts for reading and writing vector data.

TODO: define formats and signatures when annotation import/export is designed.
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from bsmu.vision.core.io import FileReader, FileWriter

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.data.vector import Vector


class VectorFileReader(FileReader):
    """Contract for readers that produce vector annotation data."""

    @abc.abstractmethod  # workaround for PYSIDE-1767
    def _read_file(self, path: Path, **kwargs) -> Vector:
        pass


class VectorFileWriter(FileWriter):
    """Contract for writers that save vector annotation data."""

    @abc.abstractmethod  # workaround for PYSIDE-1767
    def _write_to_file(self, data: Vector, path: Path, **kwargs) -> None:
        pass
