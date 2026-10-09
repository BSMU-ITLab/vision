from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.layers import VectorLayer
from bsmu.vision.undo import UndoCommand

if TYPE_CHECKING:
    from bsmu.vision.core.data.layered import LayeredData


logger = logging.getLogger(__name__)


class CreateVectorLayerCommand(UndoCommand):
    """Ensure a vector layer with data exists.

    Creates the layer if missing, or creates empty Vector data
    if the layer exists without data.
    """

    def __init__(
            self,
            layered_data: LayeredData,
            layer_name: str,
            text: str = 'Create Vector Layer',
            parent: UndoCommand | None = None,
    ) -> None:
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._layer_name = layer_name

        # Object created by this command.
        # At most one is set: either a layer (created from scratch)
        # or data (created for an existing layer without data).
        self._created_layer: VectorLayer | None = None
        self._created_data: Vector | None = None

    def redo(self) -> None:
        if self._created_layer is not None or self._created_data is not None:
            self._restore()
        else:
            self._create()

    def undo(self) -> None:
        if self._created_layer is not None:
            self._layered_data.remove_layer(self._created_layer)
        elif self._created_data is not None:
            layer = self._layered_data.layer_by_name(self._layer_name, VectorLayer)
            if layer is None:
                logger.debug(
                    'CreateVectorLayerCommand.undo: layer `%s` not found; skipping data removal',
                    self._layer_name)
                return
            if layer.data is not self._created_data:
                logger.debug(
                    'CreateVectorLayerCommand.undo: layer `%s` data was replaced; skipping data removal',
                    self._layer_name)
                return
            layer.data = None

    def _create(self) -> None:
        """Create the layer if missing, or create empty data if the layer has none."""
        layer = self._layered_data.layer_by_name(self._layer_name)
        if layer is None:
            self._created_layer = VectorLayer(Vector(), self._layer_name)
            self._layered_data.add_layer(self._created_layer)
        elif not isinstance(layer, VectorLayer):
            raise TypeError(f'Layer `{self._layer_name}` exists but is not a VectorLayer')
        elif layer.data is None:
            self._created_data = Vector()
            layer.data = self._created_data

    def _restore(self) -> None:
        """Re-attach the layer or data created by a previous execution."""
        if self._created_layer is not None:
            self._layered_data.add_layer(self._created_layer)
        else:
            layer = self._layered_data.layer_by_name(self._layer_name, VectorLayer)
            if layer is not None:
                layer.data = self._created_data


# class CreateLayerCommand
# class RemoveLayerCommand
# class RenameLayerCommand
