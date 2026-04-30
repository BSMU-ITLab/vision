from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem

from bsmu.vision.actors import GraphicsActor, ItemT
from bsmu.vision.core.data.vector.shapes import VectorElement, VectorShape, VectorNode, Point, NodeBasedShape, Polyline

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

ElementT = TypeVar('ElementT',bound=VectorElement)
ShapeT = TypeVar('ShapeT', bound=VectorShape)


class VectorElementActor(GraphicsActor[ElementT, ItemT], Generic[ElementT, ItemT]):
    def __init__(self, model: ElementT | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

    def _model_about_to_change(self, new_model: ElementT | None) -> None:
        if self.model is not None:
            self.model.changed.disconnect(self._update_graphics_item)

    def _model_changed(self) -> None:
        if self.model is not None:
            self.model.changed.connect(self._update_graphics_item)


class VectorShapeActor(VectorElementActor[ShapeT, ItemT], Generic[ShapeT, ItemT]):
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


class VectorNodeActor(VectorElementActor[VectorNode, GraphicsNodeItem]):
    """Actor for a single editable node (control point) of a vector shape."""

    def __init__(
            self,
            model: VectorNode | None = None,
            radius: float = 5.0,
            brush: QBrush | None = None,
            parent: QObject | None = None,
    ):
        self._radius = radius
        if brush is None:
            brush = QBrush(QColor(106, 255, 13))
        self._brush = brush

        super().__init__(model, parent)

    @property
    def node(self) -> VectorNode | None:
        return self.model

    def update_visual_state(self, color: QColor | None = None) -> None:
        brush = QBrush(color) if color is not None else self._brush
        self.graphics_item.setBrush(brush)

    def cleanup(self) -> None:
        self._remove_from_scene()
        self.model = None  # To disconnect signals (optional but safe)
        self.deleteLater()

    def _create_graphics_item(self) -> GraphicsNodeItem:
        return GraphicsNodeItem(radius=self._radius, brush=self._brush)

    def _update_graphics_item(self) -> None:
        if self.model is not None:
            self._update_pos()

    def _update_pos(self) -> None:
        self.graphics_item.setPos(self.model.local_pos)


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

    def _update_graphics_item(self) -> None:
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


NodeBasedShapeT = TypeVar('NodeBasedShapeT', bound=NodeBasedShape)
AntialiasedGraphicsPathItemT = TypeVar('AntialiasedGraphicsPathItemT', bound=AntialiasedGraphicsPathItem)

class NodeBasedShapeActor(
    VectorShapeActor[NodeBasedShapeT, AntialiasedGraphicsPathItemT],
    Generic[NodeBasedShapeT, AntialiasedGraphicsPathItemT]
):
    DEFAULT_DRAFT_COLOR = QColor('#94ed64')
    DEFAULT_COMPLETED_COLOR = QColor('#6495ed')
    DEFAULT_SUBSELECTED_COLOR = QColor('#93baff')  # '#bd64ed'
    DEFAULT_SELECTED_COLOR = QColor('#ffc867')  # '#edbd64'

    def __init__(
            self,
            model: NodeBasedShape | None = None,
            node_radius: float = 5.0,
            node_default_brush: QBrush | None = None,
            draft_color: QColor | None = None,
            completed_color: QColor | None = None,
            subselected_color: QColor | None = None,
            selected_color: QColor | None = None,
            parent: QObject | None = None,
    ):
        self._node_radius = node_radius
        self._node_default_brush = node_default_brush or self.DEFAULT_DRAFT_COLOR
        self._draft_color = draft_color or self.DEFAULT_DRAFT_COLOR
        self._completed_color = completed_color or self.DEFAULT_COMPLETED_COLOR
        self._subselected_color = subselected_color or self.DEFAULT_SUBSELECTED_COLOR
        self._selected_color = selected_color or self.DEFAULT_SELECTED_COLOR
        self._node_actors: list[VectorNodeActor] = []

        super().__init__(model, parent)

    @property
    def last_node(self) -> VectorNode:
        return self.model.last_node

    def create_node(self, pos: QPointF) -> VectorNode:
        return self.model.create_node(pos)

    def pop_node(self, index: int = -1) -> VectorNode:
        return self.model.pop_node(index)

    def _model_about_to_change(self, new_model: NodeBasedShape | None) -> None:
        if self.model is not None:
            self.model.transform_changed.disconnect(self._on_transform_changed)
            self.model.geometry_changed.disconnect(self._on_geometry_changed)
            self.model.node_added.disconnect(self._on_node_added)
            self.model.node_removed.disconnect(self._on_node_removed)
            self.model.completed.disconnect(self._on_completed)

        super()._model_about_to_change(new_model)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.model is not None:
            self.model.transform_changed.connect(self._on_transform_changed)
            self.model.geometry_changed.connect(self._on_geometry_changed)
            self.model.node_added.connect(self._on_node_added)
            self.model.node_removed.connect(self._on_node_removed)
            self.model.completed.connect(self._on_completed)

    def _on_transform_changed(self) -> None:
        self._update_item_pos()

    def _update_item_pos(self) -> None:
        self.graphics_item.setPos(self.model.origin)

    def _on_geometry_changed(self) -> None:
        self._rebuild_path()
        # Node actors update their positions autonomously via their own model signals

    def _on_completed(self) -> None:
        self.update_visual_state()

    def _on_node_added(self, node: VectorNode, index: int) -> None:
        self._create_node_actor(node, index)
        self._on_nodes_changed()

    def _on_node_removed(self, node: VectorNode, index: int) -> None:
        self._remove_node_actor(index)
        self._on_nodes_changed()

    def _on_nodes_changed(self) -> None:
        """Called after node addition/removal. Defaults to full path rebuild."""
        self._rebuild_path()

    def _create_node_actor(self, node: VectorNode, index: int | None = None) -> VectorNodeActor:
        node_actor = VectorNodeActor(node, radius=self._node_radius, brush=self._node_default_brush, parent=self)
        if index is None:
            index = len(self._node_actors)
        self._node_actors.insert(index, node_actor)
        node_actor.graphics_item.setParentItem(self.graphics_item)
        return node_actor

    def _remove_node_actor(self, index: int) -> None:
        node_actor = self._node_actors.pop(index)
        node_actor.cleanup()

    def _rebuild_node_actors(self) -> None:
        # Clean up old node actors
        for node_actor in self._node_actors:
            node_actor.cleanup()
        self._node_actors.clear()

        # Create new node actors
        if self.model is not None:
            for node in self.model.nodes:
                self._create_node_actor(node)

    def _update_graphics_item(self) -> None:
        self._update_item_pos()
        self._rebuild_path()
        self._rebuild_node_actors()
        self._update_graphics_item_visual_state()

    def _rebuild_path(self) -> None:
        """Define how the shape's QPainterPath is constructed."""
        raise NotImplementedError

    def _update_graphics_item_visual_state(self, is_selected: bool = False, has_selected_nodes: bool = False) -> None:
        """Define shape-specific styling (pen color, width, etc.)."""
        if self.model is None:
            return

        pen = self.graphics_item.pen()
        if is_selected:
            color = self._selected_color
        else:
            if self.model.is_completed:
                color = self._subselected_color if has_selected_nodes else self._completed_color
            else:
                color = self._draft_color
        pen.setColor(color)
        self.graphics_item.setPen(pen)

    def update_visual_state(
            self,
            is_selected: bool = False,
            selected_nodes: set[VectorNode] | None = None,
    ) -> None:
        self._update_graphics_item_visual_state(is_selected, bool(selected_nodes))
        selected_nodes = selected_nodes or set()
        for node_actor in self._node_actors:
            is_node_selected = node_actor.node in selected_nodes
            if is_node_selected:
                node_color = self._selected_color
            else:
                node_color = self._completed_color if self.model.is_completed else self._draft_color
            node_actor.update_visual_state(node_color)


class PolylineActor(NodeBasedShapeActor[Polyline, AntialiasedGraphicsPathItem]):
    def __init__(
            self,
            model: Polyline | None = None,
            node_radius: float = 5.0,
            node_default_brush: QBrush | None = None,
            draft_color: QColor | None = None,
            completed_color: QColor | None = None,
            subselected_color: QColor | None = None,
            selected_color: QColor | None = None,
            parent: QObject | None = None,
    ):
        self._path: QPainterPath | None = None

        super().__init__(
            model,
            node_radius=node_radius,
            node_default_brush=node_default_brush,
            draft_color=draft_color,
            completed_color=completed_color,
            subselected_color=subselected_color,
            selected_color=selected_color,
            parent=parent,
        )

    def _create_graphics_item(self) -> AntialiasedGraphicsPathItem:
        graphics_item = AntialiasedGraphicsPathItem()
        pen = QPen()
        pen.setWidth(3)
        pen.setCosmetic(True)
        graphics_item.setPen(pen)
        return graphics_item

    @property
    def polyline(self) -> Polyline | None:
        return self.model

    def _on_node_added(self, node: VectorNode, index: int) -> None:
        """Optimization override to avoid full path rebuild when appending a node."""
        # When appending a node, extend the path with a line segment.
        # For insertion elsewhere, rebuild the entire path.
        if self.model.last_node is node:
            if not self._path.elementCount():  # If no nodes exist, move to the first one
                self._path.moveTo(node.local_pos)
            else:
                self._path.lineTo(node.local_pos)
            self.graphics_item.setPath(self._path)
        else:
            self._rebuild_path()

        self._create_node_actor(node, index)

    def _rebuild_path(self) -> None:
        self._path = QPainterPath()  # Avoid using self._path.clear(),
        # as it does not clear moveTo element in PySide 6.8.0.2
        if self.model is not None and self.model.nodes:
            self._path.moveTo(self.model.nodes[0].local_pos)
            for node in self.model.nodes[1:]:
                self._path.lineTo(node.local_pos)
        self.graphics_item.setPath(self._path)
