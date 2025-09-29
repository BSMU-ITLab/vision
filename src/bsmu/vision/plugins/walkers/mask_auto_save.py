from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from bsmu.vision.core.config import Config, NamesOrAll
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.plugins.writers.image.common import CommonImageFileWriter

if TYPE_CHECKING:
    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.plugins.walkers.file import MdiImageLayerFileWalker, MdiImageLayerFileWalkerPlugin
    from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer


@dataclass
class MaskAutoSaveOnWalkConfig(Config):
    layers: NamesOrAll = field(default_factory=NamesOrAll.empty)


class MaskAutoSaveOnWalkPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_walker_plugin': 'bsmu.vision.plugins.walkers.file.MdiImageLayerFileWalkerPlugin',
    }

    def __init__(
            self,
            file_walker_plugin: MdiImageLayerFileWalkerPlugin,
    ):
        super().__init__()

        self._file_walker_plugin = file_walker_plugin
        self._file_walker: MdiImageLayerFileWalker | None = None

        self._mask_auto_save_on_walk: MaskAutoSaveOnWalk | None = None

    @property
    def mask_auto_save_on_walk(self) -> MaskAutoSaveOnWalk:
        return self._mask_auto_save_on_walk

    def _enable(self):
        self._file_walker = self._file_walker_plugin.mdi_image_layer_file_walker

        mask_auto_save_on_walk_config = MaskAutoSaveOnWalkConfig.from_dict(self.config.full_data)
        self._mask_auto_save_on_walk = MaskAutoSaveOnWalk(mask_auto_save_on_walk_config)

        self._file_walker.next_image_requested.connect(self._mask_auto_save_on_walk.save_masks)
        self._file_walker.prev_image_requested.connect(self._mask_auto_save_on_walk.save_masks)

    def _disable(self):
        self._file_walker.next_image_requested.disconnect(self._mask_auto_save_on_walk.save_masks)
        self._file_walker.prev_image_requested.disconnect(self._mask_auto_save_on_walk.save_masks)

        self._mask_auto_save_on_walk = None
        self._file_walker = None


class MaskAutoSaveOnWalk(QObject):
    def __init__(self, config: MaskAutoSaveOnWalkConfig):
        super().__init__()

        self._config = config
        self._writer = CommonImageFileWriter()

    def save_masks(self, image_viewer: LayeredImageViewer):
        if self._config.layers.is_all:
            for layer in image_viewer.layers:
                self._save_layer_mask(layer, image_viewer)
        else:
            for layer_name in self._config.layers.names:
                if (layer := image_viewer.layer_by_name(layer_name)) is not None:
                    self._save_layer_mask(layer, image_viewer)

    def _save_layer_mask(self, mask_layer: ImageLayer, image_viewer: LayeredImageViewer):
        if mask_layer.image is None:
            return

        # TODO: if mask was not changed (is not dirty) then return (do nothing)

        if not mask_layer.image.is_indexed:
            return

        save_path = mask_layer.image_path
        if save_path is None:
            image_layer = image_viewer.active_layer
            image_path = image_layer.image_path
            if image_path is None:
                logging.warning(
                    f"Cannot save mask for layer {mask_layer.name!r}: "
                    f"active image has no path, so a save path cannot be determined.")
                return
            new_mask_name = image_path.with_suffix('.png').name
            if mask_layer.path is not None:
                save_path = mask_layer.path / new_mask_name
            else:
                if image_layer.path is None:
                    logging.warning(f"Cannot save mask for layer {mask_layer.name!r}: "
                                    f"both mask layer path and active image layer path are undefined.")
                    return
                new_mask_layer_path = image_layer.path.with_name(mask_layer.name)
                save_path = new_mask_layer_path / new_mask_name
                mask_layer.path = new_mask_layer_path
            mask_layer.image.path = save_path

        logging.info(f"Save mask into {save_path}")
        self._writer.write_to_file(mask_layer.image, save_path)
