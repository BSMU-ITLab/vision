from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from bsmu.vision.core.data.layered import LayeredData
from bsmu.vision.core.layers import RasterLayer
from bsmu.vision.widgets.actors.layer import LayerActor
from bsmu.vision.widgets.actors.registry import create_layer_actor
from bsmu.vision.widgets.viewers.graphics import GraphicsViewer

if TYPE_CHECKING:
    from pathlib import Path
    import numpy.typing as npt

    from PySide6.QtWidgets import QGraphicsItem, QWidget

    from bsmu.vision.core.data.raster import Raster
    from bsmu.vision.core.layers import Layer
    from bsmu.vision.core.palette import Palette
    from bsmu.vision.core.visibility import Visibility
    from bsmu.vision.widgets.viewers.graphics import ImageViewerSettings


class LayeredDataViewer(GraphicsViewer[LayeredData]):
    layer_actor_about_to_add = Signal(LayerActor)
    layer_actor_added = Signal(LayerActor)
    layer_actor_about_to_remove = Signal(LayerActor)
    layer_actor_removed = Signal(LayerActor)

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

    def _create_main_graphics_object(self) -> QGraphicsItem:  # TODO: can we remove this method?
        return None

    def _data_about_to_change(self, new_data: LayeredData | None):
        if self.data is None:
            return

        self.data.layer_added.disconnect(self._on_layer_added)
        self.data.layer_removed.disconnect(self._on_layer_removed)
        self.data.display_name_changed.disconnect(self.data_name_changed)

        for layer in self.layers:
            self._on_layer_removed(layer)

    def _data_changed(self):
        if self.data is None:
            return

        self.data.layer_added.connect(self._on_layer_added)
        self.data.layer_removed.connect(self._on_layer_removed)
        self.data.display_name_changed.connect(self.data_name_changed)

        for layer in self.layers:
            self._on_layer_added(layer)

        self.data_name_changed.emit(self.data.display_name)

    def _on_layer_added(self, layer: Layer):
        actor = create_layer_actor(layer)
        if actor is None:
            return

        self.layer_actor_about_to_add.emit(actor)

        self._layer_to_actor[layer] = actor
        self.add_actor(actor)

        if len(self._layer_to_actor) == 1:  # If was added the first layer actor
            self.active_layer_view = actor

        self.layer_actor_added.emit(actor)

    def _on_layer_removed(self, layer: Layer):
        actor = self._layer_to_actor.get(layer)
        if actor is None:
            return

        self.layer_actor_about_to_remove.emit(actor)

        self.remove_actor(actor)
        del self._layer_to_actor[layer]

        if len(self._layer_to_actor) == 0:
            self.active_layer_view = None

        self.layer_actor_removed.emit(actor)
        actor.deleteLater()
