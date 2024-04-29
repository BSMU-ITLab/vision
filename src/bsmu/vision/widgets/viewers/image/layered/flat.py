from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, ImageLayerView

if TYPE_CHECKING:
    from bsmu.vision.core.image.base import FlatImage
    from bsmu.vision.core.image.layered import ImageLayer, LayeredImage
    from bsmu.vision.widgets.viewers.image.layered.base import ImageViewerSettings


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
    def __init__(self, data: LayeredImage = None, settings: ImageViewerSettings = None):
        super().__init__(data, settings)

    def _add_layer_view_from_model(self, image_layer: ImageLayer, layer_index: int = None) -> FlatImageLayerView:
        layer_view = FlatImageLayerView(image_layer, image_layer.visibility.visible, image_layer.visibility.opacity)
        self._add_layer_view(layer_view, layer_index)
        return layer_view
