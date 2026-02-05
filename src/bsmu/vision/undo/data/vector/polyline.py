from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from bsmu.vision.core.data.vector.shapes import Polyline, VectorNode
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
            self._polyline = Polyline(points=[self._initial_point])

        self._vector.add_shape(self._polyline)

    def undo(self):
        assert self._polyline is not None

        self._vector.remove_shape(self._polyline)


class AddPolylineNodeCommand(UndoCommand):
    def __init__(
            self,
            polyline: Polyline,
            pos: QPointF,
            text: str = 'Add Polyline Point',
            parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._polyline = polyline
        self._pos = pos

        self._node: VectorNode | None = None

    def redo(self):
        self._node = self._polyline.add_node(self._pos)

    def undo(self):
        if self._polyline.is_empty:
            raise ValueError('Polyline is empty. Cannot undo.')

        if self._polyline.last_node is not self._node:
            raise ValueError('The last node does not match the node being undone.')

        self._polyline.remove_last_node()
        self._node = None
