from __future__ import annotations

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, _ImageLayerView


class _FlatImageLayerView(_ImageLayerView):
    def __init__(self, image_layer: ImageLayer, visible: bool = True,
                 opacity: float = _ImageLayerView.DEFAULT_LAYER_OPACITY):
        super().__init__(image_layer, visible, opacity)

    def _create_image_view(self) -> FlatImage:
        return self.image_layer.image

    def _on_layer_image_updated(self, image: Image):
        print('_FlatImageLayerView _on_layer_image_updated (image array updated or layer image changed)')
        self._image_view = self._create_image_view()

        super()._on_layer_image_updated(image)


class LayeredFlatImageViewer(LayeredImageViewer):
    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

    def _add_layer_view_from_layer(self, image_layer: ImageLayer) -> _FlatImageLayerView:
        layer_view = _FlatImageLayerView(image_layer)
        self._add_layer_view(layer_view)
        return layer_view
