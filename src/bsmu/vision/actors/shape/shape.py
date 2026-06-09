from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem

from bsmu.vision.actors import GraphicsActor, ItemT
from bsmu.vision.core.data.vector.shapes import VectorElement, VectorShape, VectorNode, Point, NodeBasedShape, Polyline

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

ElementT = TypeVar('ElementT',bound=VectorElement)
ShapeT = TypeVar('ShapeT', bound=VectorShape)


DEFAULT_OUTLINE_COLOR = QColor('#262626')

DEFAULT_NODE_RADIUS: float = 5.0
DEFAULT_NODE_COLOR = QColor(106, 255, 13)

# Visually imperceptible threshold: changes < 0.5px are handled by anti-aliasing
_SCREEN_DELTA_THRESHOLD: float = 0.5


class VectorElementActor(GraphicsActor[ElementT, ItemT], Generic[ElementT, ItemT]):
    def __init__(self, model: ElementT | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

    def _model_about_to_change(self, new_model: ElementT | None) -> None:
        if self.model is not None:
            self.model.changed.disconnect(self._update_graphics_item)

    def _model_changed(self) -> None:
        if self.model is not None:
            self.model.changed.connect(self._update_graphics_item)

    def visual_distance_to_scene_pos(self, scene_pos: QPointF) -> float:
        """Return the Euclidean distance from the element's geometry to the scene position.

        Subclasses may override this to return a signed distance for visual
        boundary hit-testing (e.g., negative values indicating 'inside').
        """
        return math.sqrt(self.model.squared_distance_to_scene_pos(scene_pos))


class VectorShapeActor(VectorElementActor[ShapeT, ItemT], Generic[ShapeT, ItemT]):
    def __init__(self, model: ShapeT | None = None, parent: QObject | None = None):
        super().__init__(model, parent)

    @property
    def shape(self) -> ShapeT | None:
        return self.model

    def _model_about_to_change(self, new_model: ElementT | None) -> None:
        if self.model is not None:
            self.model.scene_transform_changed.disconnect(self._on_scene_transform_changed)

        super()._model_about_to_change(new_model)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.model is not None:
            self.model.scene_transform_changed.connect(self._on_scene_transform_changed)

    def _on_scene_transform_changed(self) -> None:
        self._update_scene_position()

    def _update_scene_position(self) -> None:
        if self.graphics_item is None:
            return
        # (0,0) in local coords maps to the shape's origin in scene space.
        # local_to_scene adds self._origin and all parent offsets internally.
        scene_origin = self.model.local_to_scene(QPointF(0, 0))
        # We set the scene position directly (flat item hierarchy, no parent QGraphicsItem)
        # to retain global control over z-ordering independent of logical parenting.
        self.graphics_item.setPos(scene_origin)

    def _update_graphics_item(self) -> None:
        self._update_scene_position()

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


@dataclass(frozen=True)
class NodeVisualState:
    brush: QBrush | None = None
    pen: QPen | None = None
    radius: float = DEFAULT_NODE_RADIUS


class GraphicsNodeItem(QGraphicsEllipseItem):
    def __init__(
            self,
            visual_state: NodeVisualState | None = None,
            parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)

        if visual_state is None:
            visual_state = NodeVisualState()
        self._visual_state = visual_state

        self._current_view_scale: float = 1.0
        self._scene_radius: float = math.inf
        self._scene_pen_width: float = math.inf

        self._apply_visual_state(visual_state)

    @property
    def scene_radius(self) -> float:
        return self._scene_radius

    def _apply_visual_state(self, visual_state: NodeVisualState) -> None:
        self._visual_state = visual_state
        if self._visual_state.brush is not None:
            self.setBrush(self._visual_state.brush)

        self._recalculate_scene_sizes()

    def adjust_to_view_scale(self, view_scale: float) -> None:
        if self._current_view_scale != view_scale:
            self._current_view_scale = view_scale
            self._recalculate_scene_sizes()

    def _recalculate_scene_sizes(self) -> None:
        view_scale = max(self._current_view_scale, 0.001)  # Prevent division by zero
        new_scene_radius = self._visual_state.radius / view_scale
        # Convert scene-unit deltas back to screen pixels for accurate thresholding
        scene_radius_delta_screen = abs(self._scene_radius - new_scene_radius) * view_scale

        if self._visual_state.pen is not None:
            new_scene_pen_width = self._visual_state.pen.widthF() / view_scale
            pen_width_delta_screen = abs(self._scene_pen_width - new_scene_pen_width) * view_scale
        else:
            pen_width_delta_screen = -math.inf

        # Only update if the visual change is actually perceptible on screen
        if scene_radius_delta_screen < _SCREEN_DELTA_THRESHOLD and pen_width_delta_screen < _SCREEN_DELTA_THRESHOLD:
            return

        self.prepareGeometryChange()
        self._scene_radius = new_scene_radius
        self.setRect(QRectF(-self._scene_radius, -self._scene_radius, 2 * self._scene_radius, 2 * self._scene_radius))

        if self._visual_state.pen is not None:
            pen = QPen(self._visual_state.pen)
            self._scene_pen_width = new_scene_pen_width
            pen.setWidthF(self._scene_pen_width)
            self.setPen(pen)

    def update_visual_state(self, visual_state: NodeVisualState) -> None:
        self._apply_visual_state(visual_state)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)


VectorNodeT = TypeVar('VectorNodeT', bound=VectorNode)
GraphicsNodeItemT = TypeVar('GraphicsNodeItemT', bound=GraphicsNodeItem)

class VectorNodeActor(
    VectorElementActor[VectorNodeT, GraphicsNodeItemT],
    Generic[VectorNodeT, GraphicsNodeItemT],
):
    """Actor for a single editable node (control point) of a vector shape.

    TODO(arch): Refactor to strict separation of concerns:
        1. Actor should calculate `scene_radius` based on `view_scale`.
        2. Actor should push a `NodeRenderState` dataclass to the Item.
        3. GraphicsNodeItem should become a "dumb" view that only applies pre-calculated values.
    """

    DEFAULT_RADIUS = DEFAULT_NODE_RADIUS
    DEFAULT_BRUSH = QBrush(DEFAULT_NODE_COLOR)

    def __init__(
            self,
            model: VectorNode | None = None,
            visual_state: NodeVisualState | None = None,
            parent: QObject | None = None,
    ):
        if visual_state is None:
            visual_state = NodeVisualState(
                brush=self.DEFAULT_BRUSH,
                radius=self.DEFAULT_RADIUS,
            )
        self._visual_state = visual_state

        super().__init__(model, parent)

    @property
    def node(self) -> VectorNode | None:
        return self.model

    def update_visual_state(self, visual_state: NodeVisualState) -> None:
        self._visual_state = visual_state
        self.graphics_item.update_visual_state(visual_state)

    def cleanup(self) -> None:
        self._remove_from_scene()
        self.model = None  # To disconnect signals (optional but safe)
        self.deleteLater()

    def _create_graphics_item(self) -> GraphicsNodeItem:
        return GraphicsNodeItem(visual_state=self._visual_state)

    def _update_graphics_item(self) -> None:
        if self.model is not None:
            self._update_pos()

    def _update_pos(self) -> None:
        self.graphics_item.setPos(self.model.local_pos)

    def _on_view_scale_changed(self) -> None:
        if self.graphics_item is not None:
            self.graphics_item.adjust_to_view_scale(self._current_view_scale)

    def visual_distance_to_scene_pos(self, scene_pos: QPointF) -> float:
        """Return the signed distance to the node's visual edge.

        Negative values indicate the point is inside the visual radius,
        while positive values indicate it is outside. Ideal for hit-testing.
        """
        squared_distance = self.model.squared_distance_to_scene_pos(scene_pos)
        distance_to_center = math.sqrt(squared_distance)
        return distance_to_center - self.graphics_item.scene_radius


class PointActor(VectorShapeActor[Point, GraphicsNodeItem]):
    DEFAULT_RADIUS = 6.0
    DEFAULT_BRUSH = QBrush(Qt.GlobalColor.red)

    def __init__(
            self,
            model: Point | None = None,
            visual_state: NodeVisualState | None = None,
            parent: QObject | None = None,
    ):
        if visual_state is None:
            visual_state = NodeVisualState(
                brush=self.DEFAULT_BRUSH,
                radius=self.DEFAULT_RADIUS,
            )
        self._visual_state = visual_state

        super().__init__(model, parent)

    def update_visual_state(
            self,
            is_selected: bool = False,
            selected_nodes: set[VectorNode] | None = None,
    ) -> None:
        color = Qt.GlobalColor.yellow if is_selected else Qt.GlobalColor.red
        self.graphics_item.setBrush(QBrush(color))

    def _create_graphics_item(self) -> GraphicsNodeItem:
        return GraphicsNodeItem(self._visual_state)

    def _update_graphics_item(self) -> None:
        self._update_pos()

    def _update_pos(self) -> None:
        self.graphics_item.setPos(self.model.pos)


class AntialiasedGraphicsPathItem(QGraphicsPathItem):
    def __init__(self, path: QPainterPath | None = None, parent: QGraphicsItem | None = None):
        super().__init__(path, parent)

        self._pen_target_screen_width: float = 3.0
        self._pen_current_scene_width: float = self.pen().widthF()
        self._current_view_scale: float = 1.0

        self._outline_target_screen_width: float = 1.0
        self._outline_current_scene_width: float = self._outline_target_screen_width

        self._cached_shape: QPainterPath | None = None

        self._hit_test_stroker = QPainterPathStroker()
        self._hit_test_stroker.setWidth(1.0)
        self._hit_test_stroker.setCapStyle(Qt.PenCapStyle.FlatCap)
        self._hit_test_stroker.setJoinStyle(Qt.PenJoinStyle.BevelJoin)

    @property
    def pen_target_screen_width(self) -> float:
        return self._pen_target_screen_width

    @pen_target_screen_width.setter
    def pen_target_screen_width(self, value: float) -> None:
        if self._pen_target_screen_width != value:
            self._pen_target_screen_width = value
            self._recalculate_pen_scene_widths()

    @property
    def outline_target_screen_width(self) -> float:
        return self._outline_target_screen_width

    @outline_target_screen_width.setter
    def outline_target_screen_width(self, value: float) -> None:
        if self._outline_target_screen_width != value:
            self._outline_target_screen_width = value
            self._recalculate_pen_scene_widths()

    def boundingRect(self) -> QRectF:
        if self.path().isEmpty():
            return QRectF()

        pen_margin = (self._pen_current_scene_width + self._outline_current_scene_width) / 2.0
        return self.path().boundingRect().adjusted(
            -pen_margin, -pen_margin,
            pen_margin, pen_margin,
        )

    def adjust_to_view_scale(self, view_scale: float) -> None:
        if self._current_view_scale != view_scale:
            self._current_view_scale = view_scale
            self._recalculate_pen_scene_widths()

    def _recalculate_pen_scene_widths(self) -> None:
        view_scale = max(self._current_view_scale, 0.001)  # Prevent division by zero
        pen_new_scene_width = self._pen_target_screen_width / view_scale
        outline_new_scene_width = self._outline_target_screen_width / view_scale

        # Convert scene-unit deltas back to screen pixels for accurate thresholding
        pen_delta_screen = abs(self._pen_current_scene_width - pen_new_scene_width) * view_scale
        outline_delta_screen = abs(self._outline_current_scene_width - outline_new_scene_width) * view_scale
        # Only update if the visual change is actually perceptible on screen
        if pen_delta_screen < _SCREEN_DELTA_THRESHOLD and outline_delta_screen < _SCREEN_DELTA_THRESHOLD:
            return

        self.prepareGeometryChange()
        self._pen_current_scene_width = pen_new_scene_width
        self._outline_current_scene_width = outline_new_scene_width

        pen = self.pen()
        pen.setWidthF(self._pen_current_scene_width)
        self.setPen(pen)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        if self.path().isEmpty():
            return

        main_pen = self.pen()
        if main_pen.style() == Qt.PenStyle.NoPen:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._outline_current_scene_width > 0.0:
            # Draw outline
            outline_pen = QPen(main_pen)
            outline_pen.setWidthF(self._pen_current_scene_width + self._outline_current_scene_width)
            outline_pen.setColor(DEFAULT_OUTLINE_COLOR)
            painter.setPen(outline_pen)
            painter.drawPath(self.path())

        # Draw main line on top
        painter.setPen(main_pen)
        painter.drawPath(self.path())

        painter.restore()

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
            self._cached_shape = self._hit_test_stroker.createStroke(self.path())
        return self._cached_shape


NodeBasedShapeT = TypeVar('NodeBasedShapeT', bound=NodeBasedShape)
AntialiasedGraphicsPathItemT = TypeVar('AntialiasedGraphicsPathItemT', bound=AntialiasedGraphicsPathItem)

class NodeBasedShapeActor(
    VectorShapeActor[NodeBasedShapeT, AntialiasedGraphicsPathItemT],
    Generic[NodeBasedShapeT, AntialiasedGraphicsPathItemT],
):
    DEFAULT_DRAFT_COLOR = QColor('#6495ed')
    DEFAULT_COMPLETED_COLOR = QColor('#7dab3c')
    DEFAULT_SUBSELECTED_COLOR = QColor('#96c257')
    DEFAULT_SELECTED_COLOR = QColor('#ffc259')

    def __init__(
            self,
            model: NodeBasedShape | None = None,
            node_actor_class: type[VectorNodeActor] = VectorNodeActor,
            draft_color: QColor | None = None,
            completed_color: QColor | None = None,
            subselected_color: QColor | None = None,
            selected_color: QColor | None = None,
            pen_screen_width: int = 3,
            node_radius: float = DEFAULT_NODE_RADIUS,
            node_draft_color: QColor | None = None,
            parent: QObject | None = None,
    ):
        self._node_actor_class = node_actor_class
        self._draft_color = draft_color or self.DEFAULT_DRAFT_COLOR
        self._completed_color = completed_color or self.DEFAULT_COMPLETED_COLOR
        self._subselected_color = subselected_color or self.DEFAULT_SUBSELECTED_COLOR
        self._selected_color = selected_color or self.DEFAULT_SELECTED_COLOR
        self._pen_screen_width = pen_screen_width
        self._node_radius = node_radius
        self._node_draft_color = node_draft_color or self.DEFAULT_DRAFT_COLOR

        self._node_actors: list[VectorNodeActor] = []

        self._path: QPainterPath | None = None

        # Current selection cache
        self._is_selected = False
        self._has_selected_nodes = False

        super().__init__(model, parent)

    @property
    def last_node(self) -> VectorNode:
        return self.model.last_node

    def _create_graphics_item(self) -> AntialiasedGraphicsPathItem:
        return AntialiasedGraphicsPathItem()

    def create_node(self, pos: QPointF) -> VectorNode:
        return self.model.create_node(pos)

    def pop_node(self, index: int = -1) -> VectorNode:
        return self.model.pop_node(index)

    def _model_about_to_change(self, new_model: NodeBasedShape | None) -> None:
        if self.model is not None:
            self.model.geometry_changed.disconnect(self._on_geometry_changed)
            self.model.node_added.disconnect(self._on_node_added)
            self.model.node_removed.disconnect(self._on_node_removed)
            self.model.completed.disconnect(self._on_completed)

        super()._model_about_to_change(new_model)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.model is not None:
            self.model.geometry_changed.connect(self._on_geometry_changed)
            self.model.node_added.connect(self._on_node_added)
            self.model.node_removed.connect(self._on_node_removed)
            self.model.completed.connect(self._on_completed)

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
        node_visual_state = self._compute_node_visual_state()
        node_actor = self._node_actor_class(node, visual_state=node_visual_state, parent=self)
        if index is None:
            index = len(self._node_actors)
        self._node_actors.insert(index, node_actor)
        node_actor.graphics_item.setParentItem(self.graphics_item)
        node_actor.adjust_to_view_scale(self._current_view_scale)
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
        super()._update_graphics_item()

        self._rebuild_path()
        self._rebuild_node_actors()
        self._update_graphics_item_visual_state()

    def _rebuild_path(self) -> None:
        """Define how the shape's QPainterPath is constructed."""
        raise NotImplementedError

    def _update_graphics_item_visual_state(self) -> None:
        """Define shape-specific styling (pen color, width, etc.)."""
        if self.model is None:
            return

        pen = self.graphics_item.pen()
        if self._is_selected:
            color = self._selected_color
            pen_screen_width = self._pen_screen_width + 1
            outline_screen_width = 2
        else:
            if self.model.is_completed:
                color = self._subselected_color if self._has_selected_nodes else self._completed_color
            else:
                color = self._draft_color
            pen_screen_width = self._pen_screen_width
            outline_screen_width = 0.5
        pen.setColor(color)
        self.graphics_item.setPen(pen)
        self.graphics_item.pen_target_screen_width = pen_screen_width
        self.graphics_item.outline_target_screen_width = outline_screen_width

    def _on_view_scale_changed(self) -> None:
        if self.graphics_item is not None:
            self.graphics_item.adjust_to_view_scale(self._current_view_scale)

        for node_actor in self._node_actors:
            node_actor.adjust_to_view_scale(self._current_view_scale)

    def update_visual_state(
            self,
            is_selected: bool = False,
            selected_nodes: set[VectorNode] | None = None,
    ) -> None:
        self._is_selected = is_selected
        self._has_selected_nodes = bool(selected_nodes)

        self._update_graphics_item_visual_state()

        selected_nodes = selected_nodes or set()
        for node_actor in self._node_actors:
            is_node_selected = node_actor.node in selected_nodes
            node_visual_state = self._compute_node_visual_state(is_node_selected=is_node_selected)
            node_actor.update_visual_state(node_visual_state)

    def _compute_node_visual_state(
            self,
            is_node_selected: bool = False,
            is_shape_selected: bool | None = None,
            has_selected_nodes: bool | None = None,
    ) -> NodeVisualState:
        # Use explicit arg if provided, otherwise fall back to cached state
        is_shape_selected = is_shape_selected if is_shape_selected is not None else self._is_selected
        has_selected_nodes = has_selected_nodes if has_selected_nodes is not None else self._has_selected_nodes

        pen = QPen(DEFAULT_OUTLINE_COLOR)
        if is_node_selected:
            color = self._selected_color
            pen.setWidth(2)
            radius = self._node_radius + 1.0
        else:
            if self.model.is_completed:
                color = self._subselected_color if (has_selected_nodes or is_shape_selected) else self._completed_color
            else:
                color = self._node_draft_color
            radius = self._node_radius

        return NodeVisualState(brush=QBrush(color), pen=pen, radius=radius)


class PolylineActor(NodeBasedShapeActor[Polyline, AntialiasedGraphicsPathItem]):
    def __init__(
            self,
            model: Polyline | None = None,
            node_actor_class: type[VectorNodeActor] = VectorNodeActor,
            draft_color: QColor | None = None,
            completed_color: QColor | None = None,
            subselected_color: QColor | None = None,
            selected_color: QColor | None = None,
            pen_screen_width: int = 3,
            node_radius: float = DEFAULT_NODE_RADIUS,
            parent: QObject | None = None,
    ):
        super().__init__(
            model,
            node_actor_class=node_actor_class,
            draft_color=draft_color,
            completed_color=completed_color,
            subselected_color=subselected_color,
            selected_color=selected_color,
            pen_screen_width=pen_screen_width,
            node_radius=node_radius,
            parent=parent,
        )

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
