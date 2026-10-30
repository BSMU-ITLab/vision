"""Contracts for saving and loading LayeredData projects.

Planned project file modes:
- referenced: stores links to original files;
- self-contained: embeds all data inside the project file.
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from bsmu.vision.core.io import FileReader, FileWriter

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.data.layered import LayeredData


class ProjectFileReader(FileReader):
    """Contract for loading LayeredData projects."""

    @abc.abstractmethod  # workaround for PYSIDE-1767
    def _read_file(self, path: Path, **kwargs) -> LayeredData:
        pass


class ProjectFileWriter(FileWriter):
    """Contract for saving LayeredData projects."""

    @abc.abstractmethod  # workaround for PYSIDE-1767
    def _write_to_file(self, data: LayeredData, path: Path, **kwargs) -> None:
        pass
