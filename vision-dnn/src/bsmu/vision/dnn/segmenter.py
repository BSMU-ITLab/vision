from __future__ import annotations

import copy
import numbers
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort

import bsmu.vision.core.converters.image as image_converter

if TYPE_CHECKING:
    from typing import Callable, List, Tuple, Sequence
    from pathlib import Path


class ModelParams:
    def __init__(
            self,
            path: Path,
            input_size: tuple = (256, 256, 3),
            preprocessing_mode: str = 'image-net-torch'
    ):
        self._path = path
        self._input_size = input_size
        self._preprocessing_mode = preprocessing_mode

    @property
    def path(self) -> Path:
        return self._path

    @property
    def input_size(self) -> tuple:
        return self._input_size

    @property
    def input_image_size(self) -> tuple:
        return self.input_size[:2]

    @property
    def input_channels_qty(self) -> int:
        return self.input_size[2]

    @property
    def preprocessing_mode(self) -> str:
        return self._preprocessing_mode


def preprocessed_image(image: np.ndarray, normalize: bool = True, preprocessing_mode: str = 'image-net-torch') \
        -> np.ndarray:
    if normalize:
        image = image_converter.normalized(image).astype(np.float_)

    mean = None
    std = None
    if preprocessing_mode == 'image-net-torch':
        # Normalize each channel with respect to the ImageNet dataset
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]
    elif preprocessing_mode == 'image-net-tf':
        # Scale pixels between -1 and 1, sample-wise
        image *= 2
        image -= 1

    if mean is not None:
        image -= mean

    if std is not None:
        image /= std

    return image


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

    def move_left(self, value: int):
        self.left -= value
        self.right -= value

    def move_top(self, value: int):
        self.top -= value
        self.bottom -= value


def largest_connected_component_label(mask: np.ndarray) -> Tuple[int | None, np.ndarray, BBox | None]:
    """
    Find a connected component with the largest area (exclude background label, which is 0)
    :param mask: mask to find connected components
    :return: Tuple[largest connected component label, labeled mask, largest connected component bbox]
    If all pixels are background (zeros), then return None as the largest connected component label
    """

    assert mask.dtype == np.uint8, 'The mask must have np.uint8 type'

    labels_qty, labeled_mask, stats_by_component_label, centroids = cv.connectedComponentsWithStats(mask)
    largest_area = 0
    label_with_largest_area = None
    for label in range(1, labels_qty):
        label_area = stats_by_component_label[label, cv.CC_STAT_AREA]
        if label_area > largest_area:
            largest_area = label_area
            label_with_largest_area = label
    if label_with_largest_area is None:
        largest_component_bbox = None
    else:
        largest_component_stats_array = stats_by_component_label[label_with_largest_area]
        largest_component_left = largest_component_stats_array[cv.CC_STAT_LEFT]
        largest_component_top = largest_component_stats_array[cv.CC_STAT_TOP]
        largest_component_bbox = BBox(
            largest_component_left,
            largest_component_left + largest_component_stats_array[cv.CC_STAT_WIDTH],
            largest_component_top,
            largest_component_top + largest_component_stats_array[cv.CC_STAT_HEIGHT],
        )
    return label_with_largest_area, labeled_mask, largest_component_bbox


class Segmenter:
    def __init__(self, model_params: ModelParams):
        self._model_params = model_params

        self._inference_session: ort.InferenceSession | None = None

    def _create_inference_session(self):
        if self._inference_session is None:
            self._inference_session = ort.InferenceSession(
                str(self._model_params.path), providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])

    def _segment_without_postresize(self, image: np.ndarray) -> np.ndarray:
        # If it's an RGBA-image
        if image.shape[2] == 4:
            # Remove alpha-channel
            image = image[:, :, :3]

        image = cv.resize(image, self._model_params.input_image_size, interpolation=cv.INTER_AREA)
        image = preprocessed_image(image, normalize=True, preprocessing_mode=self._model_params.preprocessing_mode)

        input_image_batch = [image]

        self._create_inference_session()
        model_inputs: List[ort.NodeArg] = self._inference_session.get_inputs()
        assert len(model_inputs) == 1, 'Segmenter can process only models with one input'
        input_feed = {model_inputs[0].name: input_image_batch}
        model_outputs: List[ort.NodeArg] = self._inference_session.get_outputs()
        output_names = [model_output.name for model_output in model_outputs]
        outputs = self._inference_session.run(output_names, input_feed)
        assert len(outputs) == 1, 'Segmenter can process only models with one output'
        output_mask_batch = outputs[0]

        mask = output_mask_batch[0]
        mask = np.squeeze(mask)
        return mask

    def segment(
            self,
            image: np.ndarray,
            postprocessing: Callable[[np.ndarray], np.ndarray | Tuple[np.ndarray, ...]] | None = None
    ) -> np.ndarray:
        mask = self._segment_without_postresize(image)

        if postprocessing is not None:
            postprocessing_result = postprocessing(mask)
            if isinstance(postprocessing_result, tuple):
                mask = postprocessing_result[0]
            else:
                mask = postprocessing_result

        src_image_shape = image.shape
        mask = cv.resize(mask, (src_image_shape[1], src_image_shape[0]), interpolation=cv.INTER_LINEAR_EXACT)

        return mask

    def segment_largest_connected_component_and_return_mask_with_bbox(
            self, image: np.ndarray, use_square_image: bool = True) -> Tuple[np.ndarray, BBox]:
        src_image_shape = image.shape

        if use_square_image:
            max_size = max(src_image_shape[:2])
            height_border = max_size - src_image_shape[0]
            top_border = int(height_border / 2)
            bottom_border = height_border - top_border
            width_border = max_size - src_image_shape[1]
            left_border = int(width_border / 2)
            right_border = width_border - left_border

            border_value = [0] * image.shape[2]
            image = cv.copyMakeBorder(
                image, top_border, bottom_border, left_border, right_border, cv.BORDER_CONSTANT, value=border_value)

        image_shape_before_preresize = image.shape
        mask = self._segment_without_postresize(image)
        mask, largest_component_bbox = largest_connected_component_mask(mask)

        resize_factor_x = image_shape_before_preresize[1] / mask.shape[1]
        resize_factor_y = image_shape_before_preresize[0] / mask.shape[0]
        largest_component_bbox.resize(resize_factor_x, resize_factor_y)

        mask = cv.resize(
            mask,
            (image_shape_before_preresize[1], image_shape_before_preresize[0]),
            interpolation=cv.INTER_NEAREST_EXACT
        )

        if use_square_image:
            largest_component_bbox.move_left(left_border)
            largest_component_bbox.move_top(top_border)

            mask = mask[
                   top_border:image_shape_before_preresize[0] - bottom_border,
                   left_border: image_shape_before_preresize[1] - right_border,
                   ...]

        largest_component_bbox.clip_to_shape(src_image_shape)

        return mask, largest_component_bbox


def largest_connected_component_soft_mask(soft_mask: np.ndarray) -> Tuple[np.ndarray, BBox]:
    """
    Erase all pixels, which do not belong to the largest connected component.
    :return: Tuple[soft mask with only largest connected component, largest connected component bbox]
    """

    assert issubclass(soft_mask.dtype.type, numbers.Real), 'This function is created for soft mask processing.'

    mask = np.round(soft_mask).astype(np.uint8)
    label_with_largest_area, labeled_mask, largest_component_bbox = largest_connected_component_label(mask)
    soft_mask_with_largest_connected_component = soft_mask.copy()
    # Do not erase zero-pixels to get soft mask
    soft_mask_with_largest_connected_component[
        np.logical_and(labeled_mask != label_with_largest_area, labeled_mask != 0)] = 0
    return soft_mask_with_largest_connected_component, largest_component_bbox


def largest_connected_component_mask(soft_mask: np.ndarray) -> Tuple[np.ndarray, BBox]:
    """
    Erase all pixels, which do not belong to the largest connected component.
    :return: Tuple[binarized mask with only largest connected component, largest connected component bbox]
    """

    assert issubclass(soft_mask.dtype.type, numbers.Real), 'This function is created for soft mask processing.'

    mask = np.round(soft_mask).astype(np.uint8)
    label_with_largest_area, labeled_mask, largest_component_bbox = largest_connected_component_label(mask)
    mask[labeled_mask != label_with_largest_area] = 0
    return mask, largest_component_bbox
