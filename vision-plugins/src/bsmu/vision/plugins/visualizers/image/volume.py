from __future__ import annotations

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.image.base import VolumeImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import VolumeSliceImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer


class VolumeImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self):
        super().__init__(VolumeImageVisualizer)


class VolumeImageVisualizer(DataVisualizer):
    _DATA_TYPES = (VolumeImage, )

    def _visualize_data(self, data: VolumeImage):
        print('visualize volume image')

        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)

        viewer_sub_windows = []
        for plane_axis in PlaneAxis:
            image_viewer = VolumeSliceImageViewer(plane_axis, None, layered_image)
            sub_window = VolumeSliceImageViewerSubWindow(image_viewer)
            self.mdi.addSubWindow(sub_window)
            sub_window.show()
            viewer_sub_windows.append(sub_window)
        return viewer_sub_windows
