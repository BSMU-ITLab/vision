from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from bsmu.vision.core.data.vector.shapes import BaseShapeState, NodeBasedShape, VectorNode
from bsmu.vision.core.utils.geometry import GEOMETRY_EPSILON

if TYPE_CHECKING:
    from typing import Sequence

    from PySide6.QtCore import QObject

    from bsmu.vision.core.data.vector.shapes import ArcParam


@dataclass(slots=True)
class SnappedSpanState(BaseShapeState):
    start_arc: float = 0.0
    end_arc: float = 0.0


class SnappedNode(VectorNode):
    """A constrained node that moves only along its constraint shape.

    Uses a geometric anchor (_anchor_local_pos) that updates only on explicit user actions,
    ensuring the node stays pinned to the same physical location during parent mutations.
    """

    def __init__(
        self,
        parent_shape: SnappedSpan,
        arc_length: float,
        parent: QObject | None = None,
    ) -> None:
        # Initialize with a temporary position; actual position is computed lazily
        super().__init__(parent_shape, QPointF(0, 0), parent)

        # Clamp to 0.0 to protect against floating-point inaccuracies (e.g., -1e-15).
        self._arc_length = max(0.0, arc_length)
        self._cached_arc_param: ArcParam | None = None

        self._anchor_local_pos: QPointF = (
            self._compute_local_pos_from_arc()
            if self.constraint_shape is not None
            else QPointF()
        )

    @property
    def span(self) -> SnappedSpan:
        assert isinstance(self._parent_shape, SnappedSpan), 'Parent shape must be a SnappedSpan'
        return self._parent_shape

    @property
    def constraint_shape(self) -> NodeBasedShape:
        return self.span.parent_shape

    @property
    def arc_length(self) -> float:
        return self._arc_length

    @arc_length.setter
    def arc_length(self, value: float) -> None:
        """Set the arc length, clamping it to the valid path bounds.

        Triggers a position commit and updates the geometric anchor
        only if the change exceeds the geometric epsilon.
        """
        max_length = self.constraint_shape.length
        clamped_value = max(0.0, min(value, max_length))

        if abs(self._arc_length - clamped_value) > GEOMETRY_EPSILON:
            self._commit_position(clamped_value)

    def _commit_position(self, new_arc: float) -> None:
        """Commit a new arc length as the authoritative position.

        Invalidates the parametric cache, updates the geometric anchor
        to match the new length, and emits the `changed` signal.
        """
        self._arc_length = new_arc
        self._cached_arc_param = None

        self._anchor_local_pos = self._compute_local_pos_from_arc()

        self.changed.emit()

    def _adjust_to_parent(self, new_arc: float) -> None:
        """Adjust the arc length to match updated parent geometry or topology.

        Unlike `_commit_position`, the geometric anchor remains unchanged.
        Emits the `changed` signal only if the arc length or the parametric
        cache actually changed.
        """
        is_arc_changed = abs(self._arc_length - new_arc) > GEOMETRY_EPSILON
        has_cached_param = self._cached_arc_param is not None

        if is_arc_changed or has_cached_param:
            self._arc_length = new_arc
            self._cached_arc_param = None
            # _anchor_local_pos is intentionally preserved
            self.changed.emit()

    @property
    def segment_index(self) -> int:
        """Return the index of the path segment containing this node."""
        return self._compute_arc_param().segment_index

    @property
    def normalized_t(self) -> float:
        """Return the normalized position (0.0 to 1.0) within the segment."""
        return self._compute_arc_param().normalized_t

    @property
    def local_pos(self) -> QPointF:
        return self._compute_local_pos_from_arc()

    @local_pos.setter
    def local_pos(self, value: QPointF) -> None:
        """Set the local position by projecting the point onto the constraint path."""
        scene_pos = self.span.local_to_scene(value)
        self.project_onto_constraint(scene_pos)

    def update_drag_position(
            self,
            cursor_scene_pos: QPointF,
            _initial_local_pos: QPointF,
            _drag_start_scene_pos: QPointF,
    ) -> None:
        """Update position during a constrained drag operation.

        Ignores drag delta; strictly snaps to the constraint path
        based on the current cursor position.
        """
        self.project_onto_constraint(cursor_scene_pos)

    def project_onto_constraint(self, scene_pos: QPointF) -> None:
        """Project a given scene point onto the constraint path and update arc length.

        Silently ignores the operation if no valid projection is found.
        """
        new_arc = self.constraint_shape.map_point_to_arc_length(scene_pos)
        if new_arc is not None:
            self.arc_length = new_arc

    def _compute_arc_param(self) -> ArcParam:
        """Compute and cache the parametric position from the current arc length."""
        if self._cached_arc_param is None:
            self._cached_arc_param = self.constraint_shape.map_arc_length_to_param(self._arc_length)
        return self._cached_arc_param

    def _compute_local_pos_from_arc(self) -> QPointF:
        """Compute the node's position in the local coordinate space of the SnappedSpan."""
        arc_param = self._compute_arc_param()
        nodes = self.constraint_shape.nodes

        if not nodes or len(nodes) < 2:
            return QPointF(0.0, 0.0)

        segment_index = arc_param.segment_index

        p1_scene = nodes[segment_index].scene_pos
        p2_scene = nodes[segment_index + 1].scene_pos

        p1_local = self.span.scene_to_local(p1_scene)
        p2_local = self.span.scene_to_local(p2_scene)

        normalized_t = max(0.0, min(1.0, arc_param.normalized_t))
        return p1_local + (p2_local - p1_local) * normalized_t

    def reproject_from_anchor(self) -> None:
        """Project the frozen geometric anchor onto the updated constraint path.

        The anchor remains unmodified, preserving the relative tissue location
        across parent topology or geometry changes.
        """
        if self.constraint_shape.length < GEOMETRY_EPSILON:
            self._adjust_to_parent(0.0)
            return

        anchor_scene_pos = self.span.local_to_scene(self._anchor_local_pos)
        new_arc = self.constraint_shape.map_point_to_arc_length(anchor_scene_pos)
        if new_arc is None:
            new_arc = max(0.0, min(self._arc_length, self.constraint_shape.length))

        self._adjust_to_parent(new_arc)


class SnappedSpan(NodeBasedShape[SnappedNode]):
    """A constrained annotation span between two points on a parent NodeBasedShape.

    Inherits NodeBasedShape for seamless PointerTool/SelectionManager compatibility.
    Uses arc_length as the primary state for robust topological stability.
    """

    def __init__(
            self,
            points: Sequence[QPointF] = (),
            origin: QPointF | None = None,
            parent_shape: NodeBasedShape | None = None,
            inherit_transform: bool = False,
            parent: QObject | None = None,
    ) -> None:
        assert parent_shape is not None, 'parent_shape is required for SnappedSpan'
        assert not isinstance(parent_shape, SnappedSpan), 'SnappedSpan cannot use another SnappedSpan as parent_shape.'

        # Defer parent_shape assignment to avoid triggering hooks before nodes are instantiated.
        super().__init__(
            points=points,
            origin=origin,
            parent_shape=None,
            inherit_transform=inherit_transform,
            parent=parent,
        )

        self._start_node: SnappedNode = self.nodes[0]
        self._end_node: SnappedNode = self.nodes[1]

        # Assign parent after nodes exist
        self.parent_shape = parent_shape

        # Forward node state changes to the shape's geometry signal
        self._start_node.changed.connect(self.geometry_changed.emit)
        self._end_node.changed.connect(self.geometry_changed.emit)

    def _create_nodes(self, points: Sequence[QPointF]) -> list[SnappedNode]:
        """Create exactly two constrained SnappedNodes.

        The 'points' argument is ignored, as initial positions are defined
        by arc_length upon explicit assignment.
        """
        return [
            SnappedNode(parent_shape=self, arc_length=0.0),
            SnappedNode(parent_shape=self, arc_length=0.0),
        ]

    def _on_parent_shape_about_to_change(self) -> None:
        parent_shape = self.parent_shape
        if parent_shape is not None:
            parent_shape.transform_changed.disconnect(self._on_parent_transform_changed)
            parent_shape.geometry_changed.disconnect(self._on_parent_geometry_changed)
            parent_shape.structure_changed.disconnect(self._on_parent_structure_changed)

    def _on_parent_shape_changed(self) -> None:
        parent_shape = self.parent_shape
        if parent_shape is not None:
            parent_shape.transform_changed.connect(self._on_parent_transform_changed)
            parent_shape.geometry_changed.connect(self._on_parent_geometry_changed)
            parent_shape.structure_changed.connect(self._on_parent_structure_changed)

            self._reproject_nodes_from_anchor()

    @property
    def allows_individual_node_deletion(self) -> bool:
        """SnappedSpan has a fixed structure of exactly two nodes."""
        return False

    @property
    def allows_node_insertion(self) -> bool:
        """SnappedSpan has a fixed structure of exactly two nodes."""
        return False

    def _reproject_nodes_from_anchor(self) -> None:
        """Reproject all span nodes onto the current constraint path."""
        for node in self.nodes:
            node.reproject_from_anchor()

    def _on_parent_transform_changed(self) -> None:
        self._reproject_nodes_from_anchor()

    def _on_parent_geometry_changed(self) -> None:
        self._reproject_nodes_from_anchor()

    def _on_parent_structure_changed(self) -> None:
        self._reproject_nodes_from_anchor()

    @property
    def start_node(self) -> SnappedNode:
        return self._start_node

    @property
    def end_node(self) -> SnappedNode:
        return self._end_node

    @property
    def length(self) -> float:
        """Return the arc-length distance between the start and end nodes."""
        return abs(self._end_node.arc_length - self._start_node.arc_length)

    @property
    def is_parent_valid(self) -> bool:
        return self.parent_shape is not None and len(self.parent_shape.nodes) >= 2

    def create_node(self, scene_pos: QPointF, index: int | None = None) -> SnappedNode:
        raise RuntimeError('Operation not supported: SnappedSpan has a fixed structure of exactly two nodes.')

    def remove_node(self, node: SnappedNode) -> None:
        raise RuntimeError('Operation not supported: SnappedSpan nodes cannot be removed.')

    def pop_node(self, index: int = -1) -> SnappedNode:
        raise RuntimeError('Operation not supported: SnappedSpan nodes cannot be removed.')

    def clear_nodes(self) -> None:
        raise RuntimeError('Operation not supported: SnappedSpan nodes cannot be cleared.')

    def move_by(self, offset: QPointF) -> None:
        raise RuntimeError(
            'Operation not supported: SnappedSpan is constrained to a 1D path. '
            'Use apply_drag with arc_length deltas instead of 2D offsets.'
        )

    def capture_state(self) -> SnappedSpanState:
        """Capture the current arc lengths of both nodes for Undo/Redo."""
        return SnappedSpanState(
            start_arc=self.start_node.arc_length,
            end_arc=self.end_node.arc_length,
        )

    def restore_state(self, state: BaseShapeState) -> None:
        """Restore the arc lengths of both nodes from a captured state."""
        # Type narrowing for safety, though the undo system guarantees the correct type
        if not isinstance(state, SnappedSpanState):
            raise TypeError(f'Expected SnappedSpanState, got {type(state).__name__}')

        self.start_node.arc_length = state.start_arc
        self.end_node.arc_length = state.end_arc

    def calculate_grab_value(self, cursor_scene_pos: QPointF) -> float:
        """Calculate the initial arc length for a drag operation.

        Projects the cursor onto the constraint path. Falls back to the
        current start node arc length if no valid projection is found.
        """
        new_arc = self.parent_shape.map_point_to_arc_length(cursor_scene_pos)
        return new_arc if new_arc is not None else self.start_node.arc_length

    def apply_drag(self, cursor_scene_pos: QPointF, grab_arc: float) -> float:
        """Apply drag movement and return the new grab arc for the next frame.

        Moves the span along the constraint path while preserving its length
        and orientation.
        """
        parent_shape = self.parent_shape
        if parent_shape is None or parent_shape.length < GEOMETRY_EPSILON:
            return grab_arc

        current_cursor_arc = parent_shape.map_point_to_arc_length(cursor_scene_pos)
        if current_cursor_arc is None:
            return grab_arc

        span_length = self.length
        constraint_length = parent_shape.length
        is_forward_oriented = self.end_node.arc_length >= self.start_node.arc_length

        delta_arc = current_cursor_arc - grab_arc
        new_start = self.start_node.arc_length + delta_arc
        new_end = new_start + (span_length if is_forward_oriented else -span_length)

        if is_forward_oriented:
            new_start = max(0.0, min(new_start, constraint_length - span_length))
            new_end = new_start + span_length
        else:
            new_end = max(0.0, min(new_end, constraint_length - span_length))
            new_start = new_end + span_length

        self.start_node.arc_length = new_start
        self.end_node.arc_length = new_end

        return current_cursor_arc

    def scene_path_points(self) -> list[QPointF]:
        """Return scene vertices along the parent path between the span nodes.

        Ensures the path is always built in forward traversal order
        (from lower to higher arc length), regardless of creation sequence.
        """
        if not self.is_parent_valid:
            return []

        parent_nodes = self.parent_shape.nodes

        # Determine traversal order based on arc length progression
        first_node = self.start_node
        last_node = self.end_node

        is_reversed = (
                first_node.segment_index > last_node.segment_index or
                (first_node.segment_index == last_node.segment_index and
                 first_node.normalized_t > last_node.normalized_t)
        )
        if is_reversed:
            first_node, last_node = last_node, first_node

        first_segment_index = first_node.segment_index
        last_segment_index = last_node.segment_index

        # Build the path: start point, intermediate full nodes, end point
        points: list[QPointF] = [first_node.scene_pos]

        # Add all intermediate parent nodes between the start and end segments
        for i in range(first_segment_index + 1, last_segment_index + 1):
            points.append(parent_nodes[i].scene_pos)

        points.append(last_node.scene_pos)

        return points
