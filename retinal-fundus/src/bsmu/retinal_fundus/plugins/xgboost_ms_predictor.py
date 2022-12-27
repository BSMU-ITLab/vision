from __future__ import annotations

from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
from PySide6.QtCore import Qt, QObject

from bsmu.retinal_fundus.core.ms_prediction import MsPredictionParameter
from bsmu.retinal_fundus.core.statistics import calculate_hsv_parameters
from bsmu.retinal_fundus.plugins.disk_region_selector import RetinalFundusDiskRegionSelector, sector_mask
from bsmu.retinal_fundus.plugins.nrr_mask_calculator import RetinalFundusNrrMaskCalculator, NrrBboxParameter
from bsmu.retinal_fundus.plugins.table_visualizer import StyledItemDelegate
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn, TableItemDataRole
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.inferencer import ModelParams as MlModelParams
from bsmu.vision.dnn.predictor import MlPredictor

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.image.layered import ImageLayer


class XgboostMsPredictionScoreParameter(MsPredictionParameter):
    NAME = 'XGBoost MS Prediction Score'


class XgboostMsPredictionScoreTableColumn(TableColumn):
    TITLE = 'MS Score\n(XGBoost)'
    OBJECT_PARAMETER_TYPE = XgboostMsPredictionScoreParameter


class MsPredictionScoreItemDelegate(StyledItemDelegate):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)

    def _paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        index_parameter = index.data(TableItemDataRole.PARAMETER)
        if index_parameter is not None and index_parameter.value > 0.75:
            painter.setPen(Qt.red)

        painter.drawText(option.rect, Qt.AlignCenter, index.data())


class RetinalFundusXgboostMsPredictorPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
    }

    _ML_MODELS_DIR_NAME = 'ml-models'
    _DATA_DIRS = (_ML_MODELS_DIR_NAME,)

    def __init__(
            self,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
    ):
        super().__init__()

        self._retinal_fundus_table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._ms_predictor: RetinalFundusXgboostMsPredictor | None = None

    @property
    def ms_predictor(self) -> RetinalFundusXgboostMsPredictor | None:
        return self._ms_predictor

    def _enable(self):
        self._table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer

        ms_predictor_model_params = MlModelParams.from_config(
            self.config.value('ms-predictor-model'), self.data_path(self._ML_MODELS_DIR_NAME))
        self._ms_predictor = RetinalFundusXgboostMsPredictor(self._table_visualizer, ms_predictor_model_params)

        self._table_visualizer.journal.record_added.connect(self._ms_predictor.add_observed_record)
        self._table_visualizer.journal.record_removing.connect(self._ms_predictor.remove_observed_record)

    def _enable_gui(self):
        ms_prediction_score_item_delegate = MsPredictionScoreItemDelegate(self._table_visualizer)
        self._table_visualizer.add_column(XgboostMsPredictionScoreTableColumn, ms_prediction_score_item_delegate)

    def _disable(self):
        self._ms_predictor = None

        self._table_visualizer = None

        raise NotImplementedError


class RetinalFundusXgboostMsPredictor(QObject):
    def __init__(self, table_visualizer: RetinalFundusTableVisualizer, ms_predictor_model_params: MlModelParams):
        super().__init__()

        self._table_visualizer = table_visualizer

        self._ms_predictor = MlPredictor(ms_predictor_model_params)

        self._connections_by_record = {}

    def add_observed_record(self, record: PatientRetinalFundusRecord):
        self._predict_for_record(record)

        record_connections = set()
        record_connections.add(
            record.create_connection(record.layered_image.layer_added, self._on_record_image_layer_added))
        record_connections.add(
            record.create_connection(record.parameter_added, self._on_record_parameter_added))
        self._connections_by_record[record] = record_connections

    def remove_observed_record(self, record: PatientRetinalFundusRecord):
        record_connections = self._connections_by_record.pop(record)
        for connection in record_connections:
            connection.disconnect()

    def _predict_for_record(self, record: PatientRetinalFundusRecord):
        if record.parameter_value_by_type(XgboostMsPredictionScoreParameter) is not None:
            return

        if (nrr_mask := RetinalFundusNrrMaskCalculator.record_nrr_mask(record)) is None:
            return

        if (nrr_bbox := record.parameter_value_by_type(NrrBboxParameter)) is None:
            return

        nrr_image_in_region = record.image.bboxed_pixels(nrr_bbox)
        nrr_mask_in_region = nrr_mask.bboxed_pixels(nrr_bbox)

        analyzed_parameters = []

        # Analyze NRR parameters
        nrr_image_in_region = nrr_image_in_region.astype(np.float32) / 255
        nrr_region_image_hsv = cv.cvtColor(nrr_image_in_region, cv.COLOR_RGB2HSV)
        nrr_region_image_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

        nrr_bool_mask_in_region = nrr_mask_in_region > 127
        nrr_hsv_flatten_pixels = nrr_region_image_hsv[nrr_bool_mask_in_region]

        nrr_hsv_mean, nrr_hsv_std, nrr_hsv_min_bin_3, nrr_hsv_max_bin_3 = calculate_hsv_parameters(
            nrr_hsv_flatten_pixels)
        analyzed_parameters += \
            list(nrr_hsv_mean) + list(nrr_hsv_std) + list(nrr_hsv_min_bin_3) + list(nrr_hsv_max_bin_3)

        # Analyze NRR ISNT-sectors
        small_disk_region = record.disk_bbox.scaled(1.2, 1.2)
        small_disk_region.clip_to_shape(record.image.shape)
        small_disk_region_image_pixels = record.image.bboxed_pixels(small_disk_region)
        disk_center_rc = tuple(round(x / 2) for x in small_disk_region.shape)
        n_sector, i_sector, t_sector, s_sector = RetinalFundusDiskRegionSelector.ISNT_SECTORS_PRESET.sectors()
        for sector in (i_sector, s_sector, n_sector, t_sector):
            curr_sector_mask = sector_mask(
                small_disk_region.shape,
                disk_center_rc,
                (sector.start_angle, sector.end_angle))

            nrr_mask_copy = np.copy(nrr_mask.pixels)
            # Analyze only selected sector
            nrr_mask_in_small_disk_region = small_disk_region.pixels(nrr_mask_copy)
            nrr_mask_in_small_disk_region[curr_sector_mask == 0] = 0

            cropped_nrr_mask = nrr_bbox.pixels(nrr_mask_copy)
            cropped_nrr_float_mask = cropped_nrr_mask / 255

            cropped_nrr_bool_mask = cropped_nrr_float_mask > 0.5
            if not cropped_nrr_bool_mask.any():
                analyzed_parameters += [None, None, None]
                continue

            nrr_hsv_flatten_pixels_in_sector = nrr_region_image_hsv[cropped_nrr_bool_mask]

            sector_hsv_mean = np.mean(nrr_hsv_flatten_pixels_in_sector, axis=0)
            analyzed_parameters += list(sector_hsv_mean)

        # Analyze small disk region HSV parameters
        small_disk_region_image_pixels = small_disk_region_image_pixels.astype(np.float32) / 255
        small_disk_region_image_hsv = cv.cvtColor(small_disk_region_image_pixels, cv.COLOR_RGB2HSV)
        small_disk_region_image_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

        small_disk_region_flatten_hsv = \
            small_disk_region_image_hsv.reshape(-1, small_disk_region_image_hsv.shape[-1])
        small_disk_region_hsv_mean, small_disk_region_hsv_std, small_disk_region_hsv_min_bin_3, small_disk_region_hsv_max_bin_3 \
            = calculate_hsv_parameters(small_disk_region_flatten_hsv)
        analyzed_parameters += \
            list(small_disk_region_hsv_mean) + list(small_disk_region_hsv_std) + \
            list(small_disk_region_hsv_min_bin_3) + list(small_disk_region_hsv_max_bin_3)

        # Analyze disk HSV parameters
        disk_image_in_region = record.image.bboxed_pixels(record.disk_bbox)
        disk_mask_in_region = record.disk_mask.bboxed_pixels(record.disk_bbox)

        disk_image_in_region = disk_image_in_region.astype(np.float32) / 255
        disk_image_in_region_hsv = cv.cvtColor(disk_image_in_region, cv.COLOR_RGB2HSV)
        disk_image_in_region_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

        disk_bool_mask_in_region = disk_mask_in_region > 127
        disk_hsv_flatten_pixels = disk_image_in_region_hsv[disk_bool_mask_in_region]

        disk_hsv_mean, disk_hsv_std, disk_hsv_min_bin_3, disk_hsv_max_bin_3 = \
            calculate_hsv_parameters(disk_hsv_flatten_pixels)
        analyzed_parameters += \
            list(disk_hsv_mean) + list(disk_hsv_std) + list(disk_hsv_min_bin_3) + list(disk_hsv_max_bin_3)

        ms_prediction_score = self._ms_predictor.predict(analyzed_parameters)

        ms_prediction_score_parameter = XgboostMsPredictionScoreParameter(ms_prediction_score)
        ms_prediction_score_parameter = record.add_parameter_or_modify_value(ms_prediction_score_parameter)

    def _on_record_image_layer_added(
            self, record: PatientRetinalFundusRecord, image_layer: ImageLayer, layer_index: int):
        self._predict_for_record(record)

    def _on_record_parameter_added(self, record: PatientRetinalFundusRecord, parameter: ObjectParameter):
        self._predict_for_record(record)
