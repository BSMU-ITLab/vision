from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtGui import QPainterPath

from bsmu.vision.actors.shape import (
    AntialiasedGraphicsPathItemT, GraphicsNodeItem, NodeBasedShapeActor, VectorNodeActor)
from bsmu.vision.core.data.vector.shapes.constrained import SnappedNode, SnappedSpan

if TYPE_CHECKING:
    from PySide6.QtCore import QObject


class SnappedNodeActor(VectorNodeActor[SnappedNode, GraphicsNodeItem]):
    pass


SnappedSpanT = TypeVar('SnappedSpanT', bound=SnappedSpan)

class SnappedSpanActor(
    NodeBasedShapeActor[SnappedSpanT, AntialiasedGraphicsPathItemT],
    Generic[SnappedSpanT, AntialiasedGraphicsPathItemT],
):
    def __init__(
            self,
            model: SnappedSpanT | None = None,
            node_actor_class: type[SnappedNodeActor] = SnappedNodeActor,
            parent: QObject | None = None,
    ) -> None:
        super().__init__(model, node_actor_class=node_actor_class, parent=parent)

    def _rebuild_path(self) -> None:
        self._path = QPainterPath()
        if self.model is None or not self.model.is_parent_valid:
            self.graphics_item.setVisible(False)
            self.graphics_item.setPath(self._path)
            return

        scene_points = self.model.scene_path_points()
        if not scene_points:
            self.graphics_item.setVisible(False)
            self.graphics_item.setPath(self._path)
            return

        local_points = [self.model.scene_to_local(scene_point) for scene_point in scene_points]

        self._path.moveTo(local_points[0])
        for local_point in local_points[1:]:
            self._path.lineTo(local_point)

        self.graphics_item.setPath(self._path)
        self.graphics_item.setVisible(True)
