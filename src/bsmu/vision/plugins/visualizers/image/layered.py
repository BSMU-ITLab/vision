from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.image import VolumeImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.selection import SelectionManager
from bsmu.vision.plugins.visualizers import DataVisualizerPlugin, DataVisualizer
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

        selection_manager = SelectionManager()
        viewer_sub_windows = []
        if data.base_layer.image.n_dims == VolumeImage.n_dims:
            viewers = [
                VolumeSliceImageViewer(plane_axis, None, data, selection_manager, self.settings)
                for plane_axis in PlaneAxis
            ]
        else:
            viewers = [LayeredFlatImageViewer(data, selection_manager, self.settings)]

        for viewer in viewers:
            if isinstance(viewer, VolumeSliceImageViewer):
                sub_window = VolumeSliceImageViewerSubWindow(viewer)
            else:
                sub_window = LayeredImageViewerSubWindow(viewer)

            sub_window.setWindowTitle(viewer.data.display_name)
            viewer.data_name_changed.connect(sub_window.setWindowTitle)

            viewer_sub_windows.append(sub_window)

        for sub_window in viewer_sub_windows:
            self.mdi.add_sub_window(sub_window)
            sub_window.show()

        return viewer_sub_windows
