from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
import skimage.color
import skimage.io
import skimage.transform


class DnnModelParams:
    def __init__(self, input_image_size: tuple = (500, 500), image_net_torch_preprocessing: bool = True,
                 age_denormalization: bool = True):
        self.input_image_size = input_image_size
        self.image_net_torch_preprocessing = image_net_torch_preprocessing
        self.age_denormalization = age_denormalization


def denormalized_age(age: float) -> float:
    """
    :param age: age in range [-1, 1]
    :return: age in range [0, 240] (months)
    """
    return (age + 1) * 120


class Predictor:
    def __init__(self, dnn_model_path: Path, dnn_model_params: DnnModelParams = DnnModelParams()):

        self._dnn_model_path = dnn_model_path
        self._dnn_model_params = dnn_model_params

        self._dnn_model = None

    def predict(self, image: FlatImage, male: bool, calculate_activation_map: bool = True) -> Tuple[float, np.ndarray]:
        """
        :return: bone age in months
        """
        if self._dnn_model is None:
            self._dnn_model = cv2.dnn.readNet(str(self._dnn_model_path))

            for index, layer_name in enumerate(self._dnn_model.getLayerNames()):
                print(f'#{index} \t\t {layer_name}')

        print(f'FLAT {image.array.shape} {image.array.dtype} {image.array.min()} {image.array.max()}')

        '''
        image2 = cv2.imread(r'D:\Temp\TempBoneAgeModels\Avgust\m_roman.jpg', cv2.IMREAD_GRAYSCALE)
###        image = skimage.transform.resize(image, (500, 500), order=3, anti_aliasing=True)
        print(f'IMAGE2: {image2.shape} {image2.dtype} {image2.min()} {image2.max()}')

        image = skimage.io.imread(r'D:\Temp\TempBoneAgeModels\Avgust\m_roman.jpg', as_gray=True)
        image = (image * 255).astype(np.uint8)
        print(f'IMAGE1: {image.shape} {image.dtype} {image.min()} {image.max()}')
        print(f'EQQQQ  {(image2 == image).all()}')
        dif = image2 - image
        print(f'SUM {np.sum(dif)}')
        print(f'dif: {dif.shape} {dif.dtype} {dif.min()} {dif.max()}')
        print(np.unique(dif))
        # image = skimage.transform.resize(
        #     image_src, model_trainer.model_input_image_size, anti_aliasing=True, order=1).astype(np.float32)
        image = image.astype(np.float32)
        '''

        image = skimage.color.rgb2gray(image.array)
        image = cv2.resize(image, (500, 500), interpolation=cv2.INTER_AREA)


        print(f'IMAGE: {image.shape} {image.dtype} {image.min()} {image.max()}')


        if self._dnn_model_params.image_net_torch_preprocessing:

            r = (image - 0.485) / 0.229
            g = (image - 0.456) / 0.224
            b = (image - 0.406) / 0.225

            image = np.dstack((r, g, b)).astype(np.float32)
            # image = np.dstack((b, g, r)).astype(np.float32)

        print(f'IMAGE PREPROCESSED: {image.shape} {image.dtype} {image.min()} {image.max()}')
        input_blob = cv2.dnn.blobFromImage(image)#, size=(500, 500))
        print(f'IMAGE BLOB: {type(input_blob)} {input_blob.shape} {input_blob.dtype}')
        self._dnn_model.setInput(input_blob, name='input_1')

        # input_male_blob = np.zeros(shape=(1, 1))    #   array([0, 0])
        input_male_blob = np.array([int(male)])
        #input_male_blob = cv2.dnn.blobFromImage(input_male_blob)
        self._dnn_model.setInput(input_male_blob, name='input_male')

        # output_blob = self._dnn_model.forward()
        OUTPUT_AGE_LAYER_NAME = 'output_age/MatMul'
        OUTPUT_LAST_CONV_LAYER_NAME = 'relu/Relu'
        OUTPUT_LAST_CONV_POOLING_LAYER_NAME = 'encoder_pooling/Mean/flatten'
        output_blobs = self._dnn_model.forward([OUTPUT_AGE_LAYER_NAME, OUTPUT_LAST_CONV_LAYER_NAME, OUTPUT_LAST_CONV_POOLING_LAYER_NAME])

        # inp_test_blod = np.zeros(shape=(1664,))
        # self._dnn_model.setInput(inp_test_blod, name='encoder_pooling/Mean/flatten')

        for out_blob in output_blobs:
            print(f'OUT BLOB: {out_blob.shape} {out_blob.dtype} {out_blob.min()} {out_blob.max()}')

        output_age_blob = output_blobs[0]
        output_age = output_age_blob[0, 0]
        print(f'=== {output_age}')
        if self._dnn_model_params.age_denormalization:
            output_age = denormalized_age(output_age)

        # Calculate activation map
        activation_map = None
        if calculate_activation_map:
            output_last_conv = output_blobs[1][0]
            output_last_conv_pooling = output_blobs[2][0]
            print(output_last_conv.shape, output_last_conv_pooling.shape)
            activation_map = calculate_cam(output_last_conv, output_last_conv_pooling)

        return output_age, activation_map


def calculate_cam(conv, pooling):
    cam = np.copy(conv)
    for feature_map_index in range(cam.shape[0]):
        cam[feature_map_index, ...] *= pooling[feature_map_index]
    cam = np.mean(cam, axis=0)
    cam = normalized_image(cam)
    return cam


def normalized_image(image):
    """
    :param image: two- or three-dimensional image
    :return: normalized to [0, 1] image
    """
    image_min = image.min()
    if image_min != 0:
        image = image - image_min
    image_max = image.max()
    if image_max != 0 and image_max != 1:
        image = image / image_max
    return image
