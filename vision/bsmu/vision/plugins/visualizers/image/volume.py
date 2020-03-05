from __future__ import annotations

from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer
from bsmu.vision.widgets.viewers.image.slice import VolumeSliceImageViewer
from bsmu.vision_core.constants import PlaneAxis
from bsmu.vision_core.dicom import Dicom
from bsmu.vision_core.image import FlatImage, VolumeImage


class VolumeImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self, app: App):
        super().__init__(app, VolumeImageVisualizer)


class VolumeImageVisualizer(DataVisualizer):
    _DATA_TYPES = (VolumeImage, )

    def _visualize_data(self, image: VolumeImage):
        print('visualize volume image')


        print('===', image.array.min(), image.array.max())


        # lutvalue = util.piecewise(data,
        #                           [data <= (level - 0.5 - (window - 1) / 2),
        #                            data > (level - 0.5 + (window - 1) / 2)],
        #                           [0, 255, lambda data:
        #                           ((data - (level - 0.5)) / (window - 1) + 0.5) *
        #                           (255 - 0)])


        # a = FlatImage(slice_a)

        image_viewer = VolumeSliceImageViewer(PlaneAxis.X, image)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()


        image_viewer = VolumeSliceImageViewer(PlaneAxis.Y, image)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        image_viewer = VolumeSliceImageViewer(PlaneAxis.Z, image)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        return sub_window
