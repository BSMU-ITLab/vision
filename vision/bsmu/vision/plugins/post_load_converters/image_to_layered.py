from __future__ import annotations

from bsmu.vision.plugins.post_load_converters.base import PostLoadConverterPlugin, PostLoadConverter
from bsmu.vision.core.data import Data
from bsmu.vision.core.image.base import FlatImage, VolumeImage
from bsmu.vision.core.image.layered import LayeredImage


class ImageToLayeredImagePostLoadConverterPlugin(PostLoadConverterPlugin):
    def __init__(self):
        super().__init__(ImageToLayeredImagePostLoadConverter)


class ImageToLayeredImagePostLoadConverter(PostLoadConverter):
    _DATA_TYPES = (FlatImage, VolumeImage)

    def _convert_data(self, data: Data) -> Data:
        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)
        return layered_image
