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

    display_name_changed = Signal(str)

    def __init__(self, path: Path = None, parent: QObject | None = None):
        super().__init__(path, parent)

        self._layers: list[Layer] = []
        self._name_to_layer = {}
        self._base_layer: Layer | None = None

    @property
    def layers(self) -> list[Layer]:
        return self._layers

    @property
    def base_layer(self) -> Layer | None:
        """Cached base layer (always layers[0] if exists, else None)."""
        return self._base_layer

    @property
    def display_name(self) -> str:
        if self.path is None:
            name = 'Untitled Project'
        else:
            name = f'{self.path.name}'

        if self._base_layer is not None and self._base_layer.data_path_name:
            name += f' / {self._base_layer.data_path_name}'
        return name

    def _path_changed(self):
        self._emit_display_name_changed()

    def _on_base_data_path_changed(self, path: Path | None):
        self._emit_display_name_changed()

    def _emit_display_name_changed(self):
        self.display_name_changed.emit(self.display_name)

    def layer_by_name(self, name: str) -> Layer | None:
        return self._name_to_layer.get(name)

    def add_layer(self, layer: Layer) -> None:
        layer_index = len(self._layers)
        self.layer_adding.emit(layer, layer_index)
        self._layers.append(layer)
        self._name_to_layer[layer.name] = layer
        self.layer_added.emit(layer, layer_index)

        # If this is the first layer, it becomes the base
        if layer_index == 0:
            self._set_base_layer(layer)

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

    def remove_layer(self, layer: Layer) -> None:
        layer_index = self._layers.index(layer)
        self.layer_removing.emit(layer, layer_index)
        self._layers.remove(layer)
        del self._name_to_layer[layer.name]
        self.layer_removed.emit(layer, layer_index)

        # If we removed the base layer (which is always at index 0 before removal)
        if layer_index == 0:
            new_base_layer = self._layers[0] if self._layers else None
            self._set_base_layer(new_base_layer)

    def _set_base_layer(self, layer: Layer | None) -> None:
        if self._base_layer == layer:
            return

        if self._base_layer is not None:
            self._base_layer.data_path_changed.disconnect(self._on_base_data_path_changed)

        old_display_name = self.display_name
        self._base_layer = layer

        if self._base_layer is not None:
            self._base_layer.data_path_changed.connect(self._on_base_data_path_changed)

        new_display_name = self.display_name
        if old_display_name != new_display_name:
            self._emit_display_name_changed()

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
