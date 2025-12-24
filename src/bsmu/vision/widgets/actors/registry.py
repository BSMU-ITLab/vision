from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bsmu.vision.core.data.vector.shapes import VectorShape, Point, Polyline
from bsmu.vision.core.layers import Layer, RasterLayer
from bsmu.vision.widgets.actors.layer import LayerActor, RasterLayerActor
from bsmu.vision.widgets.actors.shape import VectorShapeActor, PointActor, PolylineActor


# --- Layer Actor Registry ---
LayerType = type[Layer]
LayerActorFactory = Callable[[Layer], LayerActor]
_LAYER_ACTOR_REGISTRY: dict[LayerType, LayerActorFactory] = {}


def register_layer_actor(layer_cls: LayerType, factory: LayerActorFactory) -> None:
    if layer_cls in _LAYER_ACTOR_REGISTRY:
        raise ValueError(f'Actor already registered for layer type: {layer_cls}')
    _LAYER_ACTOR_REGISTRY[layer_cls] = factory


def create_layer_actor(layer: Layer) -> LayerActor | None:
    for cls in type(layer).__mro__:
        factory = _LAYER_ACTOR_REGISTRY.get(cls)
        if factory is not None:
            return factory(layer)
    return None


# --- Shape Actor Registry ---
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
register_layer_actor(RasterLayer, RasterLayerActor)

register_shape_actor(Point, PointActor)
register_shape_actor(Polyline, PolylineActor)
