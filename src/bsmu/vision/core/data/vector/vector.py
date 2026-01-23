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
    shape_about_to_add = Signal(VectorShape)
    shape_added = Signal(VectorShape)
    shape_about_to_remove = Signal(VectorShape)
    shape_removed = Signal(VectorShape)
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
        assert shape not in self._shapes, f'Shape: {shape} already exists'

        self.shape_about_to_add.emit(shape)

        self._adopt_shape(shape)
        self._shapes.append(shape)

        self.shape_added.emit(shape)

    def remove_shape(self, shape: VectorShape) -> None:
        assert shape in self._shapes, f'No such shape: {shape}'

        self.shape_about_to_remove.emit(shape)

        self._shapes.remove(shape)
        shape.setParent(None)

        self.shape_removed.emit(shape)

    def contains_shape(self, shape: VectorShape) -> bool:
        return shape in self._shapes

    def _adopt_shape(self, shape: VectorShape) -> None:
        shape.setParent(self)
