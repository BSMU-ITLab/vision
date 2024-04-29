from __future__ import annotations

from typing import Protocol
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from pathlib import Path


class Data(QObject):
    updated = Signal()

    def __init__(self, path: Path = None):
        super().__init__()

        self.path = path

    @property
    def path_name(self):
        return '' if self.path is None else self.path.name

    @property
    def dir_name(self):
        return '' if self.path is None else self.path.parent.name

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
