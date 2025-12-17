from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.layers import Layer, RasterLayer

if TYPE_CHECKING:
    from typing import Type
    from pathlib import Path
    import numpy.typing as npt

    from PySide6.QtCore import QObject

    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.image import Image
    from bsmu.vision.core.palette import Palette
    from bsmu.vision.core.visibility import Visibility


class LayeredData(Data):
    layer_adding = Signal(Layer, int)
    layer_added = Signal(Layer, int)
    layer_removing = Signal(Layer, int)
    layer_removed = Signal(Layer, int)

    def __init__(self, path: Path = None, parent: QObject | None = None):
        super().__init__(path, parent)

        self._layers: list[Layer] = []
        self._layer_by_name = {}

    @property
    def layers(self) -> list[Layer]:
        return self._layers

    def layer_by_name(self, name: str) -> Layer | None:
        return self._layer_by_name.get(name)

    def add_layer(self, layer: Layer):
        layer_index = len(self._layers)
        self.layer_adding.emit(layer, layer_index)
        self._layers.append(layer)
        self._layer_by_name[layer.name] = layer
        self.layer_added.emit(layer, layer_index)

    def add_layer_from_image(
            self, image: Raster | None, name: str = '', path: Path = None, visibility: Visibility = None) -> RasterLayer:
        image_layer = RasterLayer(image, name, path, visibility)
        self.add_layer(image_layer)
        return image_layer

    def add_layer_or_modify_image(
            self, name: str, image: Raster, path: Path = None, visibility: Visibility = None) -> RasterLayer:
        layer = self.layer_by_name(name)
        if layer is None:
            layer = self.add_layer_from_image(image, name, path, visibility)
        else:
            layer.image = image
        return layer

    def add_layer_or_modify_pixels(
            self,
            name: str,
            pixels: npt.NDArray,
            image_type: Type[Image],
            palette: Palette = None,
            path: Path = None,
            visibility: Visibility = None,
    ) -> RasterLayer:
        layer = self.layer_by_name(name)
        if layer is None:
            layer = self.add_layer_from_image(image_type(pixels, palette), name, path, visibility)
        elif layer.image is None:
            layer.image = image_type(pixels, palette)
        else:
            layer.image.pixels = pixels
            layer.image.emit_pixels_modified()
        return layer

    def remove_layer(self, layer: Layer):
        layer_index = self._layers.index(layer)
        self.layer_removing.emit(layer, layer_index)
        self._layers.remove(layer)
        del self._layer_by_name[layer.name]
        self.layer_removed.emit(layer, layer_index)

    def contains_layer(self, name: str) -> bool:
        return self.layer_by_name(name) is not None

    def layer_image(self, layer_name: str) -> Raster | None:
        return (layer := self.layer_by_name(layer_name)) and layer.image

    def print_layers(self):
        for index, layer in enumerate(self.layers):
            print(f'Layer {index}: {layer.name}')


'''
class LayerImageDependencyController(QObject):
    def __init__(self, master_layer: ImageLayer, slave_layers: List[ImageLayer]):
        super().__init__()

        self.master_layer = master_layer
        self.slave_layers = slave_layers

        self.master_layer.data_changed(self._update_slave_layers)

    def is_corresponding_layer_image(self, slave_layer: ImageLayer):
        return self.master_layer.path /
        return file_path = layer.path
        ...

    def corresponding_layer_image(self, slave_layer: ImageLayer):
        file_path = layer.path / next_file_name
        layer.image = self.file_reading_manager.read_file(file_path, palette=layer.palette)

    def _update_slave_layer_image(self, slave_layer: ImageLayer):


    def _update_slave_layers(self):
        for slave_layer in self.slave_layers:
            self._update_slave_layer_image(slave_layer)
'''
