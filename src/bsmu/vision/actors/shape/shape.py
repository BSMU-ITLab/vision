from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem

from bsmu.vision.actors import GraphicsActor, ItemT
from bsmu.vision.core.data.vector.shapes import VectorShape, Point, Polyline

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

ShapeT = TypeVar('ShapeT', bound=VectorShape)


class VectorShapeActor(Generic[ShapeT, ItemT], GraphicsActor[ShapeT, ItemT]):
    def __init__(self, model: ShapeT | None = None, parent: QObject | None = None):
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
    def __init__(self, model: Point | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

        self._handle: InteractiveHandle | None = None

    def _create_graphics_item(self) -> QGraphicsEllipseItem:
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


class AntialiasedGraphicsPathItem(QGraphicsPathItem):
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            super().paint(painter, option, widget)


class GraphicsNodeItem(QGraphicsEllipseItem):
    def __init__(
            self,
            pos: QPointF,
            radius: float = 5,
            brush: QBrush | None = None,
            parent: QGraphicsItem | None = None
    ):
        super().__init__(QRectF(-radius, -radius, 2 * radius, 2 * radius), parent)

        self.setPos(pos)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        if brush is not None:
            self.setBrush(brush)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)


class PolylineActor(VectorShapeActor[Polyline, AntialiasedGraphicsPathItem]):
    DEFAULT_COMPLETED_COLOR = QColor(106, 255, 13)
    DEFAULT_DRAFT_COLOR = Qt.GlobalColor.blue

    def __init__(
            self,
            model: Polyline | None = None,
            completed_color: QColor | None = None,
            draft_color: QColor | None = None,
            parent: QObject | None = None,
    ):
        self._path: QPainterPath | None = None

        self._completed_color = completed_color or self.DEFAULT_COMPLETED_COLOR
        self._draft_color = draft_color or self.DEFAULT_DRAFT_COLOR

        self._node_items: list[GraphicsNodeItem] = []

        super().__init__(model, parent)

    def _create_graphics_item(self) -> AntialiasedGraphicsPathItem:
        graphics_item = AntialiasedGraphicsPathItem()
        pen = QPen()
        pen.setWidth(3)
        pen.setCosmetic(True)
        graphics_item.setPen(pen)
        return graphics_item

    def _update_graphics_item(self) -> None:
        self._rebuild_path()
        self._rebuild_node_items()
        self._update_color()

    @property
    def polyline(self) -> Polyline | None:
        return self.model

    @property
    def end_point(self) -> QPointF:
        return self.model.end_point

    def append_point(self, point: QPointF) -> None:
        self.model.append_point(point)

    def remove_end_point(self) -> None:
        self.model.remove_end_point()

    def _model_about_to_change(self, new_model: Polyline | None) -> None:
        if self.model is not None:
            self.model.point_appended.disconnect(self._on_point_appended)
            self.model.end_point_removed.disconnect(self._on_end_point_removed)
            self.model.completed.disconnect(self._on_completed)

        super()._model_about_to_change(new_model)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.model is not None:
            self.model.point_appended.connect(self._on_point_appended)
            self.model.end_point_removed.connect(self._on_end_point_removed)
            self.model.completed.connect(self._on_completed)

    def _on_completed(self) -> None:
        self._update_color()

    def _update_color(self) -> None:
        if self.model is None:
            return

        pen = self.graphics_item.pen()
        color = self._completed_color if self.model.is_completed else self._draft_color
        pen.setColor(color)
        self.graphics_item.setPen(pen)

    def _on_point_appended(self, point: QPointF) -> None:
        if not self._path.elementCount():  # If no points exist, move to the first one
            self._path.moveTo(point)
        else:
            self._path.lineTo(point)
        self.graphics_item.setPath(self._path)

        self._create_node_for_point(point)

    def _create_node_for_point(self, point: QPointF) -> GraphicsNodeItem:
        node = GraphicsNodeItem(point, brush=self._completed_color, parent=self.graphics_item)
        self._node_items.append(node)
        return node

    def _on_end_point_removed(self) -> None:
        self._rebuild_path()

        end_node = self._node_items.pop()
        end_node.scene().removeItem(end_node)

    def _rebuild_path(self) -> None:
        self._path = QPainterPath()  # Avoid using self._path.clear(),
        # as it does not clear moveTo element in PySide 6.8.0.2
        if self.model is not None and self.model.points:
            self._path.moveTo(self.model.points[0])
            for point in self.model.points[1:]:
                self._path.lineTo(point)
        self.graphics_item.setPath(self._path)

    def _rebuild_node_items(self) -> None:
        # Remove all existing node items
        scene = self.graphics_item.scene()
        for node in self._node_items:
            scene.removeItem(node)
        self._node_items.clear()

        # Recreate nodes for current points
        if self.model is not None:
            for point in self.model.points:
                self._create_node_for_point(point)


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
