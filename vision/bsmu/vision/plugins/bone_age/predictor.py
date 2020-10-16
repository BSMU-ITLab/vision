from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

import cv2
import numpy as np
import skimage.color
import skimage.io
import skimage.transform

import bsmu.vision_core.converters.image as image_converter


class DnnModelParams:
    def __init__(self,
                 path: Path,
                 image_input_layer_name: str,
                 male_input_layer_name: str,
                 age_output_layer_name: str,
                 last_conv_output_layer_name: str,
                 last_conv_pooling_output_layer_name: str,
                 input_image_size: tuple = (500, 500),
                 image_net_torch_preprocessing: bool = True,
                 age_denormalization: bool = True):
        self.path = path
        self.image_input_layer_name = image_input_layer_name
        self.male_input_layer_name = male_input_layer_name
        self.age_output_layer_name = age_output_layer_name
        self.last_conv_output_layer_name = last_conv_output_layer_name
        self.last_conv_pooling_output_layer_name = last_conv_pooling_output_layer_name
        self.input_image_size = input_image_size
        self.image_net_torch_preprocessing = image_net_torch_preprocessing
        self.age_denormalization = age_denormalization


def denormalized_age(age: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    :param age: age in range [-1, 1]
    :return: age in range [0, 240] (months)
    """
    return (age + 1) * 120


def show_image(image: np.ndarray):
    # Change channels order to OpenCV (BGR)
    cv2.imshow(f'Image', image[..., ::-1])


class Predictor:
    def __init__(self, dnn_model_params: DnnModelParams, use_augmented_image_set: bool = False):
        self._dnn_model_params = dnn_model_params
        self.use_augmented_image_set = use_augmented_image_set

        self._dnn_model = None

    def predict(self, image: FlatImage, male: bool, calculate_activation_map: bool = True) -> Tuple[float, np.ndarray]:
        """
        :return: tuple of (bone age in months, activation map)
        """
        image_path_name = image.path_name
        if self._dnn_model is None:
            self._dnn_model = cv2.dnn.readNet(str(self._dnn_model_params.path))

        image = skimage.color.rgb2gray(image.array)
        image = cv2.resize(image, self._dnn_model_params.input_image_size, interpolation=cv2.INTER_AREA)

        input_images = [image]

        if self.use_augmented_image_set:
            flipped_image = horizontal_flipped(image)
            augmented_images = [
                brightness_contrast_changed(flipped_image, alpha=0.5, beta=128),
                brightness_contrast_changed(image, alpha=1.2, beta=-50),
                cropped_resized(image, x_margin_factor=0.1, y_margin_factor=0.1),
                cropped_resized(flipped_image, x_margin_factor=0.15, y_margin_factor=0),
                cropped_resized(image, x_margin_factor=0, y_margin_factor=0.15),
                flipped_image,
            ]
            input_images.extend(augmented_images)

        input_images = [
            preprocessed_image(input_image, normalize=True,
                               image_net_torch_preprocessing=self._dnn_model_params.image_net_torch_preprocessing)
            for input_image in input_images
        ]

        input_images = np.stack(input_images)
        image_input_blob = cv2.dnn.blobFromImages(input_images)
        batch_size = len(input_images)

        self._dnn_model.setInput(image_input_blob, name=self._dnn_model_params.image_input_layer_name)

        male_input_blob = np.full(batch_size, int(male))
        self._dnn_model.setInput(male_input_blob, name=self._dnn_model_params.male_input_layer_name)

        output_blobs = self._dnn_model.forward([
            self._dnn_model_params.age_output_layer_name,
            self._dnn_model_params.last_conv_output_layer_name,
            self._dnn_model_params.last_conv_pooling_output_layer_name,
        ])

        # for out_blob in output_blobs:
        #     print(f'OUT BLOB: {out_blob.shape} {out_blob.dtype} {out_blob.min()} {out_blob.max()}')

        age_output_blob = output_blobs[0]
        if self._dnn_model_params.age_denormalization:
            age_output_blob = denormalized_age(age_output_blob)

        output_age = age_output_blob[0, 0]
        print(f'Name: {image_path_name} Age: {age_output_blob}')
        if age_output_blob.size > 1:
            print(f'Original: {output_age}, Average: {np.mean(age_output_blob)}, '
                  f'Median: {np.median(age_output_blob)}, '
                  f'Variance unbiased: {np.var(age_output_blob, ddof=1)} Variance: {np.var(age_output_blob)}')

        # Calculate activation map
        activation_map = None
        if calculate_activation_map:
            output_last_conv = output_blobs[1][0]
            output_last_conv_pooling = output_blobs[2][0]
            activation_map = calculate_cam(output_last_conv, output_last_conv_pooling)

        return output_age, activation_map

    def print_layer_names(self):
        for index, layer_name in enumerate(self._dnn_model.getLayerNames()):
            print(f'#{index} \t\t {layer_name}')


def calculate_cam(conv: np.ndarray, pooling: np.ndarray) -> np.ndarray:
    cam = np.copy(conv)
    for feature_map_index in range(cam.shape[0]):
        cam[feature_map_index, ...] *= pooling[feature_map_index]
    cam = np.mean(cam, axis=0)
    cam = image_converter.normalized(cam)
    return cam


def preprocessed_image(image: np.ndarray, normalize: bool = True, image_net_torch_preprocessing: bool = True) \
        -> np.ndarray:
    if normalize:
        image = image_converter.normalized(image)

    if image_net_torch_preprocessing:
        r = (image - 0.485) / 0.229
        g = (image - 0.456) / 0.224
        b = (image - 0.406) / 0.225

        image = np.dstack((r, g, b)).astype(np.float32)
        # image = np.dstack((b, g, r)).astype(np.float32)

    return image


def horizontal_flipped(image: np.ndarray) -> np.ndarray:
    return cv2.flip(image, 1)


def brightness_contrast_changed(image: np.ndarray, alpha: float = 1, beta: float = 0) -> np.ndarray:
    image = image_converter.normalized_uint8(image)
    return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)


def cropped_resized(image: np.ndarray, y_margin_factor=0.1, x_margin_factor=0.1) -> np.ndarray:
    y_margin = int(image.shape[0] * y_margin_factor)
    x_margin = int(image.shape[1] * x_margin_factor)
    cropped = image[y_margin: -y_margin or image.shape[0], x_margin: -x_margin or image.shape[1]]
    return cv2.resize(cropped, image.shape, interpolation=cv2.INTER_CUBIC)
