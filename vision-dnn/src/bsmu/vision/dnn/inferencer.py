from __future__ import annotations

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
    from typing import Callable, Tuple
    from pathlib import Path
    from concurrent.futures import Future


class ModelParams:
    def __init__(
            self,
            path: Path,
            input_size: tuple = (256, 256, 3),
            preprocessing_mode: str = 'image-net-torch',
            preload_model: bool = False,
    ):
        self._path = path
        self._input_size = input_size
        self._preprocessing_mode = preprocessing_mode
        self._preload_model = preload_model

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

    @property
    def preload_model(self) -> bool:
        return self._preload_model


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
