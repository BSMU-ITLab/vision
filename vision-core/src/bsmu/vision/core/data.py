from __future__ import annotations

from PySide2.QtCore import QObject, Signal


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
        return self.path.parent.name

    def update(self):
        self.updated.emit()
