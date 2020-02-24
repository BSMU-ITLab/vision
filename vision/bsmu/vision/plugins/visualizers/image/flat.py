from __future__ import annotations

from bsmu.vision.plugins.visualizers.image.base import ImageVisualizerPlugin, ImageVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer
from bsmu.vision_core.image import FlatImage


class FlatImageVisualizerPlugin(ImageVisualizerPlugin):
    def __init__(self, app: App):
        super().__init__(app, FlatImageVisualizer)


class FlatImageVisualizer(ImageVisualizer):
    _DATA_TYPES = (FlatImage, )

    def _visualize_data(self, data: FlatImage):
        print('visualize flat image')

        image_viewer = LayeredImageViewer(data)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        sub_window.setWindowTitle(data.path.name)
        image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.addSubWindow(sub_window)
        sub_window.show()
        return sub_window
