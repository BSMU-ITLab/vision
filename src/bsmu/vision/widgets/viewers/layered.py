from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Signal

from bsmu.vision.core.data.layered import LayeredData
from bsmu.vision.core.layers import RasterLayer
from bsmu.vision.widgets.actors.layer import LayerActor
from bsmu.vision.widgets.actors.registry import create_layer_actor
from bsmu.vision.widgets.viewers.graphics import GraphicsViewer

if TYPE_CHECKING:
    from pathlib import Path
    import numpy.typing as npt

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QGraphicsItem, QWidget

    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.layers import Layer
    from bsmu.vision.core.palette import Palette
    from bsmu.vision.core.visibility import Visibility
    from bsmu.vision.widgets.viewers.graphics import ImageViewerSettings


class LayeredDataViewer(GraphicsViewer[LayeredData]):
    layer_actor_about_to_add = Signal(LayerActor, int)
    layer_actor_added = Signal(LayerActor, int)
    layer_actor_about_to_remove = Signal(LayerActor, int)
    layer_actor_removed = Signal(LayerActor, int)

    active_layer_view_changed = Signal(LayerActor, LayerActor)
    data_name_changed = Signal(str)

    def __init__(
            self,
            data: LayeredData | None = None,
            settings: ImageViewerSettings | None = None,
            parent: QWidget | None = None,
    ):
        self._layer_to_actor: dict[Layer, LayerActor] = {}

        self._active_layer_actor = None

        super().__init__(data, settings, parent)

    @property
    def layers(self) -> list[Layer]:
        return self.data.layers

    @property
    def layer_actors(self) -> list[LayerActor]:
        return list(self._layer_to_actor.values())

    @property
    def active_layer_view(self) -> LayerActor | None:
        return self._active_layer_actor

    @active_layer_view.setter
    def active_layer_view(self, value: LayerActor | None):
        if self._active_layer_actor != value:
            prev_active_layer_actor = self._active_layer_actor
            self._active_layer_actor = value
            self.active_layer_view_changed.emit(prev_active_layer_actor, self._active_layer_actor)

    @property
    def active_layer(self) -> Layer | None:
        return None if self._active_layer_actor is None else self._active_layer_actor.layer

    def layer_by_name(self, name: str) -> Layer | None:
        return self.data.layer_by_name(name)

    def actor_by_layer(self, layer: Layer) -> LayerActor | None:
        return self._layer_to_actor.get(layer)

    def layer_view_by_model(self, layer: Layer) -> LayerActor | None:
        warnings.warn('`layer_view_by_model` is deprecated; use `actor_by_layer` instead.',
                      DeprecationWarning, stacklevel=2)
        return self.actor_by_layer(layer)

    def add_layer(self, layer: Layer) -> None:
        self.data.add_layer(layer)

    def add_layer_from_image(self, raster: Raster, name: str = '') -> Layer:
        layer = RasterLayer(raster, name)
        self.add_layer(layer)
        return layer

    def add_layer_or_modify_image(
            self, name: str, raster: Raster, path: Path = None, visibility: Visibility = None) -> Layer:
        return self.data.add_layer_or_modify_image(name, raster, path, visibility)

    def add_layer_or_modify_pixels(
            self,
            name: str,
            pixels: npt.NDArray,
            raster_type: type[Raster],
            palette: Palette | None = None,
            path: Path | None = None,
            visibility: Visibility | None = None,
    ) -> Layer:
        return self.data.add_layer_or_modify_pixels(name, pixels, raster_type, palette, path, visibility)

    def remove_layer(self, layer: Layer) -> None:
        self.data.remove_layer(layer)

    def contains_layer(self, name: str) -> bool:
        return self.data.contains_layer(name)

    def map_viewport_to_pixel_coords(self, viewport_pos: QPoint, layer: RasterLayer) -> np.ndarray:
        """Map viewport position to continuous pixel coordinates"""
        layer_actor = self.actor_by_layer(layer)
        layer_actor_pos = self.map_viewport_to_actor(viewport_pos, layer_actor)
        return layer.data.map_spatial_to_pixel_coords(
            np.array([layer_actor_pos.y(), layer_actor_pos.x()])) * layer.data.spatial.spacing

    def map_viewport_to_pixel_indices(self, viewport_pos: QPoint, layer: RasterLayer) -> np.ndarray:
        """Map viewport position to discrete pixel array indices"""
        return self.map_viewport_to_pixel_coords(viewport_pos, layer).round().astype(np.int_)

    def _data_about_to_change(self, new_data: LayeredData | None):
        if self.data is None:
            return

        self.data.layer_added.disconnect(self._on_layer_added)
        self.data.layer_removing.disconnect(self._on_layer_about_to_remove)
        self.data.display_name_changed.disconnect(self.data_name_changed)

        for layer_index, layer in enumerate(self.layers):
            self._on_layer_about_to_remove(layer, layer_index)

    def _data_changed(self):
        if self.data is None:
            return

        self.data.layer_added.connect(self._on_layer_added)
        self.data.layer_removing.connect(self._on_layer_about_to_remove)
        self.data.display_name_changed.connect(self.data_name_changed)

        for layer_index, layer in enumerate(self.layers):
            self._on_layer_added(layer, layer_index)

        self.data_name_changed.emit(self.data.display_name)

    def _on_layer_added(self, layer: Layer, layer_index: int):
        actor = create_layer_actor(layer)
        if actor is None:
            return

        self.layer_actor_about_to_add.emit(actor, layer_index)

        self._layer_to_actor[layer] = actor
        self.add_actor(actor)

        if len(self._layer_to_actor) == 1:  # If was added the first layer actor
            self.active_layer_view = actor

        self.layer_actor_added.emit(actor, layer_index)

    def _on_layer_about_to_remove(self, layer: Layer, layer_index: int):
        actor = self._layer_to_actor.get(layer)
        if actor is None:
            return

        self.layer_actor_about_to_remove.emit(actor, layer_index)

        self.remove_actor(actor)
        del self._layer_to_actor[layer]

        if len(self._layer_to_actor) == 0:
            self.active_layer_view = None

        self.layer_actor_removed.emit(actor, layer_index)
        actor.deleteLater()
