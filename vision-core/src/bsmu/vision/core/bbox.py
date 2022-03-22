from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import Sequence


class BBox:
    def __init__(
            self,
            left: int,      # included
            right: int,     # excluded
            top: int,       # included
            bottom: int,    # excluded
    ):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def resize(self, resize_factor_x: float, resize_factor_y: float):
        self.left = round(resize_factor_x * self.left)
        self.right = round(resize_factor_x * self.right)
        self.top = round(resize_factor_y * self.top)
        self.bottom = round(resize_factor_y * self.bottom)

    def resized(self, resize_factor_x: float, resize_factor_y: float) -> BBox:
        resized_bbox = copy.copy(self)
        resized_bbox.resize(resize_factor_x, resize_factor_y)
        return resized_bbox

    def scale(self, factor_x: float, factor_y: float):
        width_margins = (factor_x - 1) * self.width
        height_margins = (factor_y - 1) * self.height
        self.add_xy_margins(round(width_margins / 2), round(height_margins / 2))

    def scaled(self, factor_x: float, factor_y: float) -> BBox:
        scaled_bbox = copy.copy(self)
        scaled_bbox.scale(factor_x, factor_y)
        return scaled_bbox

    def clip_to_shape(self, shape: Sequence[int]):
        if self.left < 0:
            self.left = 0

        if self.top < 0:
            self.top = 0

        shape_width = shape[1]
        if self.right > shape_width:
            self.right = shape_width

        shape_height = shape[0]
        if self.bottom > shape_height:
            self.bottom = shape_height

    def clipped_to_shape(self, shape: Sequence[int]) -> BBox:
        clipped_bbox = copy.copy(self)
        clipped_bbox.clip_to_shape(shape)
        return clipped_bbox

    def add_margins(self, margin_size: int):
        self.left -= margin_size
        self.right += margin_size
        self.top -= margin_size
        self.bottom += margin_size

    def margins_added(self, margin_size: int) -> BBox:
        bbox_with_margins = copy.copy(self)
        bbox_with_margins.add_margins(margin_size)
        return bbox_with_margins

    def add_xy_margins(self, x_margin: int, y_margin: int):
        self.left -= x_margin
        self.right += x_margin
        self.top -= y_margin
        self.bottom += y_margin

    def move_left(self, value: int):
        self.left -= value
        self.right -= value

    def move_top(self, value: int):
        self.top -= value
        self.bottom -= value

    def pixels(self, array: np.ndarray) -> np.ndarray:
        return array[self.top:self.bottom, self.left:self.right]
