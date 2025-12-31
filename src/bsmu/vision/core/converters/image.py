import cv2 as cv
import numpy as np
from PySide6.QtGui import QImage
from skimage.color import gray2rgba


def normalized(array: np.ndarray, min_range: float = 0, max_range: float = 1):
    array_min = array.min()
    normalized_between_zero_one = (array - array_min) / ((array.max() - array_min) or 1)
    return normalized_between_zero_one * (max_range - min_range) + min_range


def normalized_uint8(array: np.ndarray):
    return normalized(array, 0, 255).astype(np.uint8)


def converted_to_rgba(image: np.ndarray):
    if image.ndim == 2:  # one channel (grayscale image)
        image = gray2rgba(image)
    elif image.ndim == 3 and image.shape[2] == 3:  # 3-channel image
        # Add alpha-channel
        image = cv.cvtColor(image, cv.COLOR_RGB2RGBA)
    return image


def numpy_array_to_qimage(
        numpy_array: np.ndarray, image_format: QImage.Format = QImage.Format.Format_RGBA8888_Premultiplied):
    """
    Do not delete `numpy_array` or it's data, because QImage uses it without copying,
    and QImage will crash if it's data buffer will be deleted
    """
    assert numpy_array.flags['C_CONTIGUOUS'], 'Numpy array have to be C-contiguous'
    height, width, *channel_count = numpy_array.shape
    # If shape has no channels use 1 as channel count
    channel_count = (channel_count and channel_count[0]) or 1
    bytes_per_line = width * channel_count * numpy_array.itemsize
    return QImage(numpy_array.data, width, height, bytes_per_line, image_format)


def numpy_bgra_image_to_qimage(numpy_image):
    return numpy_array_to_qimage(numpy_image).rgbSwapped()
