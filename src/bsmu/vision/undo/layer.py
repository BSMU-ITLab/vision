from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.layers import VectorLayer
from bsmu.vision.undo import UndoCommand

if TYPE_CHECKING:
    from bsmu.vision.core.data.layered import LayeredData


class CreateVectorLayerCommand(UndoCommand):
    def __init__(
        self,
        layered_data: LayeredData,
        layer_name: str,
        text: str = 'Create Vector Layer',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._layer_name = layer_name

        self._created_layer: VectorLayer | None = None

    def redo(self):
        if self._created_layer is not None:
            self._layered_data.add_layer(self._created_layer)
            return

        layer = self._layered_data.layer_by_name(self._layer_name)
        if layer is None:
            self._created_layer = VectorLayer(Vector(), self._layer_name)
            self._layered_data.add_layer(self._created_layer)
        elif not isinstance(layer, VectorLayer):
            raise TypeError(f'Layer {self._layer_name} exists but is not a VectorLayer')

    def undo(self):
        if self._created_layer is not None:
            self._layered_data.remove_layer(self._created_layer)


# class CreateLayerCommand
# class RemoveLayerCommand
# class RenameLayerCommand
