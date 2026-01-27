from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bsmu.vision.actors.layer import LayerActor, RasterLayerActor, VectorLayerActor
from bsmu.vision.core.layers import Layer, RasterLayer, VectorLayer


LayerType = type[Layer]
LayerActorFactory = Callable[[Any], LayerActor]
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


# Register built-in actors
register_layer_actor(RasterLayer, RasterLayerActor)
register_layer_actor(VectorLayer, VectorLayerActor)
