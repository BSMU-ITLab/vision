from __future__ import annotations

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.image.base import VolumeImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import VolumeSliceImageViewerSubWindow, LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer
from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer


class LayeredImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self):
        super().__init__(LayeredImageVisualizer)


class LayeredImageVisualizer(DataVisualizer):
    _DATA_TYPES = (LayeredImage, )

    def _visualize_data(self, data: LayeredImage):
        print('visualize layered image')

        viewer_sub_windows = []
        if data.layers[0].image.n_dims == VolumeImage.n_dims:
            for plane_axis in PlaneAxis:
                image_viewer = VolumeSliceImageViewer(plane_axis, None, data)
                sub_window = VolumeSliceImageViewerSubWindow(image_viewer)
                image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
                viewer_sub_windows.append(sub_window)
        else:
            image_viewer = LayeredFlatImageViewer(data)
            sub_window = LayeredImageViewerSubWindow(image_viewer)
            image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
            viewer_sub_windows.append(sub_window)

        for sub_window in viewer_sub_windows:
            self.mdi.addSubWindow(sub_window)
            sub_window.show()

        return viewer_sub_windows
