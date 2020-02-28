from __future__ import annotations

import numpy as np
from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision_core.palette import Palette


class ImageViewerPathOverlayerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager
        file_loading_manager_plugin = app.enable_plugin('bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin')

        self.overlayer = ImageViewerPathOverlayer(
            self.data_visualization_manager, file_loading_manager_plugin.file_loading_manager, self.config().data)

    def _enable(self):
        self.data_visualization_manager.data_visualized.connect(self.overlayer.overlay_sibling_dirs_images)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.overlayer.overlay_sibling_dirs_images)


class ImageViewerPathOverlayer(QObject):
    def __init__(self, visualization_manager: DataVisualizationManager, loading_manager: FileLoadingManager,
                 config_data):
        super().__init__()

        self.visualization_manager = visualization_manager
        self.loading_manager = loading_manager
        self.config_data = config_data

    def overlay_sibling_dirs_images(self, data_viewer_sub_window: DataViewerSubWindow):
        if isinstance(data_viewer_sub_window, LayeredImageViewerSubWindow):
            layered_image_viewer = data_viewer_sub_window.viewer
            image_path = layered_image_viewer.active_layer.image_path
            layers_dir = image_path.parents[1]
            for layer_name, layer_properties in self.config_data['layers'].items():
                layer_image_path = layers_dir / layer_name / image_path.name
                print(layer_name, layer_image_path.exists(), layer_image_path)
                if layer_image_path.exists():
                    if layer_properties['as_gray']:
                        print('YYYYYYYYYYY')
                    image = self.loading_manager.load_file(layer_image_path)
                    print('IMMMM', image.array.shape)
                    image.array = np.rint(image.array / 255).astype(int)     ####### To convert predictions to binary image
                    print('image unique', np.unique(image.array))
                    image.palette = Palette.from_sparse_index_list(list(layer_properties['palette']))
                    # print('PALETTE', image.palette.array)
                    layer_opacity = layer_properties['opacity']
                    layered_image_viewer.add_layer(image, layer_name, opacity=layer_opacity)
