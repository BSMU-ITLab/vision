from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bsmu.vision.core.config import Config
from bsmu.vision.core.image import FlatImage, VolumeImage, LayeredImage
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.plugins.post_load_converters import PostLoadConverter, PostLoadConverterPlugin

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data


@dataclass
class SearchPath(Config):
    name: str
    depth: int = 2


@dataclass
class ImageLayerConfig(Config):
    name: str | None = None
    path: Path | None = None
    search_path: SearchPath | None = None
    visibility: Visibility | None = None

    def resolved_layer_name_and_path_from_image(self, image_path: Path) -> tuple[str, Path]:
        layer_path = None
        if self.path is None:
            if self.search_path is not None:
                current_depth = 1
                for image_parent_path in image_path.parents:
                    if current_depth > self.search_path.depth:
                        break
                    if image_parent_path.name == self.search_path.name:
                        layer_path = image_parent_path
                        break
                    current_depth += 1
        elif self.path.is_absolute():
            layer_path = self.path
        else:
            # Resolve relative path against `image_path.parent`
            layer_path = image_path.parent.joinpath(self.path).resolve()

        if layer_path is None:
            layer_path = image_path.parent
        elif not image_path.is_relative_to(layer_path):
            logging.warning(
                f'Image path {image_path} has to be relative to layer path {layer_path}. '
                f'Image parent {image_path.parent} will be used as layer path.'
            )
            layer_path = image_path.parent

        layer_name = layer_path.name if self.name is None else self.name
        return layer_name, layer_path


class ImageToLayeredImagePostLoadConverterPlugin(PostLoadConverterPlugin):
    def __init__(self):
        super().__init__(ImageToLayeredImagePostLoadConverter)

    def _enable(self):
        image_layer_config = ImageLayerConfig.from_dict(self.config_value('created_layer'))
        print(f'image_layer_config:\n{image_layer_config}')

        test_image_path = Path(r'D:\Projects\vision\tests\test-data\images\01-eye-fundus-8UC3.png')
        layer_name, layer_path = image_layer_config.resolved_layer_name_and_path_from_image(test_image_path)
        print(f'layer_path: {layer_path}')
        print(f'layer_name: {layer_name}')


class ImageToLayeredImagePostLoadConverter(PostLoadConverter):
    _DATA_TYPES = (FlatImage, VolumeImage)

    def _convert_data(self, data: Data) -> Data:
        layered_image = LayeredImage()
        layered_image.add_layer_from_image(data, name=data.dir_name)
        return layered_image
