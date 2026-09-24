from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SliceController(QObject):
    """Controls current slice number for 3D data. Can be shared between viewers to synchronize."""

    slice_changed = Signal(object)  # Emits int | None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._slice_number: int | None = None

    @property
    def slice_number(self) -> int | None:
        return self._slice_number

    @slice_number.setter
    def slice_number(self, value: int | None) -> None:
        if self._slice_number != value:
            self._slice_number = value
            self.slice_changed.emit(self._slice_number)
