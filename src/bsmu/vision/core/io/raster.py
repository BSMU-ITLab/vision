"""Contracts for reading and writing raster data."""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from bsmu.vision.core.io.file import FileReader, FileWriter

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.palette import Palette


class RasterFileReader(FileReader):
    """Contract for readers that produce `Raster` data from files."""

    def read_file(
            self,
            path: Path,
            palette: Palette | None = None,
            as_gray: bool = False,
            **kwargs,
    ) -> Raster:
        return super().read_file(path, palette=palette, as_gray=as_gray, **kwargs)

    # Workaround for PYSIDE-1767: inspect.isabstract returns False
    # for classes without explicit abstract methods
    # https://bugreports.qt.io/browse/PYSIDE-1767
    @abc.abstractmethod
    def _read_file(
            self,
            path: Path,
            palette: Palette | None = None,
            as_gray: bool = False,
            **kwargs,
    ) -> Raster:
        pass


class RasterFileWriter(FileWriter):
    """Contract for writers that save `Raster` data to files."""

    def write_to_file(self, data: Raster, path: Path, mkdir: bool = False, **kwargs) -> None:
        super().write_to_file(data, path, mkdir=mkdir, **kwargs)

    @abc.abstractmethod  # workaround for PYSIDE-1767
    def _write_to_file(self, data: Raster, path: Path, **kwargs) -> None:
        pass
