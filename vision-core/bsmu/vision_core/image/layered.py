from __future__ import annotations

from PySide2.QtCore import QObject, Signal

from bsmu.vision_core.data import Data
from bsmu.vision_core.image.base import Image


class ImageLayer(QObject):
    max_id = 0

    image_updated = Signal(Image)

    def __init__(self, image: Image, name: str = ''):
        super().__init__()
        self.id = ImageLayer.max_id
        ImageLayer.max_id += 1

        self._image = None
        self.image = image  # if image is not None else Image()
        self.name = name if name else 'Layer ' + str(self.id)

    @property
    def image_path(self) -> Path:
        return self.image.path

    @property
    def image_palette(self) -> Palette:
        return self.image.palette

    @property
    def image_pixels(self) -> np.ndarray:
        return self.image.array

    @property
    def image_path_name(self) -> str:
        return self.image_path.name

    @property  # TODO: this is slow. If we need only setter, there are alternatives without getter
    def image(self) -> Image:
        return self._image

    @image.setter
    def image(self, value: Image):
        if self._image != value:
            self._image = value
            self._on_image_updated()
            # self._image.updated.connect(self._on_image_updated)
            self._image.pixels_modified.connect(self._on_image_updated)

    def _on_image_updated(self):
        print('_ImageItemLayer _on_image_updated (image array updated or layer image changed)')
        self._displayed_image_cache = None
        self.image_updated.emit(self.image)


class LayeredImage(Data):
    def __init__(self, path: Path = None):
        super().__init__(path)

        self._layers = []
        self._names_layers = {}

    @property
    def layers(self):
        return self._layers

    def layer(self, name: str) -> ImageLayer:
        return self._names_layers.get(name)

    def add_layer(self, layer: ImageLayer):
        self._layers.append(layer)
        self._names_layers[layer.name] = layer

    def add_layer_from_image(self, image: Image, name: str = '') -> ImageLayer:
        image_layer = ImageLayer(image, name)
        self.add_layer(image_layer)
        return image_layer
