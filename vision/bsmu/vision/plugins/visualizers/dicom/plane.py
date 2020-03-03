from __future__ import annotations

from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer
from bsmu.vision_core.dicom import Dicom
from bsmu.vision_core.image import FlatImage


class PlaneDicomVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self, app: App):
        super().__init__(app, PlaneDicomVisualizer)


class PlaneDicomVisualizer(DataVisualizer):
    _DATA_TYPES = (Dicom, )

    def _visualize_data(self, data: Dicom):
        print('visualize plane dicom')


        a = FlatImage(data.pixel_array[:, :, 200])
        image_viewer = LayeredImageViewer(a)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        a = FlatImage(data.pixel_array[:, 200, :])
        image_viewer = LayeredImageViewer(a)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        a = FlatImage(data.pixel_array[200, :, :])
        image_viewer = LayeredImageViewer(a)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        return sub_window
