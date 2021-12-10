from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject

from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import List

    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow


class ImageViewerPathOverlayerPlugin(Plugin):
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

        self._overlayer: ImageViewerPathOverlayer | None = None

    def _enable(self):
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager

        self._overlayer = ImageViewerPathOverlayer(
            self._data_visualization_manager, self._file_loading_manager, self.config.value('layers'))

        self._data_visualization_manager.data_visualized.connect(self._overlayer.overlay_sibling_dirs_images)

    def _disable(self):
        self._data_visualization_manager.data_visualized.disconnect(self._overlayer.overlay_sibling_dirs_images)

        self._overlayer = None


class ImageViewerPathOverlayer(QObject):
    def __init__(
            self,
            visualization_manager: DataVisualizationManager,
            loading_manager: FileLoadingManager,
            layers_config_data: dict,
    ):
        super().__init__()

        self.visualization_manager = visualization_manager
        self.loading_manager = loading_manager
        self.layers_config_data = layers_config_data

    def overlay_sibling_dirs_images(self, data: Data, data_viewer_sub_windows: List[DataViewerSubWindow]):
        if not isinstance(data, LayeredImage):
            return

        first_layer = data.layers[0]
        first_layer_image_name = first_layer.image_path.name
        layers_dir = first_layer.path.parent

        for new_layer_name, layer_props in self.layers_config_data.items():
            new_layer_image_path = layers_dir / new_layer_name / first_layer_image_name
            if not new_layer_image_path.exists():
                continue

            palette_prop = layer_props.get('palette')
            palette = Palette.from_config(palette_prop)

            new_image = self.loading_manager.load_file(new_layer_image_path, palette=palette)
            new_image_layer = data.add_layer_from_image(new_image, new_layer_name)

            layer_opacity = layer_props.get('opacity')
            if layer_opacity is not None:
                for data_viewer_sub_window in data_viewer_sub_windows:
                    layered_image_viewer = data_viewer_sub_window.viewer
                    layered_image_viewer.layer_view_by_model(new_image_layer).opacity = layer_opacity
