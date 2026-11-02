from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers.raster import RasterVisualizerPlugin, RasterVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.viewers.image.settings import ImageViewerSettingsPlugin


class FlatRasterVisualizerPlugin(RasterVisualizerPlugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'image_viewer_settings_plugin': 'bsmu.vision.plugins.viewers.image.settings.ImageViewerSettingsPlugin',
    }

    def __init__(self, image_viewer_settings_plugin: ImageViewerSettingsPlugin):
        super().__init__(FlatRasterVisualizer, image_viewer_settings_plugin)


class FlatRasterVisualizer(RasterVisualizer):
    _DATA_TYPES = (Raster, )

    @classmethod
    def can_handle(cls, data: Raster) -> bool:
        return super().can_handle(data) and data.n_dims == 2

    def _visualize_data(self, data: Raster):
        logging.info('Visualize flat raster')

        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)
        image_viewer = LayeredFlatImageViewer(layered_image, settings=self.settings)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.add_sub_window(sub_window)
        sub_window.show()
        return [sub_window]
