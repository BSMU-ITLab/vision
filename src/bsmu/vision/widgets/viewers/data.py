from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from bsmu.vision.core.data import Data


class DataViewer(QWidget):
    def __init__(self, data: Data = None, parent: QWidget = None):
        super().__init__(parent)

        self._data = None
        self.data = data

        # Cursor shape should only be changed by the current cursor owner
        self._cursor_owner: QObject | None = None

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

    @property
    def cursor_owner(self) -> QObject | None:
        return self._cursor_owner

    @cursor_owner.setter
    def cursor_owner(self, value: QObject | None):
        if value is not None and self._cursor_owner is not None:
            raise RuntimeError(
                f'Cursor ownership conflict: current owner is "{type(self._cursor_owner).__name__}", '
                f'attempted reassignment to "{type(value).__name__}"'
            )

        self._cursor_owner = value
        self._on_cursor_owner_changed()

    def _on_cursor_owner_changed(self):
        pass

    def _on_data_changing(self):
        pass

    def _on_data_changed(self):
        pass
