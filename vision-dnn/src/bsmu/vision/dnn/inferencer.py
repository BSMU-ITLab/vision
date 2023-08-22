from __future__ import annotations

import copy
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort
from PySide6.QtCore import QObject, Signal, QThreadPool, QTimer

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.dnn.config import OnnxConfig, CPU_PROVIDER

if TYPE_CHECKING:
    from typing import Callable, Tuple, Sequence
    from pathlib import Path
    from concurrent.futures import Future


@dataclass
class ModelParams:
    DEFAULT_PRELOAD_MODEL = False

    path: Path
    preload_model: bool = DEFAULT_PRELOAD_MODEL

    @classmethod
    def from_config(cls, config_data: dict, model_dir: Path) -> ModelParams:
        return ModelParams(
            path=model_dir / config_data['name'],
            preload_model=config_data.get('preload', cls.DEFAULT_PRELOAD_MODEL),
        )

    def preprocessed_input(self, src: np.ndarray) -> np.ndarray:
        pass

    def preprocessed_input_batch(self, src_batch: Sequence[np.ndarray]) -> Sequence[np.ndarray]:
        preprocessed_batch = []
        for src in src_batch:
            src = self.preprocessed_input(src)
            preprocessed_batch.append(src)
        return preprocessed_batch


@dataclass
class ImageModelParams(ModelParams):
    DEFAULT_INPUT_SIZE = (256, 256, 3)
    DEFAULT_CHANNELS_AXIS = 2
    DEFAULT_CHANNELS_ORDER = 'rgb'
    DEFAULT_NORMALIZE = True
    DEFAULT_PREPROCESSING_MODE = 'image-net-torch'

    input_size: Sequence = DEFAULT_INPUT_SIZE
    channels_axis: int = DEFAULT_CHANNELS_AXIS
    channels_order: str = DEFAULT_CHANNELS_ORDER
    normalize: bool = DEFAULT_NORMALIZE
    preprocessing_mode: str = DEFAULT_PREPROCESSING_MODE

    @classmethod
    def from_config(cls, config_data: dict, model_dir: Path) -> ImageModelParams:
        return ImageModelParams(
            path=model_dir / config_data['name'],
            preload_model=config_data.get('preload', cls.DEFAULT_PRELOAD_MODEL),
            input_size=config_data.get('input-size', cls.DEFAULT_INPUT_SIZE),
            channels_axis=config_data.get('channels-axis', cls.DEFAULT_CHANNELS_AXIS),
            channels_order=config_data.get('channels-order', cls.DEFAULT_CHANNELS_ORDER),
            normalize=config_data.get('normalize', cls.DEFAULT_NORMALIZE),
            preprocessing_mode=config_data.get('preprocessing-mode', cls.DEFAULT_PREPROCESSING_MODE),
        )

    def copy_but_change_name(self, new_name: str) -> ImageModelParams:
        model_params_copy = copy.deepcopy(self)
        model_params_copy.path = model_params_copy.path.parent / new_name
        return model_params_copy

    @property
    def input_image_size(self) -> Sequence:
        input_size_list = list(self.input_size)
        del input_size_list[self.channels_axis]
        return input_size_list

    @property
    def input_channels_count(self) -> int:
        return self.input_size[self.channels_axis]

    def preprocessed_input(self, image: np.ndarray) -> np.ndarray:
        """
        :param image: image to preprocess in RGB, channels-last format
        :return: preprocessed image
        """
        DEFAULT_CHANNELS_AXIS = 2
        # If it's an RGBA-image
        if image.shape[DEFAULT_CHANNELS_AXIS] == 4:
            # Remove alpha-channel
            image = image[:, :, :3]

        if image.shape[:DEFAULT_CHANNELS_AXIS] != self.input_image_size:
            image = image.astype(np.float_)
            image = cv.resize(image, self.input_image_size, interpolation=cv.INTER_AREA)

        if self.normalize:
            image = image_converter.normalized(image).astype(np.float_)

        mean = None
        std = None
        if self.preprocessing_mode == 'image-net-torch':
            if not self.normalize:
                image = image / 255
            # Normalize each channel with respect to the ImageNet dataset
            mean = [0.485, 0.456, 0.406]
            std = [0.229, 0.224, 0.225]
        elif self.preprocessing_mode == 'image-net-tf':
            if not self.normalize:
                image = image / 255
            # Scale pixels between -1 and 1, sample-wise
            image *= 2
            image -= 1

        if mean is not None:
            image -= mean

        if std is not None:
            image /= std

        if self.channels_order == 'bgr':
            image = image[..., ::-1]

        image = np.moveaxis(image, DEFAULT_CHANNELS_AXIS, self.channels_axis)

        return image


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

            providers = OnnxConfig.providers
            try:
                self._inference_session = ort.InferenceSession(
                    str(self._model_params.path), providers=providers)
            except Exception as e:
                # Current onnxruntime version throws an error instead of warning,
                # when CUDA provider failed, and does not try other providers (e.g. CPU provider), so do it by self
                logging.warning(f'Cannot create an inference session with {providers} providers. '
                                f'The error: {e}'
                                f'Trying to create the inference session using only {CPU_PROVIDER}')
                self._inference_session = ort.InferenceSession(
                    str(self._model_params.path), providers=[CPU_PROVIDER])

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
