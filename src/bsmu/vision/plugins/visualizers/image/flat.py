from __future__ import annotations

import logging

from bsmu.vision.core.image import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.plugins.visualizers.image import ImageVisualizerPlugin, ImageVisualizer
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer


class FlatImageVisualizerPlugin(ImageVisualizerPlugin):
    def __init__(self):
        super().__init__(FlatImageVisualizer)


class FlatImageVisualizer(ImageVisualizer):
    _DATA_TYPES = (FlatImage, )

    def _visualize_data(self, data: FlatImage):
        logging.info('Visualize flat image')

        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)
        image_viewer = LayeredFlatImageViewer(layered_image)
        sub_window = LayeredImageViewerSubWindow(image_viewer)
        image_viewer.data_name_changed.connect(sub_window.setWindowTitle)
        self.mdi.add_sub_window(sub_window)
        sub_window.show()
        return [sub_window]
