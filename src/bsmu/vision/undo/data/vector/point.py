from __future__ import annotations

from PySide6.QtCore import QPointF

from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.data.vector.shapes import Point
from bsmu.vision.undo import UndoCommand


class CreatePointCommand(UndoCommand):
    """Create a new point in a vector data."""

    def __init__(
            self,
            vector: Vector,
            pos: QPointF,
            text: str = 'Create Point',
            parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._vector = vector
        self._pos = QPointF(pos)  # defensive copy
        self._created_point: Point | None = None

    def redo(self):
        if self._created_point is None:
            self._created_point = Point(self._pos)

        self._vector.add_shape(self._created_point)

    def undo(self):
        assert self._created_point is not None, 'redo() must be called before undo()'

        self._vector.remove_shape(self._created_point)
