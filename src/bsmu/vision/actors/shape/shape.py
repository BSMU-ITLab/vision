from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem

from bsmu.vision.actors import GraphicsActor, ModelT, ItemT
from bsmu.vision.core.data.vector.shapes import VectorShape, VectorNode, Point, Polyline

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

ShapeT = TypeVar('ShapeT', bound=VectorShape)


class VectorActor(GraphicsActor[ModelT, ItemT], Generic[ModelT, ItemT]):
        pass


class VectorShapeActor(VectorActor[ShapeT, ItemT], Generic[ShapeT, ItemT]):
    def __init__(self, model: ShapeT | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

    @property
    def shape(self) -> ShapeT | None:
        return self.model

    def update_visual_state(
            self,
            is_selected: bool = False,
            selected_nodes: set[VectorNode] | None = None,
    ) -> None:
        """
        Update the visual representation of the shape based on its current interaction state.

        :param is_selected: Whether the shape itself is selected.
        :param selected_nodes: Set of this shape's nodes that are currently selected.
        """
        raise NotImplementedError

    def _model_about_to_change(self, new_model: ShapeT | None) -> None:
        if self.model is not None:
            self.model.changed.disconnect(self._update_graphics_item)

    def _model_changed(self) -> None:
        if self.model is not None:
            self.model.changed.connect(self._update_graphics_item)


class GraphicsNodeItem(QGraphicsEllipseItem):
    def __init__(
            self,
            radius: float = 5,
            brush: QBrush | None = None,
            parent: QGraphicsItem | None = None
    ):
        super().__init__(QRectF(-radius, -radius, 2 * radius, 2 * radius), parent)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        if brush is not None:
            self.setBrush(brush)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)


class VectorNodeActor(VectorActor[VectorNode, GraphicsNodeItem]):
    """Actor for a single editable node (control point) of a vector shape."""

    def __init__(
            self,
            model: VectorNode | None = None,
            radius: float = 5.0,
            brush: QBrush | None = None,
            parent: QObject | None = None,
    ):
        self._radius = radius
        self._brush = brush

        super().__init__(model, parent)

    @property
    def node(self) -> VectorNode | None:
        return self.model

    def update_visual_state(self, is_selected: bool = False) -> None:
        brush = QBrush(Qt.GlobalColor.yellow) if is_selected else self._brush
        self.graphics_item.setBrush(brush)

    def _create_graphics_item(self) -> GraphicsNodeItem:
        return GraphicsNodeItem(radius=self._radius, brush=self._brush)

    def _model_about_to_change(self, new_model: VectorNode | None) -> None:
        if self.model is not None:
            self.model.pos_changed.disconnect(self._on_pos_changed)

    def _model_changed(self) -> None:
        if self.model is not None:
            self.model.pos_changed.connect(self._on_pos_changed)

    def _on_pos_changed(self, _pos: QPointF) -> None:
        self._update_pos()

    def _update_graphics_item(self) -> None:
        if self.model is not None:
            self._update_pos()

    def _update_pos(self) -> None:
        self.graphics_item.setPos(self.model.pos)


class PointActor(VectorShapeActor[Point, GraphicsNodeItem]):
    def __init__(self, model: Point | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

    def update_visual_state(
            self,
            is_selected: bool = False,
            selected_nodes: set[VectorNode] | None = None,
    ) -> None:
        color = Qt.GlobalColor.yellow if is_selected else Qt.GlobalColor.red
        self.graphics_item.setBrush(QBrush(color))

    def _create_graphics_item(self) -> GraphicsNodeItem:
        item = GraphicsNodeItem(radius=6, brush=QBrush(Qt.GlobalColor.red))
        # item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        return item

    def _model_about_to_change(self, new_model: Point | None) -> None:
        if self.model is not None:
            self.model.pos_changed.disconnect(self._on_pos_changed)

    def _model_changed(self) -> None:
        if self.model is not None:
            self.model.pos_changed.connect(self._on_pos_changed)

    def _on_pos_changed(self, _pos: QPointF) -> None:
        self._update_pos()

    def _update_graphics_item(self) -> None:
        if self.model is not None:
            self._update_pos()

    def _update_pos(self) -> None:
        self.graphics_item.setPos(self.model.pos)


class AntialiasedGraphicsPathItem(QGraphicsPathItem):
    def __init__(self, path: QPainterPath | None = None, parent: QGraphicsItem | None = None):
        super().__init__(path, parent)

        self._cached_shape: QPainterPath | None = None

        self._stroker = QPainterPathStroker()
        self._stroker.setWidth(1.0)
        self._stroker.setCapStyle(Qt.PenCapStyle.FlatCap)
        self._stroker.setJoinStyle(Qt.PenJoinStyle.BevelJoin)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            super().paint(painter, option, widget)

    def setPath(self, path: QPainterPath) -> None:
        # Note: QGraphicsPathItem::setPath() is not virtual in C++.
        # This redefinition only works if called through Python.
        # If the path is mutated externally (e.g., via C++ or shared reference),
        # the cache won't be invalidated - always update via this method.
        super().setPath(path)
        self._cached_shape = None

    def shape(self) -> QPainterPath:
        # Override to avoid false hits (using QGraphicsScene.items method) inside open paths (e.g., crescents).
        if self._cached_shape is None:
            self._cached_shape = self._stroker.createStroke(self.path())
        return self._cached_shape


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

        self._node_actors: list[VectorNodeActor] = []

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
        self._rebuild_node_actors()
        self._update_color()

    @property
    def polyline(self) -> Polyline | None:
        return self.model

    @property
    def last_node(self) -> VectorNode:
        return self.model.last_node

    def add_node(self, pos: QPointF) -> VectorNode:
        return self.model.add_node(pos)

    def remove_last_node(self) -> VectorNode | None:
        self.model.remove_last_node()

    def update_visual_state(
            self,
            is_selected: bool = False,
            selected_nodes: set[VectorNode] | None = None,
    ) -> None:
        pen = self.graphics_item.pen()
        color = Qt.GlobalColor.yellow if is_selected else Qt.GlobalColor.black
        pen.setColor(color)
        self.graphics_item.setPen(pen)

        selected_nodes = selected_nodes or set()
        for node_actor in self._node_actors:
            is_node_selected = node_actor.node in selected_nodes
            node_actor.update_visual_state(is_node_selected)

    def _model_about_to_change(self, new_model: Polyline | None) -> None:
        if self.model is not None:
            self.model.node_added.disconnect(self._on_node_added)
            self.model.last_node_removed.disconnect(self._on_last_node_removed)
            self.model.completed.disconnect(self._on_completed)

        super()._model_about_to_change(new_model)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.model is not None:
            self.model.node_added.connect(self._on_node_added)
            self.model.last_node_removed.connect(self._on_last_node_removed)
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

    def _on_node_added(self, node: VectorNode) -> None:
        if not self._path.elementCount():  # If no nodes exist, move to the first one
            self._path.moveTo(node.pos)
        else:
            self._path.lineTo(node.pos)
        self.graphics_item.setPath(self._path)

        self._create_node_actor(node)

    def _create_node_actor(self, node: VectorNode) -> VectorNodeActor:
        node_actor = VectorNodeActor(node, brush=self._completed_color, parent=self)
        self._node_actors.append(node_actor)
        node_actor.graphics_item.setParentItem(self.graphics_item)
        return node_actor

    def _on_last_node_removed(self) -> None:
        self._rebuild_path()

        last_node_actor = self._node_actors.pop()
        last_node_actor._remove_from_scene()

    def _rebuild_path(self) -> None:
        self._path = QPainterPath()  # Avoid using self._path.clear(),
        # as it does not clear moveTo element in PySide 6.8.0.2
        if self.model is not None and self.model.nodes:
            self._path.moveTo(self.model.nodes[0].pos)
            for node in self.model.nodes[1:]:
                self._path.lineTo(node.pos)
        self.graphics_item.setPath(self._path)

    def _rebuild_node_actors(self) -> None:
        # Clean up old node actors
        for node_actor in self._node_actors:
            node_actor._remove_from_scene()
        self._node_actors.clear()

        # Create new node actors
        if self.model is not None:
            for node in self.model.nodes:
                self._create_node_actor(node)
