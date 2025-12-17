from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from PySide6.QtCore import QObject

from bsmu.vision.core.data import Data

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtCore import QPointF


class Vector(Data):
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
            if shape.parent() is None:
                shape.setParent(self)

    @property
    def shapes(self) -> list[VectorShape]:
        return self._shapes


class VectorShape(QObject):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)


class Polyline(VectorShape):
    _points: list[QPointF]

    def __init__(
            self,
            points: Iterable[QPointF] = (),
            *,
            copy: bool = True,
            parent: QObject | None = None
    ):
        super().__init__(parent)

        if copy:
            self._points = list(points)
        else:
            self._points = points if isinstance(points, list) else list(points)

    @property
    def points(self) -> list[QPointF]:
        return self._points


class Point(VectorShape):
    def __init__(self, pos: QPointF, parent: QObject | None = None):
        super().__init__(parent)

        self._pos: QPointF = pos

    @property
    def pos(self) -> QPointF:
        return self._pos
