from __future__ import annotations

import numpy as np

from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer
from bsmu.vision_core.dicom import Dicom
from bsmu.vision_core.image import FlatImage, VolumeImage


class VolumeImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self, app: App):
        super().__init__(app, VolumeImageVisualizer)


class VolumeImageVisualizer(DataVisualizer):
    _DATA_TYPES = (VolumeImage, )

    def _visualize_data(self, data: Dicom):
        print('visualize plane dicom')


        print('===', data.array.min(), data.array.max())

        window_width = data.array.max() - data.array.min()
        window_level = (data.array.max() + data.array.min()) / 2

        slice_a = data.array[:, :, 200]
        # slice_a[slice_a < window_level - window_width / 2] = 0
        # slice_a[slice_a > window_level + window_width / 2] = 255

        print('before', slice_a.min(), slice_a.max())
        lutvalue = np.piecewise(slice_a,
                                [slice_a <= (window_level - 0.5 - (window_width - 1) / 2),
                                 slice_a > (window_level - 0.5 + (window_width - 1) / 2)],
                                [0, 255, lambda slice_a:
                                ((slice_a - (window_level - 0.5)) / (window_width - 1) + 0.5) *
                                (255 - 0)])
        slice_a = lutvalue
        print('after', slice_a.min(), slice_a.max(), slice_a.dtype)
        slice_a = slice_a.astype(np.uint8, copy=False)
        print('after astype', slice_a.min(), slice_a.max(), slice_a.dtype)


        # lutvalue = util.piecewise(data,
        #                           [data <= (level - 0.5 - (window - 1) / 2),
        #                            data > (level - 0.5 + (window - 1) / 2)],
        #                           [0, 255, lambda data:
        #                           ((data - (level - 0.5)) / (window - 1) + 0.5) *
        #                           (255 - 0)])


        a = FlatImage(slice_a)

        image_viewer = LayeredImageViewer(a)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        a = FlatImage(data.array[:, 200, :])
        image_viewer = LayeredImageViewer(a)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        a = FlatImage(data.array[200, :, :])
        image_viewer = LayeredImageViewer(a)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        # sub_window.setWindowTitle(data.path.name)
        # image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()

        return sub_window
