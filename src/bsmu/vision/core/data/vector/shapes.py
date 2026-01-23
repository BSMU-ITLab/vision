from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QObject, QPointF, Signal

from bsmu.vision.core.utils.geometry import GeometryUtils


class VectorShape(QObject):
    changed = Signal()  # emitted when geometry changes

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)


class Point(VectorShape):
    def __init__(self, pos: QPointF, parent: QObject | None = None):
        super().__init__(parent)

        self._pos: QPointF = pos

    @property
    def pos(self) -> QPointF:
        return self._pos

    @pos.setter
    def pos(self, value: QPointF):
        if self._pos != value:
            self._pos = value
            self.changed.emit()


@dataclass(frozen=True)
class ClosestPolylinePointInfo:
    point: QPointF | None = None
    segment_index: int | None = None
    squared_distance: float | None = None


class Polyline(VectorShape):
    point_appended = Signal(QPointF)
    end_point_removed = Signal(QPointF)

    completed = Signal()

    _points: list[QPointF]

    def __init__(
            self,
            points: Iterable[QPointF] = (),
            *,
            copy: bool = True,
            parent: QObject | None = None
    ):
        super().__init__(parent)

        if copy:
            self._points = list(points)
        else:
            self._points = points if isinstance(points, list) else list(points)

        self._is_completed = False

    @property
    def points(self) -> list[QPointF]:
        return self._points.copy()

    @property
    def end_point(self) -> QPointF:
        return self._points[-1]

    @property
    def is_empty(self) -> bool:
        return not self._points

    @property
    def is_completed(self) -> bool:
        return self._is_completed

    @property
    def is_draft(self) -> bool:
        return not self._is_completed

    @property
    def length(self) -> float:
        if len(self._points) < 2:
            return 0.0

        return sum(
            GeometryUtils.distance(self._points[i], self._points[i + 1])
            for i in range(len(self._points) - 1)
        )

    def append_point(self, point: QPointF):
        self._points.append(point)
        self.point_appended.emit(point)

    def remove_end_point(self):
        if self._points:
            end_point = self._points.pop()
            self.end_point_removed.emit(end_point)

    def complete(self):
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

        if len(self._points) == 1:
            return ClosestPolylinePointInfo(point=self.end_point, segment_index=0)

        closest_point: QPointF | None = None
        segment_index: int | None = None
        min_squared_distance: float = math.inf

        # Check each segment of the polyline
        for i in range(len(self._points) - 1):
            segment_start = self._points[i]
            segment_end = self._points[i + 1]

            segment_closest_point = GeometryUtils.closest_point_on_segment(segment_start, segment_end, point)
            squared_distance = GeometryUtils.squared_distance(point, segment_closest_point)

            if squared_distance < min_squared_distance:
                min_squared_distance = squared_distance
                closest_point = segment_closest_point
                segment_index = i

        return ClosestPolylinePointInfo(
            point=closest_point, segment_index=segment_index, squared_distance=min_squared_distance)
