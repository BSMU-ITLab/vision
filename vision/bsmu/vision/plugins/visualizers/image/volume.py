from __future__ import annotations

from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer
from bsmu.vision_core.constants import PlaneAxis
from bsmu.vision_core.image import VolumeImage


class VolumeImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self, app: App):
        super().__init__(app, VolumeImageVisualizer)


class VolumeImageVisualizer(DataVisualizer):
    _DATA_TYPES = (VolumeImage, )

    def _visualize_data(self, data: VolumeImage):
        print('visualize volume image')

        for plane_axis in PlaneAxis:
            image_viewer = VolumeSliceImageViewer(plane_axis, data)
            sub_window = LayeredImageViewerSubWindow(image_viewer)
            self.mdi.addSubWindow(sub_window)
            sub_window.show()
