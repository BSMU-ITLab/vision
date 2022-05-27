from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn, TableItemDataRole
from bsmu.vision.core.plugins.base import Plugin

from bsmu.retinal_fundus.plugins.nrr_mask_calculator import RetinalFundusNrrMaskCalculator

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.bbox import BBox


class NrrHsvMsPredictionParameter(ObjectParameter):
    NAME = 'NRR HSV MS Prediction'


class NrrHsvMsPredictionTableColumn(TableColumn):
    TITLE = 'NRR HSV\nMS Prediction'
    OBJECT_PARAMETER_TYPE = NrrHsvMsPredictionParameter


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

        ms_prediction_item_delegate = None #% MsPredictionScoreItemDelegate(self._table_visualizer)
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

    def add_observed_record(self, record: PatientRetinalFundusRecord):
        self._predict_for_record(record)

        record_connections = set()
        record_connections.add(
            record.create_connection(record.layered_image.layer_added, self._on_record_image_layer_added))
        self._connections_by_record[record] = record_connections

    def remove_observed_record(self, record: PatientRetinalFundusRecord):
        record_connections = self._connections_by_record.pop(record)
        for connection in record_connections:
            connection.disconnect()

    def _predict_for_record(self, record: PatientRetinalFundusRecord):
        nrr_mask = record.image_by_layer_name(RetinalFundusNrrMaskCalculator.NRR_SOFT_MASK_LAYER_NAME)
        if nrr_mask is None:
            nrr_mask = record.image_by_layer_name(
                RetinalFundusNrrMaskCalculator.NRR_BINARY_MASK_LAYER_NAME)
        print('PREDICT FOR RECORD:', nrr_mask)
        if nrr_mask is None:
            return

        print('PREDICT FOR RECORD: nrr_mask is GOOD', nrr_mask.shape)

        # disk_region_bbox = record.disk_bbox.margins_added(
        #     round((record.disk_bbox.width + record.disk_bbox.height) / 2))
        # disk_region_bbox.clip_to_shape(record.image.shape)
        # disk_region_image = disk_region_bbox.pixels(record.image.pixels)
        #
        # self._ms_predictor.predict_async(
        #     partial(self._on_ms_predicted, record),
        #     disk_region_image)

    def _on_record_image_layer_added(
            self, record: PatientRetinalFundusRecord, image_layer: ImageLayer, layer_index: int):
        print('layer_added', image_layer.name)
        self._predict_for_record(record)

    def _on_ms_predicted(self, record: PatientRetinalFundusRecord, ms_prediction_score: float):
        ms_prediction_parameter = NrrHsvMsPredictionParameter(ms_prediction_score)
        ms_prediction_parameter = record.add_parameter_or_modify_value(ms_prediction_parameter)
