from __future__ import annotations

from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
from PySide6.QtCore import QObject

from bsmu.vision.core.padding import padded_to_shape, padded_to_square_shape, padding_removed
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter

if TYPE_CHECKING:
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin
    from bsmu.vision.plugins.storages import TaskStorage, TaskStoragePlugin


class DnnTissueSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task_storage.TaskStoragePlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            task_storage_plugin: TaskStoragePlugin,
    ):
        super().__init__()

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._task_storage_plugin = task_storage_plugin

        self._dnn_tissue_segmenter: DnnTissueSegmenter | None = None

    @property
    def dnn_tissue_segmenter(self) -> DnnTissueSegmenter | None:
        return self._dnn_tissue_segmenter

    def _enable(self):
        tissue_model_params = DnnModelParams.from_config(
            self.config_value('tissue_segmenter_model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        main_palette = self._palette_pack_settings_plugin.settings.main_palette
        task_storage = self._task_storage_plugin.task_storage
        self._dnn_tissue_segmenter = DnnTissueSegmenter(
            tissue_model_params, main_palette, 'tissue', task_storage)

    def _disable(self):
        self._dnn_tissue_segmenter = None


class DnnTissueSegmenter(QObject):
    def __init__(
            self,
            model_params: DnnModelParams,
            mask_palette: Palette,
            mask_foreground_class_name: str = 'foreground',
            task_storage: TaskStorage = None,
    ):
        super().__init__()

        self._model_params = model_params
        self._task_storage = task_storage

        self._mask_palette = mask_palette
        self._mask_background_class = self._mask_palette.row_index_by_name('background')
        self._mask_foreground_class = self._mask_palette.row_index_by_name(mask_foreground_class_name)

        self._segmenter = DnnSegmenter(self._model_params)

    @property
    def segmenter(self) -> DnnSegmenter:
        return self._segmenter

    @property
    def mask_palette(self) -> Palette:
        return self._mask_palette

    @property
    def mask_background_class(self) -> int:
        return self._mask_background_class

    @property
    def mask_foreground_class(self) -> int:
        return self._mask_foreground_class

    def segment(self, image: np.ndarray) -> np.ndarray:
        image = image.astype(np.float32) / 255

        # Add paddings
        border_type = cv.BORDER_CONSTANT
        pad_value = 1
        if any(
                image_dim > model_input_dim
                for image_dim, model_input_dim in zip(image.shape, self._model_params.input_image_size)
        ):
            image, padding = padded_to_square_shape(image, border_type, pad_value)
        else:
            image, padding = padded_to_shape(image, self._model_params.input_image_size, border_type, pad_value)

        mask = self._segmenter.segment(image)

        # Remove paddings
        mask = padding_removed(mask, padding)

        mask = self.sigmoid(mask)
        mask = np.where(mask >= self._model_params.mask_binarization_threshold, 1, 0).astype(np.uint8)
        return mask

    @staticmethod
    def sigmoid(x: np.ndarray) -> np.ndarray:
        """ Benchmark showed, that this sigmoid implementation is faster than scipy.special.expit """
        return 1 / (1 + np.exp(-x))
