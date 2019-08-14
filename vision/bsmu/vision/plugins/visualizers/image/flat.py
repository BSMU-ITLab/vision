from __future__ import annotations

from bsmu.vision.plugins.visualizers.image.base import ImageVisualizerPlugin, ImageVisualizer


class FlatImageVisualizerPlugin(ImageVisualizerPlugin):
    def __init__(self, app: App):
        super().__init__(app, FlatImageVisualizer)


class FlatImageVisualizer(ImageVisualizer):
    _DATA_TYPES = (FlatImage, )

    def _visualize_data(self, data: FlatImage):
        print('visualize flat image')

        image_viewer = FlatImageViewer(data)
        sub_window = ImageViewerSubWindow(image_viewer)
        self.mdi_area.addSubWindow(sub_window)
        sub_window.show()
        return sub_window
