from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject

from bsmu.vision.core.config import IntList
from bsmu.vision.core.image import Image
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.core.visibility import Visibility

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.postread.manager import (
        PostReadConversionManager, PostReadConversionManagerPlugin
    )
    from bsmu.vision.plugins.readers.manager import FileReadingManager, FileReadingManagerPlugin


class ImageViewerIntersectionOverlayerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'post_read_conversion_manager_plugin':
            'bsmu.vision.plugins.postread.manager.PostReadConversionManagerPlugin',
        'file_reading_manager_plugin': 'bsmu.vision.plugins.readers.manager.FileReadingManagerPlugin',
    }

    def __init__(
            self,
            post_read_conversion_manager_plugin: PostReadConversionManagerPlugin,
            file_reading_manager_plugin: FileReadingManagerPlugin,
    ):
        super().__init__()

        self._post_read_conversion_manager_plugin = post_read_conversion_manager_plugin
        self._post_read_conversion_manager: PostReadConversionManager | None = None

        self._file_reading_manager_plugin = file_reading_manager_plugin
        self._file_reading_manager: FileReadingManager | None = None

        self._overlayer: ImageViewerIntersectionOverlayer | None = None

    def _enable(self):
        self._post_read_conversion_manager = self._post_read_conversion_manager_plugin.post_read_conversion_manager
        self._file_reading_manager = self._file_reading_manager_plugin.file_reading_manager

        self._overlayer = ImageViewerIntersectionOverlayer(
            self._file_reading_manager,
            self.config.value('layers'),
            self.config.value('intersection_layer'),
        )

        self._post_read_conversion_manager.data_converted.connect(
            self._overlayer.overlay_sibling_dirs_mask_intersection)

    def _disable(self):
        self._post_read_conversion_manager.data_converted.disconnect(
            self._overlayer.overlay_sibling_dirs_mask_intersection)

        self._overlayer = None


class ImageViewerIntersectionOverlayer(QObject):
    def __init__(
            self,
            file_reading_manager: FileReadingManager,
            layers_properties: dict,
            intersection_layer_properties: dict,
    ):
        super().__init__()

        self._file_reading_manager = file_reading_manager
        self._layers_properties = layers_properties
        self._intersection_layer_properties = intersection_layer_properties

    def overlay_sibling_dirs_mask_intersection(self, data: Data):
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
            new_image = self._file_reading_manager.read_file(new_layer_image_path)
            if not isinstance(new_image, Image):
                continue

            layer_classes = IntList(layer_properties.get('classes', 'all'))
            layer_background_class = layer_properties.get('background_class', 0)
            used_for_intersection_mask = (
                new_image.pixels != layer_background_class
                if layer_classes.contains_all_values
                else layer_classes.elements_in_list_mask(new_image.pixels)
            )

            if intersection_image is None:
                intersection_image = new_image.zeros()
                intersection_image.pixels[used_for_intersection_mask] = palette_layer_index
            else:
                intersection_image.pixels[
                    used_for_intersection_mask & (intersection_image.pixels > 0)
                ] = intersection_palette_layer_index
                intersection_image.pixels[
                    used_for_intersection_mask & (intersection_image.pixels == 0)
                ] = palette_layer_index

        if intersection_image is not None:
            intersection_palette_array[intersection_palette_layer_index] = self._intersection_layer_properties['color']
            intersection_image.palette = Palette(intersection_palette_array)

            intersection_layer_opacity = self._intersection_layer_properties['opacity']
            data.add_layer_from_image(
                intersection_image,
                self._intersection_layer_properties['name'],
                visibility=Visibility(opacity=intersection_layer_opacity),
            )
