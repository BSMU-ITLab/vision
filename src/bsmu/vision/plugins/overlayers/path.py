from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.visibility import Visibility

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.post_load_converters.manager import (
        PostLoadConversionManagerPlugin, PostLoadConversionManager
    )
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager


class ImageViewerPathOverlayerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'post_load_conversion_manager_plugin':
            'bsmu.vision.plugins.post_load_converters.manager.PostLoadConversionManagerPlugin',
        'file_loading_manager_plugin': 'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
    }

    def __init__(
            self,
            post_load_conversion_manager_plugin: PostLoadConversionManagerPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
    ):
        super().__init__()

        self._post_load_conversion_manager_plugin = post_load_conversion_manager_plugin
        self._post_load_conversion_manager: PostLoadConversionManager | None = None

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._overlayer: ImageViewerPathOverlayer | None = None

    def _enable(self):
        self._post_load_conversion_manager = self._post_load_conversion_manager_plugin.post_load_conversion_manager
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager

        self._overlayer = ImageViewerPathOverlayer(self._file_loading_manager, self.config.value('layers'))

        self._post_load_conversion_manager.data_converted.connect(self._overlayer.overlay_sibling_dirs_images)

    def _disable(self):
        self._post_load_conversion_manager.data_converted.disconnect(self._overlayer.overlay_sibling_dirs_images)

        self._overlayer = None


class ImageViewerPathOverlayer(QObject):
    def __init__(
            self,
            file_loading_manager: FileLoadingManager,
            layers_config_data: dict,
    ):
        super().__init__()

        self._file_loading_manager = file_loading_manager
        self._layers_config_data = layers_config_data

    def overlay_sibling_dirs_images(self, data: Data):
        if not isinstance(data, LayeredImage):
            return

        first_layer = data.layers[0]
        layers_dir = first_layer.path.parent
        relative_image_path = first_layer.image_path.relative_to(first_layer.path)

        for new_layer_name, layer_props in self._layers_config_data.items():
            new_layer_path = layers_dir / new_layer_name
            new_layer_image_path = new_layer_path / relative_image_path

            layer_extension_prop = layer_props.get('extension')
            if layer_extension_prop is not None:
                if not layer_extension_prop.startswith('.'):
                    layer_extension_prop = f'.{layer_extension_prop}'
                new_layer_image_path = new_layer_image_path.with_suffix(layer_extension_prop)

            if not new_layer_image_path.exists():
                continue

            palette_prop = layer_props.get('palette')
            palette = Palette.from_config(palette_prop)

            layer_opacity = layer_props.get('opacity')
            layer_visibility = Visibility(opacity=layer_opacity) if layer_opacity is not None else None

            new_image = self._file_loading_manager.load_file(new_layer_image_path, palette=palette)
            data.add_layer_from_image(new_image, new_layer_name, new_layer_path, layer_visibility)
