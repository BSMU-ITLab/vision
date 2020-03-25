from __future__ import annotations

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, _ImageLayerView


class _FlatImageLayerView(_ImageLayerView):
    def __init__(self, image_layer: FlatImageLayer, image_view: np.ndarray = None, visible: bool = True,
                 opacity: float = _ImageLayerView.DEFAULT_LAYER_OPACITY):
        super().__init__(image_layer, image_view, visible, opacity)

    def _on_layer_image_updated(self, image: Image):
        print('_FlatImageLayerView _on_layer_image_updated (image array updated or layer image changed)')
        self._image_view = self.image_layer.image

        super()._on_layer_image_updated(image)


class LayeredFlatImageViewer(LayeredImageViewer):
    def __init__(self, data: LayeredImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

        if self.data is not None:
            for layer in data.layers:
                self._add_layer_view_from_layer(layer)

    def _add_layer_view_from_layer(self, image_layer: ImageLayer) -> _ImageLayerView:
        layer_view = _FlatImageLayerView(image_layer)
        self._add_layer_view(layer_view)
        return layer_view
