from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from PySide6.QtCore import QObject, QPointF, Signal

from bsmu.vision.core.utils.geometry import GeometryUtils


class VectorShape(QObject):
    changed = Signal()  # Emitted when geometry changes

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)


class VectorNode(QObject):
    pos_changed = Signal(QPointF)  # Emit new position

    def __init__(self, parent_shape: VectorShape, pos: QPointF, parent: QObject | None = None):
        super().__init__(parent)

        self._parent_shape = parent_shape
        self._pos = QPointF(pos)

    @property
    def parent_shape(self) -> VectorShape:
        return self._parent_shape

    @property
    def pos(self) -> QPointF:
        return QPointF(self._pos)  # Return copy to prevent external mutation

    @pos.setter
    def pos(self, value: QPointF):
        if self._pos != value:
            self._pos = QPointF(value)
            self.pos_changed.emit(self._pos)


class Point(VectorShape):
    pos_changed = Signal(QPointF)

    def __init__(self, pos: QPointF, parent: QObject | None = None):
        super().__init__(parent)

        self._pos = QPointF(pos)

    @property
    def pos(self) -> QPointF:
        return QPointF(self._pos)

    @pos.setter
    def pos(self, value: QPointF):
        if self._pos != value:
            self._pos = QPointF(value)
            self.pos_changed.emit(self._pos)
            self.changed.emit()


@dataclass(frozen=True)
class ClosestPolylinePointInfo:
    point: QPointF | None = None
    segment_index: int | None = None
    squared_distance: float | None = None  # Squared distance from the query point to the closest point on the polyline


class Polyline(VectorShape):
    node_added = Signal(VectorNode)
    last_node_removed = Signal(VectorNode)
    completed = Signal()

    def __init__(
            self,
            points: Iterable[QPointF] = (),
            parent: QObject | None = None,
    ):
        super().__init__(parent)

        self._nodes: list[VectorNode] = []
        for point in points:
            self._append_node(point)

        self._is_completed = False

    @property
    def nodes(self) -> Sequence[VectorNode]:
        """Immutable sequence of nodes. Do not modify."""
        return self._nodes

    @property
    def points(self) -> list[QPointF]:
        return [node.pos for node in self._nodes]

    @property
    def is_empty(self) -> bool:
        return not self._nodes

    @property
    def is_completed(self) -> bool:
        return self._is_completed

    @property
    def is_draft(self) -> bool:
        return not self._is_completed

    @property
    def last_node(self) -> VectorNode:
        return self._nodes[-1]

    @property
    def length(self) -> float:
        if len(self._nodes) < 2:
            return 0.0

        return sum(
            GeometryUtils.distance(self._nodes[i].pos, self._nodes[i + 1].pos)
            for i in range(len(self._nodes) - 1)
        )

    def add_node(self, pos: QPointF) -> VectorNode:
        node = self._append_node(pos)
        self.node_added.emit(node)
        return node

    def _append_node(self, pos: QPointF) -> VectorNode:
        node = VectorNode(self, pos, parent=self)
        self._nodes.append(node)
        return node

    def remove_last_node(self) -> VectorNode | None:
        if self._nodes:
            node = self._nodes.pop()
            self.last_node_removed.emit(node)
            return node
        return None

    def complete(self) -> None:
        if not self._is_completed:
            self._is_completed = True
            self.completed.emit()

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
            return ClosestPolylinePointInfo(point=self.last_node.pos, segment_index=0)

        closest_point: QPointF | None = None
        segment_index: int | None = None
        min_squared_distance: float = math.inf

        # Check each segment of the polyline
        for i in range(len(self._nodes) - 1):
            segment_start = self._nodes[i].pos
            segment_end = self._nodes[i + 1].pos

            segment_closest_point = GeometryUtils.closest_point_on_segment(segment_start, segment_end, point)
            squared_distance = GeometryUtils.squared_distance(point, segment_closest_point)

            if squared_distance < min_squared_distance:
                min_squared_distance = squared_distance
                closest_point = segment_closest_point
                segment_index = i

        return ClosestPolylinePointInfo(
            point=closest_point, segment_index=segment_index, squared_distance=min_squared_distance)
