from __future__ import annotations

import numpy as np
from PySide2.QtCore import QObject


class ColorTransferFunctionPoint(QObject):
    def __init__(self, x: float, color_array: np.ndarray):
        super().__init__()

        self.x = x
        self.color_array = color_array


class ColorTransferFunction(QObject):
    def __init__(self):
        super().__init__()

        self.points = []

    def add_point(self, point: ColorTransferFunctionPoint):
        self.points.append(point)

    def add_point_from_x_color(self, x: float, color_array: np.ndarray):
        self.add_point(ColorTransferFunctionPoint(x, color_array))
