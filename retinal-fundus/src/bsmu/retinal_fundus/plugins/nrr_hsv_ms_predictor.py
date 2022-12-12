from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
from PySide6.QtCore import Qt, QObject

from bsmu.retinal_fundus.plugins.disk_region_selector import RetinalFundusDiskRegionSelector, sector_mask
from bsmu.retinal_fundus.plugins.nrr_mask_calculator import RetinalFundusNrrMaskCalculator, NrrBboxParameter
from bsmu.retinal_fundus.plugins.table_visualizer import StyledItemDelegate
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn, TableItemDataRole
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Type

    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.image.layered import ImageLayer


class DiseaseStatus(Enum):
    NORM = auto()
    PATHOLOGY = auto()

    def __str__(self):
        return self.name.capitalize()


class NrrHsvMsPredictionParameter(ObjectParameter):
    NAME = 'NRR HSV MS Prediction'


class NrrHsvMsPredictionTableColumn(TableColumn):
    TITLE = 'MS Prediction\n(NRR HSV)'
    OBJECT_PARAMETER_TYPE = NrrHsvMsPredictionParameter


class NrrHsvMsPredictionItemDelegate(StyledItemDelegate):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)

    def _paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        index_parameter = index.data(TableItemDataRole.PARAMETER)
        if index_parameter is not None and index_parameter.value == DiseaseStatus.PATHOLOGY:
            painter.setPen(Qt.red)

        painter.drawText(option.rect, Qt.AlignCenter, index.data())


class RetinalFundusNrrHsvMsPredictorPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
    }

    def __init__(
            self,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
    ):
        super().__init__()

        self._retinal_fundus_table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._ms_predictor: RetinalFundusNrrHsvMsPredictor | None = None

    @property
    def ms_predictor(self) -> RetinalFundusNrrHsvMsPredictor | None:
        return self._ms_predictor

    def _enable(self):
        self._table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer

        self._ms_predictor = RetinalFundusNrrHsvMsPredictor(self._table_visualizer)

        ms_prediction_item_delegate = NrrHsvMsPredictionItemDelegate(self._table_visualizer)
        self._table_visualizer.add_column(NrrHsvMsPredictionTableColumn, ms_prediction_item_delegate)
        self._table_visualizer.journal.record_added.connect(self._ms_predictor.add_observed_record)
        self._table_visualizer.journal.record_removing.connect(self._ms_predictor.remove_observed_record)

    def _disable(self):
        self._ms_predictor = None

        self._table_visualizer = None

        raise NotImplementedError


class RetinalFundusNrrHsvMsPredictor(QObject):
    def __init__(self, table_visualizer: RetinalFundusTableVisualizer):
        super().__init__()

        self._table_visualizer = table_visualizer

        self._connections_by_record = {}

    @property
    def prediction_parameter_type(self) -> Type[ObjectParameter]:
        return NrrHsvMsPredictionParameter

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
        """
        DiseaseStatus.NORM:      mean H <  0.07 and mean S >= 0.69
        DiseaseStatus.PATHOLOGY: mean H >= 0.07 and mean S <  0.69
        In case of uncertainty:
            if at least one ISNT-sector has mean S >= 0.7:
                DiseaseStatus.NORM:
            else:
                DiseaseStatus.PATHOLOGY
        """

        if record.parameter_value_by_type(self.prediction_parameter_type) is not None:
            return

        if (nrr_mask := RetinalFundusNrrMaskCalculator.record_nrr_mask(record)) is None:
            return

        if (nrr_bbox := record.parameter_value_by_type(NrrBboxParameter)) is None:
            return

        nrr_image_in_region = nrr_bbox.pixels(record.image.pixels)
        nrr_mask_in_region = nrr_bbox.pixels(nrr_mask.pixels)

        nrr_image_in_region = nrr_image_in_region.astype(np.float32) / 255
        nrr_region_image_hsv = cv.cvtColor(nrr_image_in_region, cv.COLOR_RGB2HSV)
        nrr_region_image_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

        nrr_bool_mask_in_region = nrr_mask_in_region > 127

        nrr_region_image_h_channel = nrr_region_image_hsv[..., 0]
        nrr_region_image_s_channel = nrr_region_image_hsv[..., 1]
        h_mean = np.mean(nrr_region_image_h_channel, where=nrr_bool_mask_in_region)
        s_mean = np.mean(nrr_region_image_s_channel, where=nrr_bool_mask_in_region)

        if h_mean < 0.07 and s_mean >= 0.69:
            disease_status = DiseaseStatus.NORM
        elif h_mean >= 0.07 and s_mean < 0.69:
            disease_status = DiseaseStatus.PATHOLOGY
        else:
            # Analyze every ISNT-sector
            isnt_sectors_preset = RetinalFundusDiskRegionSelector.ISNT_SECTORS_PRESET
            isnt_sectors = isnt_sectors_preset.sectors()

            nrr_shape = nrr_image_in_region.shape[:2]
            nrr_center = (round(nrr_shape[0] / 2), round(nrr_shape[1] / 2))

            disease_status = DiseaseStatus.PATHOLOGY
            for isnt_sector in isnt_sectors:
                isnt_sector_mask = sector_mask(nrr_shape, nrr_center, (isnt_sector.start_angle, isnt_sector.end_angle))
                nrr_sector_bool_mask = nrr_bool_mask_in_region & isnt_sector_mask
                sector_s_mean = np.mean(nrr_region_image_s_channel, where=nrr_sector_bool_mask)
                if sector_s_mean >= 0.7:
                    disease_status = DiseaseStatus.NORM
                    break

        nrr_hsv_ms_prediction_parameter = self.prediction_parameter_type(disease_status)
        record.add_parameter_or_modify_value(nrr_hsv_ms_prediction_parameter)

    def _on_record_image_layer_added(
            self, record: PatientRetinalFundusRecord, image_layer: ImageLayer, layer_index: int):
        self._predict_for_record(record)

    def _on_record_parameter_added(self, record: PatientRetinalFundusRecord, parameter: ObjectParameter):
        self._predict_for_record(record)
