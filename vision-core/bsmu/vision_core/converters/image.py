import numpy as np
from PySide2.QtGui import QImage
from skimage.color import gray2rgb


def normalized(array: np.ndarray, min_range: float = 0, max_range: float = 1):
    array_min = array.min()
    normalized_between_zero_one = (array - array_min) / ((array.max() - array_min) or 1)
    return normalized_between_zero_one * (max_range - min_range) + min_range


def normalized_uint8(array: np.ndarray):
    return normalized(array, 0, 255).astype(np.uint8)


def converted_to_rgba(image):
    if image.ndim == 2:  # one channel (grayscale image)
        image = gray2rgb(image, True)
    elif image.ndim == 3 and image.shape[2] == 3:  # 3-channel image
        # Add alpha-channel
        image = np.dstack((image, np.full(image.shape[:2], 255, np.uint8)))
    return image


# Do not delete |numpy_image| or it's data, because QImage uses it without copying,
# and QImage will crash if it's data buffer will be deleted
def numpy_rgba_image_to_qimage(numpy_image, image_format: QImage.Format = QImage.Format_RGBA8888_Premultiplied):
    # print('STRIDES', numpy_image.strides[0])
    # print(numpy_image.flags)
    assert numpy_image.flags['C_CONTIGUOUS'], 'Numpy array have to be C-contiguous'
    height, width, channel = numpy_image.shape
    bytes_per_line = width * channel * numpy_image.itemsize
    return QImage(numpy_image.data, width, height, bytes_per_line, image_format)


def numpy_bgra_image_to_qimage(numpy_image):
    return numpy_rgba_image_to_qimage(numpy_image).rgbSwapped()
