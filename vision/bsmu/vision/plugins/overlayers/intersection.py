from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette

if TYPE_CHECKING:
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager


class ImageViewerIntersectionOverlayerPlugin(Plugin):
    DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'data_visualization_manager_plugin': 'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
        'file_loading_manager_plugin': 'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
    }

    def __init__(
            self,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
    ):
        super().__init__()

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager | None = None

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._overlayer: ImageViewerIntersectionOverlayer | None = None

    def _enable(self):
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager

        self._overlayer = ImageViewerIntersectionOverlayer(
            self._data_visualization_manager,
            self._file_loading_manager,
            self.config.value('layers'),
            self.config.value('intersection-layer'),
        )

        self._data_visualization_manager.data_visualized.connect(
            self._overlayer.overlay_sibling_dirs_mask_intersection)

    def _disable(self):
        self._data_visualization_manager.data_visualized.disconnect(
            self._overlayer.overlay_sibling_dirs_mask_intersection)

        self._overlayer = None


class ImageViewerIntersectionOverlayer(QObject):
    def __init__(
            self,
            visualization_manager: DataVisualizationManager,
            loading_manager: FileLoadingManager,
            layers_properties: dict,
            intersection_layer_properties: dict,
    ):
        super().__init__()

        self.visualization_manager = visualization_manager
        self.loading_manager = loading_manager
        self.layers_properties = layers_properties
        self.intersection_layer_properties = intersection_layer_properties

    def overlay_sibling_dirs_mask_intersection(self, data: Data, data_viewer_sub_windows: DataViewerSubWindow):
        if isinstance(data, LayeredImage):
            first_layer = data.layers[0]
            first_layer_image_name = first_layer.image_path.name
            layers_dir = first_layer.path.parent

            intersection_image = None
            intersection_layer_index = len(self.layers_properties) + 1
            # First row is all zeros color (empty mask), last row is for intersection mask color
            intersection_palette_array = np.zeros(shape=(intersection_layer_index + 1, 4), dtype=np.uint8)

            for i, (new_layer_name, layer_properties) in enumerate(self.layers_properties.items()):
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

                        print('LEN', len(self.layers_properties))

            if intersection_image is not None:
                print('II', np.unique(intersection_image.array))
                intersection_palette_array[intersection_layer_index] = self.intersection_layer_properties['color']
                print('palette', intersection_palette_array)
                intersection_image.palette = Palette(intersection_palette_array)
                intersection_layer = data.add_layer_from_image(intersection_image, self.intersection_layer_properties['name'])

                intersection_layer_opacity = self.intersection_layer_properties['opacity']
                for data_viewer_sub_window in data_viewer_sub_windows:
                    layered_image_viewer = data_viewer_sub_window.viewer
                    layered_image_viewer.layer_view_by_model(intersection_layer).opacity = intersection_layer_opacity
