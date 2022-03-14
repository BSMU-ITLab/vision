from __future__ import annotations

import copy
import numbers
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort
from PySide6.QtCore import QObject, Signal, QThreadPool, QTimer

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.core.image import tile_splitter

if TYPE_CHECKING:
    from typing import Callable, List, Tuple, Sequence
    from pathlib import Path
    from concurrent.futures import Future


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


def padded_to_square_shape(image: np.ndarray) -> Tuple[np.ndarray, Padding]:
    max_size = max(image.shape[:2])
    height_pad = max_size - image.shape[0]
    top_pad = int(height_pad / 2)
    bottom_pad = height_pad - top_pad
    width_pad = max_size - image.shape[1]
    left_pad = int(width_pad / 2)
    right_pad = width_pad - left_pad

    pad_value = [0] * image.shape[2]
    image = cv.copyMakeBorder(image, top_pad, bottom_pad, left_pad, right_pad, cv.BORDER_CONSTANT, value=pad_value)
    padding = Padding(left_pad, right_pad, top_pad, bottom_pad)
    return image, padding


def padding_removed(image: np.ndarray, padding: Padding) -> np.ndarray:
    return image[
           padding.top: image.shape[0] - padding.bottom,
           padding.left: image.shape[1] - padding.right,
           ...]


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


class Segmenter(QObject):
    async_finished = Signal(object, object)  # Signal(callback: Callable, result: Tuple | Any)

    def __init__(self, model_params: ModelParams, preload_model: bool = True, parent: QObject = None):
        super().__init__(parent)

        self._model_params = model_params

        self._inference_session: ort.InferenceSession | None = None
        self._inference_session_being_created: bool = False

        # Use this signal to call slot in the thread, where segmenter was created (most often this is the main thread)
        self.async_finished.connect(self._call_async_callback_in_segmenter_thread)

        if preload_model:
            # Use zero timer to start method whenever there are no pending events (see QCoreApplication::exec doc)
            QTimer.singleShot(0, self._preload_model)

    def _preload_model(self):
        QThreadPool.globalInstance().start(self._create_inference_session_with_delay)

    def _create_inference_session_with_delay(self):
        time.sleep(1.5)  # Wait for application is fully loaded to avoid GUI freezes
        self._create_inference_session()

    def _create_inference_session(self):
        while self._inference_session_being_created:
            time.sleep(0.1)

        if self._inference_session is None:
            self._inference_session_being_created = True

            self._inference_session = ort.InferenceSession(
                str(self._model_params.path), providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])

            self._inference_session_being_created = False

    def _segment_batch_without_postresize(self, images: Sequence[np.ndarray]) -> Sequence[np.ndarray]:
        input_image_batch = []

        for image in images:
            # If it's an RGBA-image
            if image.shape[2] == 4:
                # Remove alpha-channel
                image = image[:, :, :3]

            if image.shape[:2] != self._model_params.input_image_size:
                image = cv.resize(image, self._model_params.input_image_size, interpolation=cv.INTER_AREA)

            image = preprocessed_image(image, normalize=True, preprocessing_mode=self._model_params.preprocessing_mode)

            input_image_batch.append(image)

        self._create_inference_session()
        model_inputs: List[ort.NodeArg] = self._inference_session.get_inputs()
        assert len(model_inputs) == 1, 'Segmenter can process only models with one input'
        input_feed = {model_inputs[0].name: input_image_batch}
        model_outputs: List[ort.NodeArg] = self._inference_session.get_outputs()
        output_names = [model_output.name for model_output in model_outputs]
        outputs = self._inference_session.run(output_names, input_feed)
        assert len(outputs) == 1, 'Segmenter can process only models with one output'
        output_mask_batch = outputs[0]

        # Squeeze channels axis
        output_mask_batch = np.squeeze(output_mask_batch, axis=3)
        return output_mask_batch

    def _segment_without_postresize(self, image: np.ndarray) -> np.ndarray:
        return self._segment_batch_without_postresize([image])[0]

    def segment(
            self,
            image: np.ndarray,
            postprocessing: Callable[[np.ndarray], np.ndarray | Tuple] | None = None
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
            image, padding = padded_to_square_shape(image)

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
            largest_component_bbox.move_left(padding.left)
            largest_component_bbox.move_top(padding.top)

            mask = padding_removed(mask, padding)

        largest_component_bbox.clip_to_shape(src_image_shape)

        return mask, largest_component_bbox

    def segment_largest_connected_component_and_return_mask_with_bbox_async(
            self,
            callback: Callable,
            image: np.ndarray,
            use_square_image: bool = True,
    ):
        self._call_async_with_callback(
            callback,
            self.segment_largest_connected_component_and_return_mask_with_bbox,
            image,
            use_square_image,
        )

    def _call_async_callback_in_segmenter_thread(self, callback: Callable, result):
        if type(result) is tuple:
            callback(*result)
        else:
            callback(result)

    def _async_callback_with_future(self, callback: Callable, future: Future):
        """
        This callback most often will be called in the async thread (where async method was called)
        But we want to call |callback| in the thread, where segmenter was created.
        So we use Qt signal to do it.
        See https://doc.qt.io/qt-6/threads-qobject.html#signals-and-slots-across-threads
        """
        result = future.result()
        self.async_finished.emit(callback, result)

    def _call_async_with_callback(self, callback: Callable, async_method: Callable, *async_method_args):
        assert callback is not None, 'Callback to call async method has to be not None'

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(async_method, *async_method_args)
        future.add_done_callback(
            partial(self._async_callback_with_future, callback))

    def segment_on_splitted_into_tiles(
            self,
            image: np.ndarray,
            use_square_image: bool = True,
            tile_grid_shape: Sequence = (3, 3),
            border_size: int = 10,
    ) -> np.ndarray:
        model_input_image_size = self._model_params.input_image_size
        borders_size = 2 * border_size
        model_input_image_size_multiplied_by_tile_shape = (
            (model_input_image_size[0] - borders_size) * tile_grid_shape[0],
            (model_input_image_size[1] - borders_size) * tile_grid_shape[1])

        if use_square_image:
            image, padding = padded_to_square_shape(image)

        image_shape_before_preresize = image.shape
        image = cv.resize(image, model_input_image_size_multiplied_by_tile_shape, interpolation=cv.INTER_AREA)

        # Split image into tiles
        image_tiles = tile_splitter.split_image_into_tiles(image, tile_grid_shape, border_size=border_size)
        # Get mask predictions for tiles
        tile_masks = self._segment_batch_without_postresize(image_tiles)
        # Merge tiles
        mask = tile_splitter.merge_tiles_into_image_with_blending(tile_masks, tile_grid_shape, border_size=border_size)

        # Resize resulted mask to image size
        mask = cv.resize(
            mask, (image_shape_before_preresize[1], image_shape_before_preresize[0]),
            interpolation=cv.INTER_LINEAR_EXACT)

        if use_square_image:
            mask = padding_removed(mask, padding)

        return mask

    def segment_on_splitted_into_tiles_async(
            self,
            callback: Callable,
            image: np.ndarray,
            use_square_image: bool = True,
            tile_grid_shape: Sequence = (3, 3),
            border_size: int = 10,
    ):
        self._call_async_with_callback(
            callback,
            self.segment_on_splitted_into_tiles,
            image,
            use_square_image,
            tile_grid_shape,
            border_size,
        )


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
