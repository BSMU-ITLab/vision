from __future__ import annotations

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


class LayeredFlatImageViewer(LayeredImageViewer):
    def __init__(self, data: FlatImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

        if self.data is not None:
            print('layer shape:', self.data.array.shape)
            self.add_layer(self.data)
