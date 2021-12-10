from __future__ import annotations

from functools import partial
from typing import List, Union

from bsmu.vision.widgets.viewers.image.layered.base import ImageLayerView
from bsmu.vision.widgets.visibility import VisibilityWidget


class LayerVisibilityWidget(VisibilityWidget):
    def __init__(self, layer_views: Union[ImageLayerView, List[ImageLayerView]],
                 embedded: bool = False, parent: QWidget = None):
        super().__init__(embedded=embedded, parent=parent)

        self._layer_views = [layer_views] if isinstance(layer_views, ImageLayerView) else layer_views

        first_layer_view = self._layer_views[0]
        self.checked = first_layer_view.visible
        self.opacity = first_layer_view.opacity

        for layer_view in self._layer_views:
            self.toggled.connect(partial(self._change_layer_view_visibility, layer_view))
            self.opacity_changed.connect(partial(self._change_layer_view_opacity, layer_view))

            layer_view.visibility_changed.connect(self._change_visibility)
            layer_view.opacity_changed.connect(self._change_opacity)

    def _change_layer_view_visibility(self, layer_view: ImageLayerView, visible: bool):
        layer_view.visible = visible

    def _change_layer_view_opacity(self, layer_view: ImageLayerView, opacity: float):
        layer_view.opacity = opacity

    def _change_visibility(self, visible: bool):
        self.checked = visible

    def _change_opacity(self, opacity: float):
        self.opacity = opacity
