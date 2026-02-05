from __future__ import annotations

import logging

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.image import VolumeImage
from bsmu.vision.core.selection import SelectionManager
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import VolumeSliceImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer


class VolumeImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self):
        super().__init__(VolumeImageVisualizer)


class VolumeImageVisualizer(DataVisualizer):
    _DATA_TYPES = (VolumeImage, )

    def _visualize_data(self, data: VolumeImage):
        logging.info('Visualize volume image')

        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)

        viewer_sub_windows = []
        selection_manager = SelectionManager()
        for plane_axis in PlaneAxis:
            image_viewer = VolumeSliceImageViewer(plane_axis, None, layered_image, selection_manager)
            sub_window = VolumeSliceImageViewerSubWindow(image_viewer)
            self.mdi.add_sub_window(sub_window)
            sub_window.show()
            viewer_sub_windows.append(sub_window)
        return viewer_sub_windows
