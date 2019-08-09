from __future__ import annotations

from PySide2.QtCore import QObject, Signal


class Data(QObject):
    updated = Signal()

    def __init__(self, path: Path = None):
        super().__init__()

        self.path = path

    def update(self):
        self.updated.emit()
