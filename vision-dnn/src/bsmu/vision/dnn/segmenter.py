from __future__ import annotations

import numbers
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort

import bsmu.vision.core.converters.image as image_converter

if TYPE_CHECKING:
    from typing import Callable, List, Tuple
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


def largest_connected_component_label(mask: np.ndarray) -> Tuple[int | None, np.ndarray]:
    """
    Find a connected component with the largest area (exclude background label, which is 0)
    :param mask: mask to find connected components
    :return: Tuple[largest connected component label, labeled mask]
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
    return label_with_largest_area, labeled_mask


class Segmenter:
    def __init__(self, model_params: ModelParams):
        self._model_params = model_params

        self._inference_session: ort.InferenceSession | None = None

    def segment(
            self,
            image: np.ndarray,
            postprocessing: Callable[[np.ndarray], np.ndarray] | None = None
    ) -> np.ndarray:

        if self._inference_session is None:
            self._inference_session = ort.InferenceSession(
                str(self._model_params.path), providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])

        src_image_shape = image.shape
        image = cv.resize(image, self._model_params.input_image_size, interpolation=cv.INTER_AREA)
        image = preprocessed_image(image, normalize=True, preprocessing_mode=self._model_params.preprocessing_mode)

        input_image_batch = [image]

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

        if postprocessing is not None:
            mask = postprocessing(mask)

        mask = cv.resize(mask, (src_image_shape[1], src_image_shape[0]), interpolation=cv.INTER_LINEAR_EXACT)

        return mask


def largest_connected_component_soft_mask(soft_mask: np.ndarray) -> np.ndarray:
    """
    Erase all pixels, which do not belong to the largest connected component.
    :return: soft mask with only largest connected component
    """

    assert issubclass(soft_mask.dtype.type, numbers.Real), 'This function is created for soft mask processing.'

    mask = np.round(soft_mask).astype(np.uint8)
    label_with_largest_area, labeled_mask = largest_connected_component_label(mask)
    soft_mask_with_largest_connected_component = soft_mask.copy()
    # Do not erase zero-pixels to get soft mask
    soft_mask_with_largest_connected_component[
        np.logical_and(labeled_mask != label_with_largest_area, labeled_mask != 0)] = 0
    return soft_mask_with_largest_connected_component


def largest_connected_component_mask(soft_mask: np.ndarray) -> np.ndarray:
    """
    Erase all pixels, which do not belong to the largest connected component.
    :return: binarized mask with only largest connected component
    """

    assert issubclass(soft_mask.dtype.type, numbers.Real), 'This function is created for soft mask processing.'

    mask = np.round(soft_mask).astype(np.uint8)
    label_with_largest_area, labeled_mask = largest_connected_component_label(mask)
    mask[labeled_mask != label_with_largest_area] = 0
    return mask
