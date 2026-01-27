from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bsmu.vision.actors.shape import VectorShapeActor, PointActor, PolylineActor
from bsmu.vision.core.data.vector.shapes import VectorShape, Point, Polyline


ShapeType = type[VectorShape]
ShapeActorFactory = Callable[[Any], VectorShapeActor]
_SHAPE_ACTOR_REGISTRY: dict[ShapeType, ShapeActorFactory] = {}


def register_shape_actor(shape_cls: ShapeType, factory: ShapeActorFactory) -> None:
    if shape_cls in _SHAPE_ACTOR_REGISTRY:
        raise ValueError(f'Actor already registered for shape type: {shape_cls}')
    _SHAPE_ACTOR_REGISTRY[shape_cls] = factory


def create_shape_actor(shape: VectorShape) -> VectorShapeActor | None:
    for cls in type(shape).__mro__:
        factory = _SHAPE_ACTOR_REGISTRY.get(cls)
        if factory is not None:
            return factory(shape)
    return None


# Register built-in actors
register_shape_actor(Point, PointActor)
register_shape_actor(Polyline, PolylineActor)
