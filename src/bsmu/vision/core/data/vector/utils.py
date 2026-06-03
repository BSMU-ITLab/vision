from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable

    from bsmu.vision.core.data.vector.shapes import VectorShape


def flatten_shapes_with_descendants(shapes: Iterable[VectorShape]) -> list[VectorShape]:
    """
    Flatten shape hierarchies into a deduplicated post-order list.
    Guarantees that children appear before their parents, making it safe
    for cascade deletion or reversed restoration.
    """
    result: list[VectorShape] = []
    visited: set[VectorShape] = set()

    for shape in shapes:
        if shape in visited:
            continue

        # Add descendants first (already in post-order)
        for descendant in shape.collect_descendants():
            if descendant not in visited:
                visited.add(descendant)
                result.append(descendant)

        # Then add the shape itself
        visited.add(shape)
        result.append(shape)

    return result
