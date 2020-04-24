from __future__ import annotations

import numpy as np
from PySide2.QtCore import QObject, Signal
from PySide2.QtGui import QColor
from sortedcontainers import SortedList


class ColorTransferFunctionPoint(QObject):
    x_changed = Signal(float)
    color_array_changed = Signal(np.ndarray)

    def __init__(self, x: float, color_array: np.ndarray):
        super().__init__()

        self._x = x
        self._color_array = color_array

    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, value: float):
        if self._x != value:
            self._x = value
            self.x_changed.emit(self._x)

    @property
    def color_array(self) -> np.ndarray:
        return self._color_array

    @color_array.setter
    def color_array(self, value: np.ndarray):
        if (self._color_array != value).any():
            self._color_array = value
            self.color_array_changed.emit(self._color_array)

    @property
    def color(self) -> QColor:
        return QColor(*self.color_array)

    @color.setter
    def color(self, value: QColor):
        self.color_array = np.array([value.red(), value.green(), value.blue(), value.alpha()])

    def __lt__(self, other):
        return self.x < other.x


class ColorTransferFunction(QObject):
    point_added = Signal(ColorTransferFunctionPoint)

    def __init__(self):
        super().__init__()

        self.points = SortedList()

    def add_point(self, point: ColorTransferFunctionPoint):
        self.points.add(point)
        self.point_added.emit(point)

    def add_point_from_x_color(self, x: float, color_array: np.ndarray = np.array([0, 0, 0, 255])):
        self.add_point(ColorTransferFunctionPoint(x, color_array))

    def point_before(self, point: ColorTransferFunctionPoint) -> ColorTransferFunctionPoint:
        return self.points[self.points.index(point) - 1]

    def point_after(self, point: ColorTransferFunctionPoint) -> ColorTransferFunctionPoint:
        return self.points[self.points.index(point) + 1]
