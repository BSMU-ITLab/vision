from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort
from PySide6.QtCore import QObject, QThreadPool, QTimer

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.dnn.config import OnnxConfig, CPU_PROVIDER

if TYPE_CHECKING:
    from typing import Sequence
    from pathlib import Path


@dataclass
class ModelParams:
    path: Path
    output_object_name: str = 'Object'
    output_object_short_name: str = 'Obj'
    preload: bool = False

    @classmethod
    def from_config(cls, config_data: dict, model_dir: Path) -> ModelParams:
        field_names = {field.name for field in fields(cls)}
        SENTINEL = object()
        field_name_to_config_value = \
            {field_name: config_value for field_name in field_names
             if (config_value := config_data.get(field_name, SENTINEL)) != SENTINEL}
        return cls(path=model_dir / config_data['name'], **field_name_to_config_value)

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
    input_size: Sequence = (256, 256, 3)
    channels_axis: int = 2
    channels_order: str = 'rgb'
    normalize: bool = True
    preprocessing_mode: str = 'image-net-torch'
    mask_binarization_threshold: float = 0.5

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
            image = image.astype(np.float64)
            image = cv.resize(image, self.input_image_size, interpolation=cv.INTER_AREA)

        if self.normalize:
            image = image_converter.normalized(image).astype(np.float64)

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


class Inferencer(QObject):
    def __init__(self, model_params: ModelParams, parent: QObject = None):
        super().__init__(parent)

        self._model_params = model_params

        self._inference_session: ort.InferenceSession | None = None
        self._inference_session_being_created: bool = False

        if self._model_params.preload:
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

            used_provider = self._inference_session.get_providers()[0]
            logging.info(f'Using ONNX `{used_provider}`')

            self._inference_session_being_created = False
