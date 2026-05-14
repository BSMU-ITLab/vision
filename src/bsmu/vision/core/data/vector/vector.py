from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.data.vector.shapes import VectorShape

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Iterable

    from PySide6.QtCore import QObject


class Vector(Data):
    shape_about_to_add = Signal(VectorShape, int)
    shape_added = Signal(VectorShape, int)
    shape_about_to_remove = Signal(VectorShape, int)
    shape_removed = Signal(VectorShape, int)
    # shapes_changed = Signal()  # for bulk changes

    _shapes: list[VectorShape]

    def __init__(
            self,
            path: Path | None = None,
            shapes: Iterable[VectorShape] = (),
            *,
            copy: bool = True,
            parent: QObject | None = None,
    ):
        super().__init__(path, parent)

        if copy:
            self._shapes = list(shapes)
        else:
            # Trust the caller: assume `shapes` is already a list and we take ownership
            self._shapes = shapes if isinstance(shapes, list) else list(shapes)

        for shape in self._shapes:
            self._adopt_shape(shape)

    @property
    def shapes(self) -> list[VectorShape]:
        return self._shapes.copy()  # copy to prevent external mutation

    def add_shape(self, shape: VectorShape) -> None:
        self.insert_shape(shape)

    def insert_shape(self, shape: VectorShape, index: int | None = None) -> None:
        """Inserts a shape at a specific index."""
        assert shape not in self._shapes, f'Shape: {shape} already exists in this vector'

        if index is None:
            index = len(self._shapes)

        self.shape_about_to_add.emit(shape, index)

        self._adopt_shape(shape)
        self._shapes.insert(index, shape)

        self.shape_added.emit(shape, index)

    def remove_shape(self, shape: VectorShape) -> None:
        index = self._shapes.index(shape)
        self.pop_shape(index)

    def pop_shape(self, index: int = -1) -> VectorShape:
        """Remove and return a shape by index. Defaults to last shape."""
        if index == -1:
            index = len(self._shapes) - 1

        self.shape_about_to_remove.emit(self._shapes[index], index)

        shape = self._shapes.pop(index)
        shape.setParent(None)

        self.shape_removed.emit(shape, index)
        return shape

    def contains_shape(self, shape: VectorShape) -> bool:
        return shape in self._shapes

    def _adopt_shape(self, shape: VectorShape) -> None:
        shape.setParent(self)
