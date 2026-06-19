from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, overload

from PySide6.QtCore import Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.data.vector.shapes import NodeBasedShape, VectorNode, VectorShape
from bsmu.vision.core.handle_registry import HandleRegistry
from bsmu.vision.core.layers import Layer, RasterLayer, VectorLayer

if TYPE_CHECKING:
    from typing import Sequence
    from pathlib import Path
    import numpy.typing as npt

    from PySide6.QtCore import QObject

    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.image import Image
    from bsmu.vision.core.palette import Palette
    from bsmu.vision.core.visibility import Visibility


_L = TypeVar('_L', bound=Layer)

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

        # Handle registries for all vector shapes/nodes across all layers
        self._shape_registry = HandleRegistry[VectorShape]()
        self._node_registry = HandleRegistry[VectorNode]()

    @property
    def layers(self) -> Sequence[Layer]:
        """Read-only copy of layers. Use add_layer()/remove_layer() to modify."""
        return self._layers.copy()

    @property
    def base_layer(self) -> Layer | None:
        """Cached base layer (always layers[0] if exists, else None)."""
        return self._base_layer

    @property
    def shape_registry(self) -> HandleRegistry[VectorShape]:
        """Registry for all vector shapes. Use for undo/redo commands."""
        return self._shape_registry

    @property
    def node_registry(self) -> HandleRegistry[VectorNode]:
        return self._node_registry

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

    @overload
    def layer_by_name(self, name: str) -> Layer | None: pass

    @overload
    def layer_by_name(self, name: str, layer_type: type[_L]) -> _L | None: pass

    def layer_by_name(self, name: str, layer_type: type[Layer] | None = None) -> Layer | None:
        layer = self._name_to_layer.get(name)
        if layer_type is not None and not isinstance(layer, layer_type):
            return None
        return layer

    def add_layer(self, layer: Layer) -> None:
        if layer.name in self._name_to_layer:
            raise ValueError(f'Layer with name {layer.name} already exists in this LayeredData.')

        layer_index = len(self._layers)
        self.layer_adding.emit(layer, layer_index)

        self._layers.append(layer)
        self._name_to_layer[layer.name] = layer

        self._connect_layer_signals(layer)
        self._register_layer_shapes(layer)

        # If this is the first layer, it becomes the base
        if layer_index == 0:
            self._set_base_layer(layer)

        self.layer_added.emit(layer, layer_index)

    def add_layer_from_image(
            self,
            image: Raster | None,
            name: str = '',
            path: Path | None = None,
            visibility: Visibility | None = None
    ) -> RasterLayer:
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
            image_type: type[Image],
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

        self._unregister_layer_shapes(layer)
        self._disconnect_layer_signals(layer)

        self._layers.remove(layer)
        del self._name_to_layer[layer.name]

        # If we removed the base layer (which is always at index 0 before removal)
        if layer_index == 0:
            new_base_layer = self._layers[0] if self._layers else None
            self._set_base_layer(new_base_layer)

        self.layer_removed.emit(layer, layer_index)

    def _connect_layer_signals(self, layer: Layer) -> None:
        if isinstance(layer, VectorLayer):
            layer.shape_added.connect(self._register_shape)
            layer.shape_removed.connect(self._unregister_shape)

    def _disconnect_layer_signals(self, layer: Layer) -> None:
        if isinstance(layer, VectorLayer):
            layer.shape_added.disconnect(self._register_shape)
            layer.shape_removed.disconnect(self._unregister_shape)

    def _register_layer_shapes(self, layer: Layer) -> None:
        """Register all existing shapes in a layer."""
        if isinstance(layer, VectorLayer):
            for shape in layer.shapes:
                self._register_shape(shape)

    def _unregister_layer_shapes(self, layer: Layer) -> None:
        """Unregister all shapes from a layer."""
        if isinstance(layer, VectorLayer):
            for shape in layer.shapes:
                self._unregister_shape(shape)

    def _register_shape(self, shape: VectorShape) -> None:
        self._shape_registry.register(shape)

        if isinstance(shape, NodeBasedShape):
            shape.node_added.connect(self._register_node)
            shape.node_removed.connect(self._unregister_node)
            # Register existing nodes in this shape
            for node in shape.nodes:
                self._register_node(node)

    def _unregister_shape(self, shape: VectorShape) -> None:
        if isinstance(shape, NodeBasedShape):
            for node in shape.nodes:
                self._unregister_node(node)
            shape.node_added.disconnect(self._register_node)
            shape.node_removed.disconnect(self._unregister_node)

        handle = self._shape_registry.get_handle(shape)
        if handle is not None:
            self._shape_registry.unregister(handle)

    def _register_node(self, node: VectorNode) -> None:
        self._node_registry.register(node)

    def _unregister_node(self, node: VectorNode) -> None:
        handle = self._node_registry.get_handle(node)
        if handle is not None:
            self._node_registry.unregister(handle)

    def get_or_create_vector_layer(self, name: str, visibility: Visibility | None = None) -> VectorLayer:
        """Returns an existing VectorLayer with the given name, or creates a new one."""
        layer = self.layer_by_name(name)
        if layer is None:
            new_layer = VectorLayer(Vector(), name, visibility=visibility)
            self.add_layer(new_layer)
            return new_layer
        elif not isinstance(layer, VectorLayer):
            raise TypeError(f'Layer {name} exists but is not a VectorLayer')
        else:
            return layer

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
