from __future__ import annotations

from typing import List, Optional

from PySide2.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.image.base import Image


class ImageLayer(QObject):
    max_id = 0

    image_updated = Signal(Image)
    image_pixels_modified = Signal()

    def __init__(self, image: Image | None = None, name: str = ''):
        super().__init__()
        self.id = ImageLayer.max_id
        ImageLayer.max_id += 1

        self.path = None
        self.palette = None

        self._image = None
        self.image = image  # if image is not None else Image()
        self.name = name if name else 'Layer ' + str(self.id)

    @property
    def image_path(self) -> Optional[Path]:
        return self.image.path if self.image is not None else None

    @property
    def image_palette(self) -> Palette:
        return self.image.palette

    @property
    def image_pixels(self) -> np.ndarray:
        return self.image.array

    @property
    def image_path_name(self) -> str:
        return self.image_path.name if self.image_path is not None else ''

    @property  # TODO: this is slow. If we need only setter, there are alternatives without getter
    def image(self) -> Image:
        return self._image

    @image.setter
    def image(self, value: Image):
        if self._image != value:
            self._image = value
            self._on_image_updated()
            if self._image is not None:
                if self._image.path is not None:
                    self.path = self._image.path.parent
                self.palette = self._image.palette
                self._image.pixels_modified.connect(self.image_pixels_modified)

    def _on_image_updated(self):
        self.image_updated.emit(self.image)


class LayeredImage(Data):
    layer_adding = Signal(ImageLayer)
    layer_added = Signal(ImageLayer)
    layer_removed = Signal(ImageLayer)

    def __init__(self, path: Path = None):
        super().__init__(path)

        self._layers = []
        self._names_layers = {}

    @property
    def layers(self) -> List[ImageLayer]:
        return self._layers

    def layer_by_name(self, name: str) -> ImageLayer:
        return self._names_layers.get(name)

    def add_layer(self, layer: ImageLayer):
        self.layer_adding.emit(layer)
        self._layers.append(layer)
        self._names_layers[layer.name] = layer
        self.layer_added.emit(layer)

    def add_layer_from_image(self, image: Optional[Image], name: str = '') -> ImageLayer:
        image_layer = ImageLayer(image, name)
        self.add_layer(image_layer)
        return image_layer

    def print_layers(self):
        for index, layer in enumerate(self.layers):
            print(f'Layer {index}: {layer.name}')

'''
class LayerImageDependencyController(QObject):
    def __init__(self, master_layer: ImageLayer, slave_layers: List[ImageLayer]):
        super().__init__()

        self.master_layer = master_layer
        self.slave_layers = slave_layers

        self.master_layer.image_updated(self._update_slave_layers)

    def is_corresponding_layer_image(self, slave_layer: ImageLayer):
        return self.master_layer.path /
        return file_path = layer.path
        ...

    def corresponding_layer_image(self, slave_layer: ImageLayer):
        file_path = layer.path / next_file_name
        layer.image = self.file_loading_manager.load_file(file_path, palette=layer.palette)

    def _update_slave_layer_image(self, slave_layer: ImageLayer):


    def _update_slave_layers(self):
        for slave_layer in self.slave_layers:
            self._update_slave_layer_image(slave_layer)
'''