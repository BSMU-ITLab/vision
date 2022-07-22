from __future__ import annotations

import copy
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort
from PySide6.QtCore import QObject, Signal, QThreadPool, QTimer

import bsmu.vision.core.converters.image as image_converter

if TYPE_CHECKING:
    from typing import Callable, Tuple, Sequence, Any
    from pathlib import Path
    from concurrent.futures import Future


class ModelParams:
    def __init__(
            self,
            path: Path,
            input_size: tuple | None = None,
            channels_axis: int | None = None,
            channels_order: str | None = None,
            normalize: bool | None = None,
            preprocessing_mode: str | None = None,
            preload_model: bool | None = None,
    ):
        self._path = path
        self._input_size = self.default_if_none(input_size, (256, 256, 3))
        self._channels_axis = self.default_if_none(channels_axis, 2)
        self._channels_order = self.default_if_none(channels_order, 'rgb')
        self._normalize = self.default_if_none(normalize, True)
        self._preprocessing_mode = self.default_if_none(preprocessing_mode, 'image-net-torch')
        self._preload_model = self.default_if_none(preload_model, False)

    @staticmethod
    def default_if_none(value: Any, default: Any) -> Any:
        return default if value is None else value

    @staticmethod
    def from_config(config_data: dict, model_dir: Path) -> ModelParams:
        return ModelParams(
            model_dir / config_data['name'],
            config_data.get('input-size'),
            config_data.get('channels-axis'),
            config_data.get('channels-order'),
            config_data.get('normalize'),
            config_data.get('preprocessing-mode'),
            config_data.get('preload'),
        )

    def copy_but_change_name(self, new_name: str) -> ModelParams:
        model_params_copy = copy.deepcopy(self)
        model_params_copy._path = model_params_copy.path.parent / new_name
        return model_params_copy

    @property
    def path(self) -> Path:
        return self._path

    @property
    def input_size(self) -> tuple:
        return self._input_size

    @property
    def input_image_size(self) -> Sequence:
        input_size_list = list(self.input_size)
        del input_size_list[self._channels_axis]
        return input_size_list

    @property
    def input_channels_qty(self) -> int:
        return self.input_size[self._channels_axis]

    @property
    def channels_axis(self) -> int:
        return self._channels_axis

    @property
    def channels_order(self) -> str:
        return self._channels_order

    @property
    def normalize(self) -> bool:
        return self._normalize

    @property
    def preprocessing_mode(self) -> str:
        return self._preprocessing_mode

    @property
    def preload_model(self) -> bool:
        return self._preload_model


def preprocessed_image(image: np.ndarray, model_params: ModelParams) -> np.ndarray:
    """
    :param image: image to preprocess in RGB, channels-last format
    :param model_params: model parameters used for preprocessing
    :return: preprocessed image
    """
    DEFAULT_CHANNELS_AXIS = 2
    # If it's an RGBA-image
    if image.shape[DEFAULT_CHANNELS_AXIS] == 4:
        # Remove alpha-channel
        image = image[:, :, :3]

    if image.shape[:DEFAULT_CHANNELS_AXIS] != model_params.input_image_size:
        image = cv.resize(image, model_params.input_image_size, interpolation=cv.INTER_AREA)

    if model_params.normalize:
        image = image_converter.normalized(image).astype(np.float_)

    mean = None
    std = None
    if model_params.preprocessing_mode == 'image-net-torch':
        # Normalize each channel with respect to the ImageNet dataset
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]
    elif model_params.preprocessing_mode == 'image-net-tf':
        # Scale pixels between -1 and 1, sample-wise
        image *= 2
        image -= 1

    if mean is not None:
        image -= mean

    if std is not None:
        image /= std

    if model_params.channels_order == 'bgr':
        image = image[..., ::-1]

    image = image.swapaxes(model_params.channels_axis, DEFAULT_CHANNELS_AXIS)

    return image


def preprocessed_image_batch(images: Sequence[np.ndarray], model_params: ModelParams) -> Sequence[np.ndarray]:
    image_batch = []
    for image in images:
        image = preprocessed_image(image, model_params)
        image_batch.append(image)
    return image_batch


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


class Inferencer(QObject):
    async_finished = Signal(object, object)  # Signal(callback: Callable, result: Tuple | Any)

    def __init__(self, model_params: ModelParams, parent: QObject = None):
        super().__init__(parent)

        self._model_params = model_params

        self._inference_session: ort.InferenceSession | None = None
        self._inference_session_being_created: bool = False

        # Use this signal to call slot in the thread, where inferencer was created (most often this is the main thread)
        self.async_finished.connect(self._call_async_callback_in_inferencer_thread)

        if self._model_params.preload_model:
            # Use zero timer to start method whenever there are no pending events (see QCoreApplication::exec doc)
            QTimer.singleShot(0, self._preload_model)

    @property
    def model_params(self) -> ModelParams:
        return self._model_params

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

    def _call_async_callback_in_inferencer_thread(self, callback: Callable, result):
        if type(result) is tuple:
            callback(*result)
        else:
            callback(result)

    def _async_callback_with_future(self, callback: Callable, future: Future):
        """
        This callback most often will be called in the async thread (where async method was called)
        But we want to call |callback| in the thread, where inferencer was created.
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
