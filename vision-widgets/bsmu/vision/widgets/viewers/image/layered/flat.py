from __future__ import annotations

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


class LayeredFlatImageViewer(LayeredImageViewer):
    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

        if self.data is not None:
            for layer in data.layers:
                self. add_displayed_layer_from_layer(layer)
