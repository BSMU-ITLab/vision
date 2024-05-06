from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject

from bsmu.vision.core.image import Image, LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.core.visibility import Visibility

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.widgets.mdi.windows import DataViewerSubWindow


class ImageViewerIntersectionOverlayerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
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
            self.config.value('intersection_layer'),
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

        self._visualization_manager = visualization_manager
        self._loading_manager = loading_manager
        self._layers_properties = layers_properties
        self._intersection_layer_properties = intersection_layer_properties

    def overlay_sibling_dirs_mask_intersection(self, data: Data, data_viewer_sub_windows: DataViewerSubWindow):
        if not isinstance(data, LayeredImage):
            return

        first_layer = data.layers[0]
        first_layer_image_name = first_layer.image_path.name
        layers_dir = first_layer.path.parent

        intersection_image = None
        # Add two additional rows into palette:
        # first row is all zeros color (empty mask);
        # last row is for intersection mask color.
        intersection_palette_array = np.zeros(shape=(len(self._layers_properties) + 2, 4), dtype=np.uint8)
        intersection_palette_layer_index = len(intersection_palette_array) - 1

        for i, (new_layer_name, layer_properties) in enumerate(self._layers_properties.items()):
            new_layer_image_path = layers_dir / new_layer_name / first_layer_image_name

            layer_extension_prop = layer_properties.get('extension')
            if layer_extension_prop is not None:
                if not layer_extension_prop.startswith('.'):
                    layer_extension_prop = f'.{layer_extension_prop}'
                new_layer_image_path = new_layer_image_path.with_suffix(layer_extension_prop)

            if not new_layer_image_path.exists():
                continue

            palette_layer_index = i + 1
            color_property = layer_properties.get('color')
            intersection_palette_array[palette_layer_index] = color_property
            new_image = self._loading_manager.load_file(new_layer_image_path)
            if not isinstance(new_image, Image):
                continue

            if intersection_image is None:
                intersection_image = new_image
                intersection_image.pixels[intersection_image.pixels > 0] = palette_layer_index
            else:
                masked_new_image = new_image.pixels > 0
                intersection_image.pixels[
                    masked_new_image & (intersection_image.pixels > 0)
                ] = intersection_palette_layer_index
                intersection_image.pixels[masked_new_image & (intersection_image.pixels == 0)] = palette_layer_index

        if intersection_image is not None:
            intersection_palette_array[intersection_palette_layer_index] = self._intersection_layer_properties['color']
            intersection_image.palette = Palette(intersection_palette_array)

            intersection_layer_opacity = self._intersection_layer_properties['opacity']
            data.add_layer_from_image(
                intersection_image,
                self._intersection_layer_properties['name'],
                Visibility(opacity=intersection_layer_opacity),
            )
