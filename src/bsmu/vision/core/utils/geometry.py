from __future__ import annotations

import math

from PySide6.QtCore import QPointF


class GeometryUtils:
    @staticmethod
    def squared_distance(p1: QPointF, p2: QPointF) -> float:
        diff = p2 - p1
        return diff.x() ** 2 + diff.y() ** 2

    @classmethod
    def distance(cls, p1: QPointF, p2: QPointF) -> float:
        return math.sqrt(cls.squared_distance(p1, p2))

    @staticmethod
    def closest_point_on_segment(segment_start: QPointF, segment_end: QPointF, query_point: QPointF) -> QPointF:
        """Find the closest point on the line segment [segment_start, segment_end] to query_point."""
        segment_vector = segment_end - segment_start
        segment_length_squared = segment_vector.x() ** 2 + segment_vector.y() ** 2

        # If segment is a single point
        if segment_length_squared == 0:
            return segment_start

        # Vector from segment_start to query_point
        start_to_query = query_point - segment_start

        # Projection (dot product) normalized by segment_length_squared
        projection_scalar = QPointF.dotProduct(start_to_query, segment_vector) / segment_length_squared
        # Clamp the scalar to stay within the segment bounds [0, 1]
        projection_scalar = max(0, min(1, projection_scalar))

        # Calculate the closest point
        return segment_start + segment_vector * projection_scalar
