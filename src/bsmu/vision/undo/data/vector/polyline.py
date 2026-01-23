from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from bsmu.vision.core.data.vector.shapes import Polyline
from bsmu.vision.undo import UndoCommand

if TYPE_CHECKING:
    from bsmu.vision.core.data.vector import Vector


class CreatePolylineCommand(UndoCommand):
    def __init__(
        self,
        vector: Vector,
        initial_point: QPointF,
        text: str = 'Create Polyline',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._vector = vector
        self._initial_point = QPointF(initial_point)
        self._polyline: Polyline | None = None

    @property
    def polyline(self) -> Polyline | None:
        return self._polyline

    def redo(self):
        if self._polyline is None:
            self._polyline = Polyline()
            self._polyline.append_point(self._initial_point)

        self._vector.add_shape(self._polyline)

    def undo(self):
        assert self._polyline is not None

        self._vector.remove_shape(self._polyline)
