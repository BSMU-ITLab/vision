from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data


class DataViewer(QWidget):
    def __init__(self, data: Data = None, parent: QWidget = None):
        super().__init__(parent)

        self._data = None
        self.data = data

    @property
    def data(self) -> Data:
        return self._data

    @data.setter
    def data(self, value: Data):
        if self._data != value:
            self._on_data_changing()
            self._data = value
            self._on_data_changed()

    @property
    def data_path_name(self):
        return '' if self.data is None else self.data.path_name

    def _on_data_changing(self):
        pass

    def _on_data_changed(self):
        pass
