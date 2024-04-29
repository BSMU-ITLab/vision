from __future__ import annotations

import cv2 as cv
import numpy as np


class Padding:
    def __init__(
            self,
            left: int,
            right: int,
            top: int,
            bottom: int,
    ):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom


def calculate_padding(shape: tuple[int, ...], target_shape: [int, ...]) -> Padding:
    height, width = shape[:2]
    padded_height, padded_width = target_shape[:2]

    top_pad, bottom_pad = calculate_dim_padding(height, padded_height)
    left_pad, right_pad = calculate_dim_padding(width, padded_width)

    return Padding(left_pad, right_pad, top_pad, bottom_pad)


def calculate_dim_padding(current_dim: int, target_dim: int) -> tuple[int, int]:
    total_padding = max(target_dim - current_dim, 0)
    pad_before = total_padding // 2
    pad_after = total_padding - pad_before
    return pad_before, pad_after


def padded(
        image: np.ndarray,
        padding: Padding,
        border_type: cv.BorderTypes = cv.BORDER_CONSTANT,
        pad_value: cv.typing.Scalar | int = 0,
) -> np.ndarray:
    if isinstance(pad_value, int):
        pad_value = [pad_value] * image.shape[2]
    return cv.copyMakeBorder(
        image, padding.top, padding.bottom, padding.left, padding.right, border_type, value=pad_value)


def padded_to_shape(
        image: np.ndarray,
        padded_shape: tuple[int, int],
        border_type: cv.BorderTypes = cv.BORDER_CONSTANT,
        pad_value: cv.typing.Scalar | int = 0,
) -> tuple[np.ndarray, Padding]:
    padding = calculate_padding(image.shape, padded_shape)
    padded_image = padded(image, padding, border_type, pad_value)
    return padded_image, padding


def padded_to_square_shape(
        image: np.ndarray,
        border_type: cv.BorderTypes = cv.BORDER_CONSTANT,
        pad_value: cv.typing.Scalar | int = 0,
) -> tuple[np.ndarray, Padding]:
    max_size = max(image.shape[:2])
    padding = calculate_padding(image.shape, (max_size, max_size))
    padded_image = padded(image, padding, border_type, pad_value)
    return padded_image, padding


def padding_removed(image: np.ndarray, padding: Padding) -> np.ndarray:
    return image[
           padding.top: image.shape[0] - padding.bottom,
           padding.left: image.shape[1] - padding.right,
           ...]
