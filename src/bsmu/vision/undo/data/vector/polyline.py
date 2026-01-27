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
    def created_polyline(self) -> Polyline:
        if self._polyline is None:
            raise RuntimeError('Command must be pushed to UndoStack before accessing result.')
        return self._polyline

    def redo(self):
        if self._polyline is None:
            self._polyline = Polyline()
            self._polyline.append_point(self._initial_point)

        self._vector.add_shape(self._polyline)

    def undo(self):
        assert self._polyline is not None

        self._vector.remove_shape(self._polyline)


class AddPolylinePointCommand(UndoCommand):
    def __init__(
            self,
            polyline: Polyline,
            point: QPointF,
            text: str = 'Add Polyline Point',
            parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._polyline = polyline
        self._point = point

    def redo(self):
        self._polyline.append_point(self._point)

    def undo(self):
        if self._polyline.is_empty:
            raise ValueError('Polyline is empty. Cannot undo.')

        if self._polyline.end_point is not self._point:
            raise ValueError('End point does not match the point being undone.')

        self._polyline.remove_end_point()
