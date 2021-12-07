from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject, Signal
from PySide2.QtGui import QColor
from sortedcontainers import SortedList

from bsmu.vision.core.data import Data

if TYPE_CHECKING:
    from typing import List, Tuple

    from pathlib import Path


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


class ColorTransferFunction(Data):
    point_added = Signal(ColorTransferFunctionPoint)

    def __init__(self, path: Path = None):
        super().__init__(path)

        self.points = SortedList()

    @classmethod
    def from_x_fractions_colors_array(
            cls,
            x_fractions_colors_array: List[List[float | int]] | np.ndarray,
            max_x: int = 255,
    ) -> ColorTransferFunction:

        color_transfer_function = cls()
        for row in x_fractions_colors_array:
            x_fraction = row[0]
            color_array = row[1:]
            color_transfer_function.add_point_from_x_color(x_fraction * max_x, color_array)
        return color_transfer_function

    @classmethod
    def default_jet(cls, max_x: int = 255) -> ColorTransferFunction:
        return ColorTransferFunction.from_x_fractions_colors_array(
            [[0, 0, 0, 255, 255],
             [0.25, 0, 255, 255, 255],
             [0.5, 0, 255, 0, 255],
             [0.75, 255, 255, 0, 255],
             [1, 255, 0, 0, 255]],
            max_x)

    @classmethod
    def default_from_color_to_color(
            cls,
            from_color: Tuple[int] | List[int] | np.ndarray = (255, 255, 255, 0),
            to_color: Tuple[int] | List[int] | np.ndarray = (255, 255, 255, 255),
            max_x: int = 255,
    ) -> ColorTransferFunction:
        return ColorTransferFunction.from_x_fractions_colors_array(
            [[0, *from_color],
             [1, *to_color]],
            max_x)

    @classmethod
    def default_from_transparent_to_opaque_colored_mask(
            cls,
            rgb_color: Tuple[int] | List[int] | np.ndarray = (255, 255, 255),
            max_x: int = 255,
    ) -> ColorTransferFunction:
        return ColorTransferFunction.from_x_fractions_colors_array(
            [[0, *rgb_color, 0],
             [1, *rgb_color, 255]],
            max_x)

    @classmethod
    def default_from_transparent_black_to_opaque_colored_mask(
            cls,
            rgb_color: Tuple[int] | List[int] | np.ndarray = (255, 255, 255),
            max_x: int = 255,
    ) -> ColorTransferFunction:
        return ColorTransferFunction.from_x_fractions_colors_array(
            [[0, 0, 0, 0, 0],
             [1, *rgb_color, 255]],
            max_x)

    def add_point(self, point: ColorTransferFunctionPoint):
        self.points.add(point)
        self.point_added.emit(point)

    def add_point_from_x_color(self, x: float, color_array: np.ndarray = np.full((4,), 255)):
        self.add_point(ColorTransferFunctionPoint(x, color_array))

    def point_before(self, point: ColorTransferFunctionPoint) -> ColorTransferFunctionPoint:
        return self.points[self.points.index(point) - 1]

    def point_after(self, point: ColorTransferFunctionPoint) -> ColorTransferFunctionPoint:
        return self.points[self.points.index(point) + 1]
