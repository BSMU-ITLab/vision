from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette

if TYPE_CHECKING:
    from bsmu.vision.app import App


class ImageViewerIntersectionOverlayerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager
        file_loading_manager_plugin = app.enable_plugin('bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin')

        self.overlayer = ImageViewerIntersectionOverlayer(
            self.data_visualization_manager, file_loading_manager_plugin.file_loading_manager, self.old_config().data)

    def _enable(self):
        self.data_visualization_manager.data_visualized.connect(
            self.overlayer.overlay_sibling_dirs_mask_intersection)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(
            self.overlayer.overlay_sibling_dirs_mask_intersection)


class ImageViewerIntersectionOverlayer(QObject):
    def __init__(self, visualization_manager: DataVisualizationManager, loading_manager: FileLoadingManager,
                 config_data):
        super().__init__()

        self.visualization_manager = visualization_manager
        self.loading_manager = loading_manager
        self.config_data = config_data

    def overlay_sibling_dirs_mask_intersection(self, data: Data, data_viewer_sub_windows: DataViewerSubWindow):
        if isinstance(data, LayeredImage):
            first_layer = data.layers[0]
            first_layer_image_name = first_layer.image_path.name
            layers_dir = first_layer.path.parent

            intersection_image = None
            layers_config = self.config_data['layers']
            intersection_layer_index = len(layers_config) + 1
            # First row is all zeros color (empty mask), last row is for intersection mask color
            intersection_palette_array = np.zeros(shape=(intersection_layer_index + 1, 4), dtype=np.uint8)

            for i, (new_layer_name, layer_properties) in enumerate(layers_config.items()):
                new_layer_image_path = layers_dir / new_layer_name / first_layer_image_name
                layer_index = i + 1
                if new_layer_image_path.exists():
                    color_property = layer_properties.get('color')
                    intersection_palette_array[layer_index] = color_property
                    new_image = self.loading_manager.load_file(new_layer_image_path)

                    if intersection_image is None:
                        new_image.array[new_image.array > 0] = layer_index
                        intersection_image = new_image
                    else:
                        masked_new_image = new_image.array > 0
                        intersection_image.array[np.logical_and(intersection_image.array > 0, masked_new_image)] = intersection_layer_index
                        intersection_image.array[np.logical_and(intersection_image.array == 0, masked_new_image)] = layer_index

                        print('LEN', len(layers_config))

            if intersection_image is not None:
                print('II', np.unique(intersection_image.array))
                intersection_layer_properties = self.config_data['intersection-layer']
                intersection_palette_array[intersection_layer_index] = intersection_layer_properties['color']
                print('palette', intersection_palette_array)
                intersection_image.palette = Palette(intersection_palette_array)
                intersection_layer = data.add_layer_from_image(intersection_image, intersection_layer_properties['name'])

                intersection_layer_opacity = intersection_layer_properties['opacity']
                for data_viewer_sub_window in data_viewer_sub_windows:
                    layered_image_viewer = data_viewer_sub_window.viewer
                    layered_image_viewer.layer_view_by_model(intersection_layer).opacity = intersection_layer_opacity
