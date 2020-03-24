from __future__ import annotations

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, _ImageLayerView


class LayeredFlatImageViewer(LayeredImageViewer):
    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

        if self.data is not None:
            for layer in data.layers:
                self._add_layer_view_from_layer(layer)

    def _add_layer_view_from_layer(self, image_layer: ImageLayer) -> _ImageLayerView:
        layer_view = _ImageLayerView(image_layer)
        self._add_layer_view(layer_view)
        return layer_view
