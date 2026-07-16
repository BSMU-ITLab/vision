from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import ClassVar

import cv2 as cv
import numpy as np
import numpy.typing as npt
import onnxruntime as ort
from PySide6.QtCore import QObject, QThreadPool, QTimer

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.core.config import Config, IntSequenceOrAll, FloatSequence, StrSequence
from bsmu.vision.dnn.config import OnnxConfig, CPU_PROVIDER


@dataclass
class ModelConfig(Config):
    path: Path
    output_object_name: str = 'Object'
    output_object_short_name: str = 'Obj'
    preload: bool = False
    batch_size: int = 1

    def preprocessed_input(self, src: np.ndarray) -> np.ndarray:
        pass

    def preprocessed_input_batch(self, src_batch: Sequence[np.ndarray]) -> Sequence[np.ndarray]:
        preprocessed_batch = []
        for src in src_batch:
            src = self.preprocessed_input(src)
            preprocessed_batch.append(src)
        return preprocessed_batch


@dataclass
class ImageModelConfig(ModelConfig):
    input_size: Sequence[int] = (256, 256, 3)
    channels_axis: int = 2
    channels_order: str = 'rgb'
    normalize: bool = True
    preprocessing_mode: str = 'image-net-torch'

    # Data type the image is converted to at the start of preprocessing.
    # Use np.uint8 if the model expects raw [0..255] inputs and handles normalization internally
    # (can slightly improve GPU inference speed). Otherwise, np.float32 is recommended.
    input_type: npt.DTypeLike = np.float32

    # Which output channels to return: 'all' (default), a single index, or a list of indices.
    output_channels: IntSequenceOrAll = field(default_factory=IntSequenceOrAll)
    # Class name(s) corresponding to output_channels.
    output_class_names: StrSequence = field(default_factory=lambda: StrSequence('foreground'))
    # One threshold per output class. If single value given, auto-repeats for all classes.
    mask_binarization_thresholds: FloatSequence = field(default_factory=lambda: FloatSequence(0.5))

    _input_image_size_cache: tuple = field(default=None, init=False, repr=False, compare=False)

    IMAGENET_MEAN: ClassVar[np.ndarray] = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    IMAGENET_STD: ClassVar[np.ndarray] = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    # The following constants are used for minor optimization
    IMAGENET_MEAN_x_255: ClassVar[np.ndarray] = IMAGENET_MEAN * 255
    IMAGENET_STD_x_255: ClassVar[np.ndarray] = IMAGENET_STD * 255

    def __post_init__(self):
        n_cls = len(self.output_class_names)

        if not self.output_channels.is_all:
            n_ch = len(self.output_channels)
            if n_ch != n_cls:
                raise ValueError(
                    f'`output_channels` count ({n_ch}) != `output_class_names` count ({n_cls})'
                )

        n_thr = len(self.mask_binarization_thresholds)
        if n_thr == 1 and n_cls > 1:
            # Auto-repeat single threshold for all classes
            self.mask_binarization_thresholds = FloatSequence(
                [self.mask_binarization_thresholds[0]] * n_cls
            )
        elif n_thr != n_cls:
            raise ValueError(
                f'`mask_binarization_thresholds` count ({n_thr}) != `output_class_names` count ({n_cls})'
            )

    @property
    def is_multiclass_output(self) -> bool:
        """True if the model returns multiple class mask."""
        return len(self.output_class_names) > 1

    def copy_but_change_name(self, new_name: str) -> ImageModelConfig:
        return replace(self, path=self.path.parent / new_name)

    @property
    def input_image_size(self) -> tuple[int, ...]:
        if self._input_image_size_cache is None:
            input_size_list = list(self.input_size)
            del input_size_list[self.channels_axis]
            self._input_image_size_cache = tuple(input_size_list)
        return self._input_image_size_cache

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

        image = image.astype(self.input_type, copy=False)
        if image.shape[:DEFAULT_CHANNELS_AXIS] != self.input_image_size:
            image = cv.resize(image, self.input_image_size, interpolation=cv.INTER_AREA)

        if self.normalize:
            image = image_converter.normalized(image)

        if self.preprocessing_mode == 'image-net-torch':
            # Standardize the image using ImageNet mean and standard deviation
            if self.normalize:
                image -= self.IMAGENET_MEAN
                image /= self.IMAGENET_STD
            else:
                image -= self.IMAGENET_MEAN_x_255
                image /= self.IMAGENET_STD_x_255

                # The above code is a slightly optimized version of:
                # image /= 255
                # image -= self.IMAGENET_MEAN
                # image /= self.IMAGENET_STD
        elif self.preprocessing_mode == 'image-net-tf':
            if not self.normalize:
                image /= 255
            # Scale pixels between -1 and 1, sample-wise
            image *= 2
            image -= 1

        if self.channels_order == 'bgr':
            image = image[..., ::-1]

        image = np.moveaxis(image, DEFAULT_CHANNELS_AXIS, self.channels_axis)

        if image.dtype != self.input_type:
            logging.warning(
                f'Preprocessed image dtype is {image.dtype}, but expected {self.input_type}. '
                f'The dtype may have been promoted during preprocessing steps.'
            )
        return image


class Inferencer(QObject):
    def __init__(self, model_config: ModelConfig, parent: QObject = None):
        super().__init__(parent)

        self._model_config = model_config

        self._inference_session: ort.InferenceSession | None = None
        self._inference_session_being_created: bool = False

        if self._model_config.preload:
            # Use zero timer to start method whenever there are no pending events (see QCoreApplication::exec doc)
            QTimer.singleShot(0, self._preload_model)

    @property
    def model_config(self) -> ModelConfig:
        return self._model_config

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
                    str(self._model_config.path), providers=providers)
            except Exception as e:
                # Current onnxruntime version throws an error instead of warning,
                # when CUDA provider failed, and does not try other providers (e.g. CPU provider), so do it by self
                logging.warning(f'Cannot create an inference session with {providers} providers. '
                                f'The error: {e}'
                                f'Trying to create the inference session using only {CPU_PROVIDER}')
                self._inference_session = ort.InferenceSession(
                    str(self._model_config.path), providers=[CPU_PROVIDER])

            used_provider = self._inference_session.get_providers()[0]
            logging.info(f'Using ONNX `{used_provider}`')

            self._inference_session_being_created = False
