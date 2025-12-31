from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QPen
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem

from bsmu.vision.core.data.vector.shapes import VectorShape, Point, Polyline
from bsmu.vision.widgets.actors import GraphicsActor, ItemT

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF

ShapeT = TypeVar('ShapeT', bound=VectorShape)


class VectorShapeActor(Generic[ShapeT, ItemT], GraphicsActor[ShapeT, ItemT]):
    def __init__(self, model: ShapeT | None, parent: QObject | None = None):
        super().__init__(model, parent)

    @property
    def shape(self) -> ShapeT | None:
        return self.model

    def _model_about_to_change(self, new_model: ShapeT | None) -> None:
        if self.model is not None:
            self.model.changed.disconnect(self._update_graphics_item)

    def _model_changed(self) -> None:
        if self.model is not None:
            self.model.changed.connect(self._update_graphics_item)


class PointActor(VectorShapeActor[Point, QGraphicsEllipseItem]):
    def __init__(self, model: Point | None, parent: QObject | None = None):
        super().__init__(model, parent)

        self._handle: InteractiveHandle | None = None

    def _create_graphics_item(self) -> ItemT:
        item = QGraphicsEllipseItem(-3, -3, 6, 6)
        item.setPen(QPen(Qt.GlobalColor.black, 1))
        item.setBrush(QBrush(Qt.GlobalColor.transparent))
        item.setZValue(5)
        return item

    def _update_graphics_item(self):
        if self.model is not None:
            self.graphics_item.setPos(self.model.pos)
            self._update_handle_position()
        else:
            self.graphics_item.setPos(0, 0)

    def enter_edit_mode(self):
        """Show interactive handle."""
        if self._handle is None:
            self._handle = InteractiveHandle(radius=5.0)
            self._handle._on_moved = self._on_handle_moved
            self._handle._on_selected = self._on_handle_selected

        scene = self.graphics_item.scene()
        if self._handle.scene() is None and scene:
            scene.addItem(self._handle)
        self._update_handle_position()

    def exit_edit_mode(self):
        """Hide interactive handle."""
        if self._handle.scene():
            self._handle.scene().removeItem(self._handle)

    def _update_handle_position(self):
        if self.model and self._handle and self._handle.scene():  # TODO: just keep: if self.model and self._handle
            self._handle.setPos(self.model.pos)

    def _on_handle_moved(self, new_pos: QPointF):
        if self.model:
            self.model.pos = new_pos  # emits model.changed -> updates graphics item

    def _on_handle_selected(self) -> None:
        # Emit selection signal if you define one in PointActor
        # self.selected.emit()
        pass


class PolylineActor(VectorShapeActor[Polyline, QGraphicsPathItem]):
    def __init__(self, model: Polyline | None, parent: QObject | None = None):
        super().__init__(model, parent)


class InteractiveHandle(QGraphicsEllipseItem):
    """Lightweight, draggable edit handle for vector shapes."""
    def __init__(self, radius: float = 5.0, brush: QBrush = None, parent: QGraphicsItem = None):
        super().__init__(QRectF(-radius, -radius, 2 * radius, 2 * radius), parent)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        if brush is not None:
            self.setBrush(brush)

        ######---------
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        self.setBrush(QBrush(Qt.red))
        self.setPen(QPen(Qt.black, 1))
        self.setCursor(Qt.PointingHandCursor)
        self.setZValue(10)  # appear above other items
        ######

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.ItemPositionHasChanged:
            self._on_moved(value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._on_selected()
        super().mousePressEvent(event)

    # To be overridden by subclasses or patched
    def _on_moved(self, new_pos):
        pass

    def _on_selected(self):
        pass
