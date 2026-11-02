from __future__ import annotations

import logging

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.selection import SelectionManager
from bsmu.vision.plugins.visualizers.raster import RasterVisualizer, RasterVisualizerPlugin
from bsmu.vision.widgets.mdi.windows.image.layered import VolumeSliceImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer


class VolumeRasterVisualizerPlugin(RasterVisualizerPlugin):
    def __init__(self):
        super().__init__(VolumeRasterVisualizer)


class VolumeRasterVisualizer(RasterVisualizer):
    _DATA_TYPES = (Raster, )

    @classmethod
    def can_handle(cls, data: Raster) -> bool:
        return super().can_handle(data) and data.n_dims == 3

    def _visualize_data(self, data: Raster):
        logging.info('Visualize volume raster')

        layered_image = LayeredImage()  # TODO: migrate to LayeredData
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
