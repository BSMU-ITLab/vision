from __future__ import annotations

from PySide2.QtWidgets import QWidget


class DataViewer(QWidget):
    def __init__(self, data: Data = None):
        super().__init__()

        self.data = data

    @property
    def data_path_name(self):
        return self.data.path_name
