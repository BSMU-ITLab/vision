from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
import bsmu.vision_core.converters.image as image_converter

if TYPE_CHECKING:
    from pathlib import Path


class ModelParams:
    def __init__(
            self,
            path: Path,
            input_image_size: tuple = (500, 500),
            image_net_torch_preprocessing: bool = True):
        self._path = path
        self._input_image_size = input_image_size
        self._image_net_torch_preprocessing = image_net_torch_preprocessing

    @property
    def path(self) -> Path:
        return self._path

    @property
    def input_image_size(self) -> tuple:
        return self._input_image_size

    @property
    def image_net_torch_preprocessing(self) -> bool:
        return self._image_net_torch_preprocessing


def preprocessed_image(image: np.ndarray, normalize: bool = True, image_net_torch_preprocessing: bool = True) \
        -> np.ndarray:
    if normalize:
        image = image_converter.normalized(image).astype(np.float_)

    if image_net_torch_preprocessing:
        image[..., 0] = (image[..., 0] - 0.485) / 0.229
        image[..., 1] = (image[..., 1] - 0.456) / 0.224
        image[..., 2] = (image[..., 2] - 0.406) / 0.225

        # r = (image - 0.485) / 0.229
        # g = (image - 0.456) / 0.224
        # b = (image - 0.406) / 0.225

        # image = np.dstack((r, g, b)).astype(np.float32)
        # image = np.dstack((b, g, r)).astype(np.float32)

    return image


class Segmenter:
    def __init__(self, model_params: ModelParams):
        self._model_params = model_params

        self._model = None

    def segment(self, image: np.ndarray):
        import onnxruntime as ort

        # # Load the ONNX model
        # model = onnx.load("alexnet.onnx")
        # # Check that the IR is well formed
        # onnx.checker.check_model(model)

        session = ort.InferenceSession(str(self._model_params.path))


        image = cv2.resize(image, self._model_params.input_image_size, interpolation=cv2.INTER_AREA)
        input_images = [image]
        input_images = [
            preprocessed_image(input_image, normalize=True,
                               image_net_torch_preprocessing=self._model_params.image_net_torch_preprocessing)
            for input_image in input_images
        ]

        print('IIII', input_images)
        # input_images = np.stack(input_images)
        # input_images = input_images.astype(np.float32)
        # print('INPUT_IMAGES', input_images.shape, input_images.dtype)


        input = {'input_1': input_images}
        # start = int(time() * 1000)
        outputs = session.run(input_feed=input, output_names=['sigmoid'])#[0][0]

        print('Outputs:', outputs)
        for output in outputs:
            print('---------', output.shape, output.dtype)

        mask_output_batch = outputs[0]
        mask0 = mask_output_batch[0]
        print('mask0', mask0.shape, mask0.dtype, mask0.min(), mask0.max())
        print('mask0 unique', np.unique(mask0))


        # print('Outputs shape:', outputs.shape)
        # duration = int(time() * 1000) - start
        # print("MiniLM inference using onnxruntime py {} ms, score={}".format(duration, score))

        # if self._model is None:
        #     self._model = cv2.dnn.readNet(str(self._model_params.path))

        print('readNet ready')

        return mask0
