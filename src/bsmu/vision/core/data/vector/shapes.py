from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple, Generic, TypeVar

from PySide6.QtCore import QObject, QPointF, Signal

from bsmu.vision.core.utils.geometry import GeometryUtils, GEOMETRY_EPSILON

if TYPE_CHECKING:
    from typing import Sequence


class VectorElement(QObject):
    changed = Signal()  # Emitted when the element's internal state is modified

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def squared_distance_to_scene_pos(self, scene_pos: QPointF) -> float:
        """Must be overridden by subclasses.
        Return infinity by default so it is never selected as the nearest element."""
        return math.inf


@dataclass(slots=True)
class BaseShapeState:
    """Abstract base class for all shape states used in Undo/Redo."""
    pass


@dataclass(slots=True)
class ShapeState(BaseShapeState):
    origin: QPointF = field(default_factory=QPointF)


@dataclass(slots=True)
class SnappedSpanState(BaseShapeState):
    start_arc: float = 0.0
    end_arc: float = 0.0


class VectorShape(VectorElement):
    parent_shape_changed = Signal(VectorElement)  # VectorShape

    transform_changed = Signal()  # Local origin/transform changed
    scene_transform_changed = Signal()

    geometry_changed = Signal()  # Node positions changed
    structure_changed = Signal()  # Nodes added/removed

    def __init__(
            self,
            origin: QPointF | None = None,
            parent_shape: VectorShape | None = None,
            inherit_transform: bool = True,
            parent: QObject | None = None,
    ):
        super().__init__(parent)

        # The origin is stored in local coordinates.
        # When inherit_transform is True, it represents an offset relative to the parent.
        # When False, the shape is not affected by parent transforms, so its local
        # coordinate system coincides with the scene and the origin acts as a scene position.
        self._origin = QPointF(origin) if origin is not None else QPointF(0, 0)
        self._parent_shape: VectorShape | None = None
        self._child_shapes: set[VectorShape] = set()
        self._inherit_transform = inherit_transform

        # Set parent through setter to trigger automatic child registration
        if parent_shape is not None:
            self.parent_shape = parent_shape

    @property
    def origin(self) -> QPointF:
        return QPointF(self._origin)

    @origin.setter
    def origin(self, value: QPointF):
        if self._origin != value:
            self._origin = QPointF(value)
            self.transform_changed.emit()
            self.scene_transform_changed.emit()

    @property
    def parent_shape(self) -> VectorShape | None:
        return self._parent_shape

    @parent_shape.setter
    def parent_shape(self, value: VectorShape | None):
        if self._parent_shape is value:
            return

        self._on_parent_shape_about_to_change()

        if self._parent_shape is not None:
            if self._inherit_transform:
                self._parent_shape.scene_transform_changed.disconnect(self._on_parent_scene_transform_changed)
            self._parent_shape._child_shapes.remove(self)

        self._parent_shape = value

        if self._parent_shape is not None:
            self._parent_shape._child_shapes.add(self)
            if self._inherit_transform:
                self._parent_shape.scene_transform_changed.connect(self._on_parent_scene_transform_changed)

        self._on_parent_shape_changed()
        self.parent_shape_changed.emit(value)

    def _on_parent_shape_about_to_change(self) -> None:
        """Override to clean up before the parent shape changes."""
        pass

    def _on_parent_shape_changed(self) -> None:
        """Override to set up after the parent shape changes."""
        pass

    def _on_parent_scene_transform_changed(self):
        self.scene_transform_changed.emit()

    @property
    def child_shapes(self) -> set[VectorShape]:
        return self._child_shapes.copy()

    @property
    def inherit_transform(self) -> bool:
        return self._inherit_transform

    def capture_state(self) -> BaseShapeState:
        return ShapeState(origin=self.origin)

    def restore_state(self, state: BaseShapeState) -> None:
        self.origin = state.origin

    def calculate_grab_value(self, cursor_scene_pos: QPointF) -> QPointF:
        """Calculate grab point for drag start."""
        return QPointF(cursor_scene_pos)

    def apply_drag(self, cursor_scene_pos: QPointF, grab_value: QPointF) -> QPointF:
        """Apply drag and return updated grab value for next frame."""
        delta = cursor_scene_pos - grab_value
        self.move_by(delta)
        return QPointF(cursor_scene_pos)

    def move_by(self, offset: QPointF) -> None:
        self.origin += offset

    def local_to_scene(self, local_pos: QPointF) -> QPointF:
        """
        Convert a local coordinate to an absolute scene coordinate.
        Recursively apply parent transforms to support arbitrary nesting depth.
        """
        current_pos = self._origin + local_pos
        if self._inherit_transform and self._parent_shape is not None:
            return self._parent_shape.local_to_scene(current_pos)
        return current_pos

    def scene_to_local(self, scene_pos: QPointF) -> QPointF:
        """
        Convert an absolute scene coordinate to a local coordinate.
        Recursively unwind parent transforms.
        """
        if self._inherit_transform and self._parent_shape is not None:
            scene_pos = self._parent_shape.scene_to_local(scene_pos)
        return scene_pos - self._origin

    def collect_descendants(self) -> list[VectorShape]:
        """Return all descendant shapes in post-order (children before parents)."""
        descendants: list[VectorShape] = []
        for child in self._child_shapes:
            descendants.extend(child.collect_descendants())
            descendants.append(child)
        return descendants


class VectorNode(VectorElement):
    """Node stores position relative to parent shape's origin."""

    parent_shape_changed = Signal(VectorShape)  # NodeBasedShape

    def __init__(
            self,
            parent_shape: NodeBasedShape,
            local_pos: QPointF,
            parent: QObject | None = None,
    ):
        super().__init__(parent)

        self._parent_shape = parent_shape
        self._local_pos = QPointF(local_pos)

    @classmethod
    def from_scene_pos(cls, parent_shape: NodeBasedShape, scene_pos: QPointF, parent: QObject | None = None) -> VectorNode:
        """Create a node from a scene (absolute) position."""
        return cls(parent_shape, parent_shape.scene_to_local(scene_pos), parent)

    @classmethod
    def from_local_pos(cls, parent_shape: NodeBasedShape, local_pos: QPointF, parent: QObject | None = None) -> VectorNode:
        """Create a node from a local (relative) position."""
        return cls(parent_shape, local_pos, parent)

    @property
    def parent_shape(self) -> NodeBasedShape:
        return self._parent_shape

    @parent_shape.setter
    def parent_shape(self, value: NodeBasedShape | None):
        if self._parent_shape is not value:
            self._on_parent_shape_about_to_change()
            self._parent_shape = value
            self._on_parent_shape_changed()
            self.parent_shape_changed.emit(value)

    def _on_parent_shape_about_to_change(self) -> None:
        """Override to clean up before the parent shape changes."""
        pass

    def _on_parent_shape_changed(self) -> None:
        """Override to set up after the parent shape changes."""
        pass

    @property
    def scene_pos(self) -> QPointF:
        """Return the scene coordinates.

        Use the `local_pos` property (not the `_local_pos` field) to ensure
        dynamic position calculations in subclasses (e.g., SnappedNode) work correctly.
        """
        return self._parent_shape.local_to_scene(self.local_pos)

    @scene_pos.setter
    def scene_pos(self, value: QPointF):
        self.local_pos = self._parent_shape.scene_to_local(value)

    @property
    def local_pos(self) -> QPointF:
        """Position relative to parent shape's origin (local)."""
        return QPointF(self._local_pos)

    @local_pos.setter
    def local_pos(self, value: QPointF):
        if self._local_pos != value:
            self._local_pos = QPointF(value)
            self.changed.emit()
            self._parent_shape.geometry_changed.emit()

    def squared_distance_to_scene_pos(self, scene_pos: QPointF) -> float:
        return GeometryUtils.squared_distance(self.scene_pos, scene_pos)

    def move_by(self, offset: QPointF) -> None:
        self.local_pos += offset

    def update_drag_position(
            self,
            cursor_scene_pos: QPointF,
            initial_local_pos: QPointF,
            drag_start_scene_pos: QPointF,
    ) -> None:
        """Translate node by cursor delta in local coordinates."""
        local_cursor = self.parent_shape.scene_to_local(cursor_scene_pos)
        local_start = self.parent_shape.scene_to_local(drag_start_scene_pos)
        delta = local_cursor - local_start
        self.local_pos = initial_local_pos + delta


class Point(VectorShape):
    def __init__(
            self,
            pos: QPointF,
            parent_shape: VectorShape | None = None,
            inherit_transform: bool = True,
            parent: QObject | None = None,
    ):
        # Origin is the point position.
        super().__init__(origin=pos, parent_shape=parent_shape, inherit_transform=inherit_transform, parent=parent)

    @property
    def pos(self) -> QPointF:
        return self.origin

    @pos.setter
    def pos(self, value: QPointF):
        self.origin = value


@dataclass(frozen=True)
class EdgeHitInfo:
    closest_point: QPointF | None = None
    edge_index: int | None = None             # Index of the starting node of the edge
    edge_normalized_pos: float | None = None  # Normalized position [0, 1] along the edge
    squared_distance: float | None = None


class ArcParam(NamedTuple):
    """Parametric representation of a point along an arc-length path.

    Attributes:
        segment_index: Index of the path segment containing the point.
        normalized_t: Normalized position (0.0 to 1.0) within that segment.
    """
    segment_index: int
    normalized_t: float


NodeT = TypeVar('NodeT', bound=VectorNode)

class NodeBasedShape(VectorShape, Generic[NodeT]):
    """Base class for shapes defined by a sequence of editable VectorNodes."""

    node_about_to_add = Signal(VectorNode, int)  # Node and its insertion index
    node_added = Signal(VectorNode, int)
    node_about_to_remove = Signal(VectorNode, int)
    node_removed = Signal(VectorNode, int)

    completed = Signal()

    def __init__(
            self,
            points: Sequence[QPointF] = (),
            origin: QPointF | None = None,
            parent_shape: VectorShape | None = None,
            inherit_transform: bool = True,
            parent: QObject | None = None
    ):
        super().__init__(origin=origin, parent_shape=parent_shape, inherit_transform=inherit_transform, parent=parent)

        self._nodes: list[NodeT] = self._create_nodes(points)

        self._is_completed = False

    def _create_nodes(self, points: Sequence[QPointF]) -> list[NodeT]:
        """Override to customize node creation. Defaults to standard VectorNodes."""
        return [
            VectorNode.from_scene_pos(self, point, parent=self)
            for point in points
        ]

    @property
    def nodes(self) -> Sequence[NodeT]:
        """Immutable sequence of nodes. Do not modify."""
        return self._nodes

    @property
    def scene_points(self) -> list[QPointF]:
        """Return node positions in scene coordinates."""
        return [node.scene_pos for node in self._nodes]

    @property
    def local_points(self) -> list[QPointF]:
        """Return node positions in local coordinates."""
        return [node.local_pos for node in self._nodes]

    @property
    def is_empty(self) -> bool:
        return not self._nodes

    @property
    def last_node(self) -> NodeT:
        return self._nodes[-1]

    @property
    def length(self) -> float:
        if len(self._nodes) < 2:
            return 0.0

        return sum(
            GeometryUtils.distance(self._nodes[i].local_pos, self._nodes[i + 1].local_pos)
            for i in range(len(self._nodes) - 1)
        )

    @property
    def is_completed(self) -> bool:
        return self._is_completed

    @property
    def is_draft(self) -> bool:
        return not self._is_completed

    def complete(self) -> None:
        """Mark shape as finalized in the document. Not undoable."""
        if not self._is_completed:
            self._is_completed = True
            self.completed.emit()

    def squared_distance_to_scene_pos(self, scene_pos: QPointF) -> float:
        hit = self.closest_edge(scene_pos)
        if hit is not None:
            return hit.squared_distance

        points = self._scene_path_points()
        if not points:
            return super().squared_distance_to_scene_pos(scene_pos)

        # Fallback for a single point (closest_edge requires >= 2 points)
        return GeometryUtils.squared_distance(points[0], scene_pos)

    def create_node(self, scene_pos: QPointF, index: int | None = None) -> NodeT:
        """Create and insert node at index (appends if None)."""
        node = VectorNode.from_scene_pos(self, scene_pos, parent=self)
        self._insert_node(node, index)
        return node

    def create_node_local(self, local_pos: QPointF, index: int | None = None) -> NodeT:
        """Create and insert node using local coordinates."""
        node = VectorNode.from_local_pos(self, local_pos, parent=self)
        self._insert_node(node, index)
        return node

    def _insert_node(self, node: NodeT, index: int | None = None) -> None:
        """Insert node and emit signals."""
        if index is None:
            index = len(self._nodes)

        self.node_about_to_add.emit(node, index)
        self._nodes.insert(index, node)
        self.node_added.emit(node, index)

        self.structure_changed.emit()

    def remove_node(self, node: NodeT) -> None:
        """Remove specific node by reference."""
        index = self._nodes.index(node)
        self.pop_node(index)

    def pop_node(self, index: int = -1) -> NodeT:
        """Remove and return a node by index. Defaults to last node."""
        if not self._nodes:
            raise IndexError('Cannot pop node from empty shape.')

        if index == -1:
            index = len(self._nodes) - 1

        self.node_about_to_remove.emit(self._nodes[index], index)
        node = self._nodes.pop(index)

        node.parent_shape = None
        node.setParent(None)

        self.node_removed.emit(node, index)
        self.structure_changed.emit()
        return node

    def clear_nodes(self) -> None:
        """Remove all nodes."""
        while self._nodes:
            self.pop_node()

    def _scene_path_points(self) -> list[QPointF]:
        """Return scene positions defining the shape's edges for hit-testing.

        Override in subclasses to customize the path geometry
        (e.g., to follow a parent shape in SnappedSpan).
        """
        return [node.scene_pos for node in self._nodes]

    def closest_edge(
            self,
            scene_pos: QPointF,
            max_tolerance: float = math.inf,
    ) -> EdgeHitInfo | None:
        """Find the closest edge point to a scene position.
        Returns None if shape has < 2 nodes or exceeds tolerance."""
        points = self._scene_path_points()
        if len(points) < 2:
            return None

        closest_hit: EdgeHitInfo | None = None
        min_squared_distance = max_tolerance ** 2

        for i in range(len(points) - 1):
            node_start_pos = points[i]
            node_end_pos = points[i + 1]

            closest_point, normalized_pos = GeometryUtils.closest_point_on_segment(
                node_start_pos, node_end_pos, scene_pos)
            current_squared_distance = GeometryUtils.squared_distance(scene_pos, closest_point)

            if current_squared_distance < min_squared_distance:
                min_squared_distance = current_squared_distance
                closest_hit = EdgeHitInfo(
                    closest_point=closest_point,
                    edge_index=i,
                    edge_normalized_pos=normalized_pos,
                    squared_distance=current_squared_distance,
                )

        return closest_hit

    def map_arc_length_to_param(self, arc_length: float) -> ArcParam:
        """Convert arc-length to parametric position on path."""
        node_count = len(self._nodes)
        if node_count < 2:
            return ArcParam(0, 0.0)

        remaining = max(0.0, arc_length)
        for i in range(node_count - 1):
            p1 = self._nodes[i].local_pos
            p2 = self._nodes[i + 1].local_pos
            seg_len = GeometryUtils.distance(p1, p2)

            if remaining <= seg_len + GEOMETRY_EPSILON:
                t = remaining / seg_len if seg_len > GEOMETRY_EPSILON else 0.0
                return ArcParam(i, max(0.0, min(1.0, t)))
            remaining -= seg_len

        # Arc-length exceeds total path length; clamp to end of last segment
        return ArcParam(max(0, node_count - 2), 1.0)

    def map_point_to_arc_length(self, point: QPointF) -> float:
        """Project point onto nearest path segment and return arc-length from start."""
        hit = self.closest_edge(point, max_tolerance=math.inf)
        if hit is None or hit.edge_index is None or hit.edge_normalized_pos is None:
            return 0.0

        # Sum lengths of all segments before the hit segment
        arc_len = 0.0
        for i in range(hit.edge_index):
            p1 = self._nodes[i].local_pos
            p2 = self._nodes[i + 1].local_pos
            arc_len += GeometryUtils.distance(p1, p2)

        # Add partial length along the hit segment
        p_start = self._nodes[hit.edge_index].local_pos
        p_end = self._nodes[hit.edge_index + 1].local_pos
        arc_len += hit.edge_normalized_pos * GeometryUtils.distance(p_start, p_end)

        return arc_len


@dataclass(frozen=True)
class ClosestPolylinePointInfo:
    point: QPointF | None = None
    segment_index: int | None = None
    squared_distance: float | None = None  # Squared distance from the query point to the closest point on the polyline


class Polyline(NodeBasedShape):
    def __init__(
            self,
            points: Sequence[QPointF] = (),
            origin: QPointF | None = None,
            parent_shape: VectorShape | None = None,
            inherit_transform: bool = True,
            parent: QObject | None = None,
    ):
        super().__init__(
            points, origin=origin, parent_shape=parent_shape, inherit_transform=inherit_transform, parent=parent)

    def closest_point(self, point: QPointF) -> QPointF | None:
        """
        Returns the closest point on the polyline to the given point.
        Returns None if the polyline is empty.
        """
        return self._closest_point_info(point).point

    def closest_point_info(self, point: QPointF) -> ClosestPolylinePointInfo:
        """Returns the closest point with segment info, calculating distance if needed."""
        partial_closest_point_info = self._closest_point_info(point)
        if partial_closest_point_info.point is not None and partial_closest_point_info.squared_distance is None:
            return ClosestPolylinePointInfo(
                point=partial_closest_point_info.point,
                segment_index=partial_closest_point_info.segment_index,
                squared_distance=GeometryUtils.squared_distance(point, partial_closest_point_info.point),
            )
        return partial_closest_point_info

    def _closest_point_info(self, point: QPointF) -> ClosestPolylinePointInfo:
        """
        Internal implementation of closest point search.
        :return: ClosestPolylinePointInfo with:
            - For empty polylines: all None
            - For single-point polylines: (point, 0, None)
            - For normal cases: full results
        """
        if self.is_empty:
            return ClosestPolylinePointInfo()

        if len(self._nodes) == 1:
            return ClosestPolylinePointInfo(point=self.last_node.scene_pos, segment_index=0)

        closest_point: QPointF | None = None
        segment_index: int | None = None
        min_squared_distance: float = math.inf

        # Check each segment of the polyline
        for i in range(len(self._nodes) - 1):
            segment_start = self._nodes[i].scene_pos
            segment_end = self._nodes[i + 1].scene_pos

            segment_closest_point, _ = GeometryUtils.closest_point_on_segment(segment_start, segment_end, point)
            squared_distance = GeometryUtils.squared_distance(point, segment_closest_point)

            if squared_distance < min_squared_distance:
                min_squared_distance = squared_distance
                closest_point = segment_closest_point
                segment_index = i

        return ClosestPolylinePointInfo(
            point=closest_point, segment_index=segment_index, squared_distance=min_squared_distance)
