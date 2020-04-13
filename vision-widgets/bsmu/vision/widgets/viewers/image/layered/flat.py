from __future__ import annotations

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, ImageLayerView


class FlatImageLayerView(ImageLayerView):
    def __init__(self, image_layer: ImageLayer, visible: bool = True,
                 opacity: float = ImageLayerView.DEFAULT_LAYER_OPACITY):
        super().__init__(image_layer, visible, opacity)

        self._update_image_view()

        self.slice_number = None

    @property
    def flat_image(self) -> FlatImage:
        return self.image_layer.image

    def _create_image_view(self) -> FlatImage:
        return self.flat_image


class LayeredFlatImageViewer(LayeredImageViewer):
    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

        self._add_layer_views_from_model()

    def _add_layer_view_from_model(self, image_layer: ImageLayer) -> FlatImageLayerView:
        layer_view = FlatImageLayerView(image_layer)
        self._add_layer_view(layer_view)
        return layer_view
