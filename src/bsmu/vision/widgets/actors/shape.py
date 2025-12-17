from __future__ import annotations

from typing import TYPE_CHECKING, Generic

from bsmu.vision.core.data import VectorShape
from bsmu.vision.widgets.actors import GraphicsActor, ItemT

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem


class VectorShapeActor(Generic[ItemT], GraphicsActor[VectorShape, ItemT]):
    def __init__(self, model: VectorShape | None, parent: QObject | None = None):
        super().__init__(model, parent)

    @property
    def shape(self) -> VectorShape | None:
        return self.model


class PolylineActor(VectorShapeActor[QGraphicsPathItem]):
    def __init__(self, model: VectorShape | None, parent: QObject | None = None):
        super().__init__(model, parent)


class PointActor(VectorShapeActor[QGraphicsEllipseItem]):
    def __init__(self, model: VectorShape | None, parent: QObject | None = None):
        super().__init__(model, parent)
