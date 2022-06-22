from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from pathlib import Path
import numpy as np
import cv2 as cv
from PySide6.QtCore import Qt, QObject

import skimage.util
from bsmu.vision.core.image import tile_splitter

from bsmu.retinal_fundus.plugins.table_visualizer import StyledItemDelegate
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn, TableItemDataRole
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.inferencer import ModelParams as DnnModelParams
from bsmu.vision.dnn.predictor import Predictor as DnnPredictor

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.bbox import BBox

    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager


class BiocellPcIsupPredictorPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_loading_manager_plugin':
            'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
        'data_visualization_manager_plugin':
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
    ):
        super().__init__()

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager

        self._pc_isup_predictor: BiocellPcIsupPredictor | None = None

    @property
    def ms_predictor(self) -> BiocellPcIsupPredictor | None:
        return self._pc_isup_predictor

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager

        model_params = DnnModelParams.from_config(
            self.config.value('predictor-model'), self.data_path(self._DNN_MODELS_DIR_NAME))
        self._pc_isup_predictor = BiocellPcIsupPredictor(self._data_visualization_manager, model_params)

        # ms_prediction_score_item_delegate = MsPredictionScoreItemDelegate(self._table_visualizer)
        # self._table_visualizer.add_column(MsPredictionScoreTableColumn, ms_prediction_score_item_delegate)
        # self._table_visualizer.journal.record_added.connect(self._ms_predictor.add_observed_record)
        # self._table_visualizer.journal.record_removing.connect(self._ms_predictor.remove_observed_record)
        self._file_loading_manager.file_loaded.connect(self._pc_isup_predictor.predict)

    def _disable(self):
        self._pc_isup_predictor = None

        self._file_loading_manager = None

        raise NotImplementedError


class BiocellPcIsupPredictor(QObject):
    def __init__(self, data_visualization_manager: DataVisualizationManager, model_params: DnnModelParams):
        super().__init__()

        self._data_visualization_manager = data_visualization_manager
        self._model_params = model_params

        self._pc_predictor = DnnPredictor(self._model_params)

    def predict(self, data: Data):
        print('predict', type(data))

        if not isinstance(data, FlatImage):
            return

        img = data.pixels

        # img = cv.resize(img, (img.shape[1] // 4, img.shape[0] // 4), interpolation=cv.INTER_AREA)

        tiles, idxs = self._tiled(img, 192, 64)
        # img = tile_splitter.merge_tiles_into_image(tiles, (64, 64))

        img = np.swapaxes(tiles.reshape((8, 8, 192, 192, 3)), 1, 2)
        # # img = img.view((192*8, 192*8, 3))
        img = img.reshape((192 * 8, 192 * 8, 3))


        self._data_visualization_manager.visualize_data(FlatImage(img))

        img = 255 - img

        img = (img / 255).astype(float)
        print('Before prediction:', img.dtype, img.shape)

        self._pc_predictor.predict_async(self._on_pc_predicted, img)

    def _on_pc_predicted(self, pc_prediction: np.ndarray):
        print('pc_prediction', pc_prediction)
        pc_prediction = self.sigmoid_array(pc_prediction)
        print('pc_prediction', pc_prediction)

        # isup = round(pc_prediction[:5].sum())
        # glisson = round(pc_prediction[5:].sum())

        isup = np.round(pc_prediction[:5])
        glisson = np.round(pc_prediction[5:])

        print(f'isup {isup}')
        print(f'glisson {glisson}')

        # pc_prediction = pc_prediction > 0

    def sigmoid_array(self, x):
        return 1 / (1 + np.exp(-x))

    def as_tiles(self, image: np.ndarray, tile_size: int):
        new_shape = (tile_size, tile_size, image.shape[-1])
        print('as_tiles0', image.shape)
        image = skimage.util.view_as_blocks(image, new_shape)
        print('as_tiles1', image.shape)
        image = image.reshape(-1, *new_shape)
        print('as_tiles2', image.shape)
        return image #image.reshape(-1, *new_shape)

    def _tiled(self, image: np.ndarray, tile_size: int, n_tiles: int, pad_value=255):
        print('IMAGE type:', image.dtype, image.min(), image.max())

        h, w, c = image.shape

        pad_h = -h % tile_size
        pad_w = -w % tile_size

        pad = ((pad_h // 2, pad_h - pad_h // 2), (pad_w // 2, pad_w - pad_w // 2), (0, 0))

        image = np.pad(image, pad, constant_values=pad_value)
        image = self.as_tiles(image, tile_size)
        idxs = np.argsort(image.reshape(image.shape[0], -1).sum(-1))[:n_tiles]
        print('Bef', image.shape,   idxs.shape)
        image = image[idxs]
        print('aft', image.shape)

        if len(image) < n_tiles:
            pad = ((0, n_tiles - len(image)), (0, 0), (0, 0), (0, 0))
            image = np.pad(image, pad, constant_values=pad_value)

        print('aft', image.shape)
        return image, idxs
