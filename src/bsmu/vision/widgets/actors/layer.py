from __future__ import annotations

from typing import TYPE_CHECKING, Generic

from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

from bsmu.vision.core.layers import Layer
from bsmu.vision.widgets.actors import GraphicsActor, ItemT

if TYPE_CHECKING:
    from PySide6.QtCore import QObject


class LayerActor(Generic[ItemT], GraphicsActor[Layer, ItemT]):
    def __init__(self, model: Layer | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

    @property
    def layer(self) -> Layer | None:
        return self.model


class RasterLayerActor(LayerActor[QGraphicsPixmapItem]):
    def __init__(self, model: Layer | None = None, parent: QObject | None = None):
        super().__init__(model, parent)


class VectorLayerActor(LayerActor[QGraphicsItem]):
    def __init__(self, model: Layer | None = None, parent: QObject | None = None):
        super().__init__(model, parent)
