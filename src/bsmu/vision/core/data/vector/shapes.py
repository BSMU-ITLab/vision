from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from PySide6.QtCore import QObject, QPointF, Signal

from bsmu.vision.core.utils.geometry import GeometryUtils


class VectorElement(QObject):
    changed = Signal()  # Emitted when the element's internal state is modified

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)


class VectorShape(VectorElement):
    parent_shape_changed = Signal(VectorElement)  # VectorShape

    transform_changed = Signal()  # Origin/transform changed
    geometry_changed = Signal()  # Node positions changed
    structure_changed = Signal()  # Nodes added/removed

    def __init__(
            self,
            origin: QPointF | None = None,
            parent_shape: VectorShape | None = None,
            parent: QObject | None = None
    ):
        super().__init__(parent)

        self._origin = QPointF(origin) if origin is not None else QPointF(0, 0)
        self._parent_shape = parent_shape

    @property
    def origin(self) -> QPointF:
        return QPointF(self._origin)

    @origin.setter
    def origin(self, value: QPointF):
        if self._origin != value:
            self._origin = QPointF(value)
            self.transform_changed.emit()

    @property
    def parent_shape(self) -> VectorShape | None:
        return self._parent_shape

    @parent_shape.setter
    def parent_shape(self, value: VectorShape | None):
        if self._parent_shape is not value:
            self._parent_shape = value
            self.parent_shape_changed.emit(value)

    def move_by(self, offset: QPointF) -> None:
        self.origin += offset

    def local_to_scene(self, local_pos: QPointF) -> QPointF:
        """Convert local coordinate to scene coordinate."""
        return self._origin + local_pos

    def scene_to_local(self, scene_pos: QPointF) -> QPointF:
        """Convert scene coordinate to local coordinate."""
        return scene_pos - self._origin


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
            self._parent_shape = value
            self.parent_shape_changed.emit(value)

    @property
    def scene_pos(self) -> QPointF:
        return self._parent_shape.local_to_scene(self._local_pos)

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

    def move_by(self, offset: QPointF) -> None:
        self.local_pos += offset


class Point(VectorShape):
    def __init__(self, pos: QPointF, parent: QObject | None = None):
        # Origin is the point position.
        super().__init__(origin=pos, parent=parent)

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


class NodeBasedShape(VectorShape):
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
            parent: QObject | None = None
    ):
        super().__init__(origin=origin, parent_shape=parent_shape, parent=parent)

        self._nodes: list[VectorNode] = []
        for point in points:
            # Initialize without signals to avoid overhead during construction
            node = VectorNode.from_scene_pos(self, point, parent=self)
            self._nodes.append(node)

        self._is_completed = False

    @property
    def nodes(self) -> Sequence[VectorNode]:
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
    def last_node(self) -> VectorNode:
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

    def create_node(self, scene_pos: QPointF, index: int | None = None) -> VectorNode:
        """Create and insert node at index (appends if None)."""
        node = VectorNode.from_scene_pos(self, scene_pos, parent=self)
        self._insert_node(node, index)
        return node

    def create_node_local(self, local_pos: QPointF, index: int | None = None) -> VectorNode:
        """Create and insert node using local coordinates."""
        node = VectorNode.from_local_pos(self, local_pos, parent=self)
        self._insert_node(node, index)
        return node

    def _insert_node(self, node: VectorNode, index: int | None = None) -> None:
        """Insert node and emit signals."""
        if index is None:
            index = len(self._nodes)

        self.node_about_to_add.emit(node, index)
        self._nodes.insert(index, node)
        self.node_added.emit(node, index)

        self.structure_changed.emit()

    def remove_node(self, node: VectorNode) -> None:
        """Remove specific node by reference."""
        index = self._nodes.index(node)
        self.pop_node(index)

    def pop_node(self, index: int = -1) -> VectorNode:
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

    def closest_edge(
            self,
            scene_pos: QPointF,
            max_tolerance: float = math.inf,
    ) -> EdgeHitInfo | None:
        """Find the closest edge point to a scene point.
        Returns None if shape has < 2 nodes or exceeds tolerance."""
        if len(self._nodes) < 2:
            return None

        closest_hit: EdgeHitInfo | None = None
        min_squared_distance = max_tolerance ** 2

        for i in range(len(self._nodes) - 1):
            node_start_pos = self._nodes[i].scene_pos
            node_end_pos = self._nodes[i + 1].scene_pos

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
            parent: QObject | None = None,
    ):
        super().__init__(points, origin=origin, parent_shape=parent_shape, parent=parent)

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
