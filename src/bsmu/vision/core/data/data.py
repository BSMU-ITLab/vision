from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal


class Data(QObject):
    path_changed = Signal(Path)
    updated = Signal()

    def __init__(self, path: Path | None = None):
        super().__init__()

        self._path = path

    @property
    def path(self) -> Path | None:
        return self._path

    @path.setter
    def path(self, value: Path | None):
        if self._path != value:
            self._path = value
            self.path_changed.emit(self._path)

    @property
    def path_name(self):
        return '' if self._path is None else self._path.name

    @property
    def dir_name(self):
        return '' if self._path is None else self._path.parent.name

    def update(self):
        self.updated.emit()


class DataHolder(Protocol):
    @property
    def data(self) -> Data:
        pass

    @data.setter
    def data(self, value: Data):
        pass

    @property
    def data_path_name(self) -> str:
        pass

    def _on_data_changing(self):
        pass

    def _on_data_changed(self):
        pass
