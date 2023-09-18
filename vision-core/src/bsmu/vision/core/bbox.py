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

    def __str__(self):
        return f'{self.__class__.__name__} {hex(id(self))}: ' \
               f'rc-format: [{self.top}:{self.bottom}, {self.left}:{self.right}]'

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    @property
    def empty(self) -> bool:
        return self.width == 0 or self.height == 0

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
        self.left, self.right = np.clip([self.left, self.right], 0, shape[1])
        self.top, self.bottom = np.clip([self.top, self.bottom], 0, shape[0])

    def clip_to_shape_and_return_clip_bbox(self, shape: Sequence[int]) -> BBox:
        src_bbox = copy.copy(self)
        self.clip_to_shape(shape)
        return self.calculate_clip_bbox(src_bbox)

    def clipped_to_shape(self, shape: Sequence[int]) -> BBox:
        clipped_bbox = copy.copy(self)
        clipped_bbox.clip_to_shape(shape)
        return clipped_bbox

    def calculate_clip_bbox(self, src_bbox: BBox) -> BBox:
        """Calculates bbox, which have to be applied to |src_bbox| to get |self| (clipped bbox)
        :param src_bbox: source (not clipped) bbox
        :return: calculated bbox
        """
        return BBox(
            self.left - src_bbox.left,
            src_bbox.width - (src_bbox.right - self.right),
            self.top - src_bbox.top,
            src_bbox.height - (src_bbox.bottom - self.bottom)
        )

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

    def map_rc_point(self, point: Sequence) -> tuple:
        """Map point into coordinates of this BBox
        :param point: point in (row, col) format
        :return: mapped point in (row, col) format
        """
        return point[0] - self.top, point[1] - self.left

    def map_to_bbox(self, other: BBox):
        """Map |self| to coordinates of |other|
        If both bboxes are from the same array, and |other| includes |self|,
        then |self| will get its bbox values relative to |other|
        """
        self.move_left(other.left)
        self.move_top(other.top)

    def mapped_to_bbox(self, other: BBox) -> BBox:
        mapped_bbox = copy.copy(self)
        mapped_bbox.map_to_bbox(other)
        return mapped_bbox

    def unite_with(self, other: BBox):
        self.left = min(self.left, other.left)
        self.right = max(self.right, other.right)
        self.top = min(self.top, other.top)
        self.bottom = max(self.bottom, other.bottom)

    def united_with(self, other: BBox) -> BBox:
        united_bbox = copy.copy(self)
        united_bbox.unite_with(other)
        return united_bbox
