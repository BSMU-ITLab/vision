import numpy as np

from skimage.color import gray2rgb

from PySide2.QtGui import QImage


def converted_to_normalized_uint8(image):
    if image.dtype != np.uint8 or image.max() != 255:
        if image.max() != 0:
            image = image / image.max() * 255
        image = image.astype(np.uint8)
    return image


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
    # print("STRIDES", numpy_image.strides[0])
    # print(numpy_image.flags['C_CONTIGUOUS'])

    height, width, channel = numpy_image.shape
    bytes_per_line = width * channel * numpy_image.itemsize
    return QImage(numpy_image.data, width, height, bytes_per_line, image_format)


def numpy_bgra_image_to_qimage(numpy_image):
    return numpy_rgba_image_to_qimage(numpy_image).rgbSwapped()
