from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers.image.base import ImageVisualizerPlugin, ImageVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.viewers.image.settings import ImageViewerSettingsPlugin


class FlatImageVisualizerPlugin(ImageVisualizerPlugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'image_viewer_settings_plugin': 'bsmu.vision.plugins.viewers.image.settings.ImageViewerSettingsPlugin',
    }

    def __init__(self, image_viewer_settings_plugin: ImageViewerSettingsPlugin):
        super().__init__(FlatImageVisualizer, image_viewer_settings_plugin)


class FlatImageVisualizer(ImageVisualizer):
    _DATA_TYPES = (FlatImage, )

    def _visualize_data(self, data: FlatImage):
        logging.info('Visualize flat image')

        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)
        image_viewer = LayeredFlatImageViewer(layered_image, self.settings)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        # self._mdi.addSubWindow(sub_window)
        self._mdi.add_dock_widget(sub_window, focusable=True)
        sub_window.show()
        return [sub_window]
