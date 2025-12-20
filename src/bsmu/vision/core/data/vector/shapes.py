from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF


class VectorShape(QObject):
    changed = Signal()  # emitted when geometry changes

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)


class Point(VectorShape):
    def __init__(self, pos: QPointF, parent: QObject | None = None):
        super().__init__(parent)

        self._pos: QPointF = pos

    @property
    def pos(self) -> QPointF:
        return self._pos

    @pos.setter
    def pos(self, value: QPointF):
        if self._pos != value:
            self._pos = value
            self.changed.emit()


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
