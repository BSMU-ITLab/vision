from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.image.base import VolumeImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import VolumeSliceImageViewerSubWindow, LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer
from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.viewers.image.settings import ImageViewerSettingsPlugin


class LayeredImageVisualizerPlugin(DataVisualizerPlugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'image_viewer_settings_plugin': 'bsmu.vision.plugins.viewers.image.settings.ImageViewerSettingsPlugin',
    }

    def __init__(self, image_viewer_settings_plugin: ImageViewerSettingsPlugin):
        super().__init__(LayeredImageVisualizer, image_viewer_settings_plugin)


class LayeredImageVisualizer(DataVisualizer):
    _DATA_TYPES = (LayeredImage, )

    def _visualize_data(self, data: LayeredImage):
        logging.info('Visualize layered image')

        viewer_sub_windows = []
        if data.layers[0].image.n_dims == VolumeImage.n_dims:
            for plane_axis in PlaneAxis:
                image_viewer = VolumeSliceImageViewer(plane_axis, None, data, self.settings)
                sub_window = VolumeSliceImageViewerSubWindow(image_viewer)
                image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
                viewer_sub_windows.append(sub_window)
        else:
            image_viewer = LayeredFlatImageViewer(data, self.settings)
            sub_window = LayeredImageViewerSubWindow(image_viewer)
            image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
            viewer_sub_windows.append(sub_window)

        for sub_window in viewer_sub_windows:
            self.mdi.addSubWindow(sub_window)
            sub_window.show()

        return viewer_sub_windows
