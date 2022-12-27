from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject

from bsmu.retinal_fundus.core.ms_prediction import MsPredictionParameter
from bsmu.retinal_fundus.plugins.table_visualizer import StyledItemDelegate
from bsmu.vision.core.models.table import TableColumn, TableItemDataRole
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.predictor import Predictor as DnnPredictor

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.bbox import BBox


class MsPredictionScoreParameter(MsPredictionParameter):
    NAME = 'MS Prediction Score'


class MsPredictionScoreTableColumn(TableColumn):
    TITLE = 'MS Score\n(DNN)'
    OBJECT_PARAMETER_TYPE = MsPredictionScoreParameter


class MsPredictionScoreItemDelegate(StyledItemDelegate):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)

    def _paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        index_parameter = index.data(TableItemDataRole.PARAMETER)
        if index_parameter is not None and index_parameter.value > 0.75:
            painter.setPen(Qt.red)

        painter.drawText(option.rect, Qt.AlignCenter, index.data())


class RetinalFundusMsPredictorPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
    ):
        super().__init__()

        self._retinal_fundus_table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._ms_predictor: RetinalFundusMsPredictor | None = None

    @property
    def ms_predictor(self) -> RetinalFundusMsPredictor | None:
        return self._ms_predictor

    def _enable(self):
        self._table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer

        ms_predictor_model_params = DnnModelParams.from_config(
            self.config.value('ms-predictor-model'), self.data_path(self._DNN_MODELS_DIR_NAME))
        self._ms_predictor = RetinalFundusMsPredictor(self._table_visualizer, ms_predictor_model_params)

        ms_prediction_score_item_delegate = MsPredictionScoreItemDelegate(self._table_visualizer)
        self._table_visualizer.add_column(MsPredictionScoreTableColumn, ms_prediction_score_item_delegate)
        self._table_visualizer.journal.record_added.connect(self._ms_predictor.add_observed_record)
        self._table_visualizer.journal.record_removing.connect(self._ms_predictor.remove_observed_record)

    def _disable(self):
        self._ms_predictor = None

        self._table_visualizer = None

        raise NotImplementedError


class RetinalFundusMsPredictor(QObject):
    def __init__(self, table_visualizer: RetinalFundusTableVisualizer, ms_predictor_model_params: DnnModelParams):
        super().__init__()

        self._table_visualizer = table_visualizer
        self._ms_predictor = DnnPredictor(ms_predictor_model_params)

        self._connections_by_record = {}

    def add_observed_record(self, record: PatientRetinalFundusRecord):
        self._predict_for_record(record)

        record_connections = set()
        record_connections.add(
            record.create_connection(record.disk_bbox_changed, self._on_record_disk_bbox_changed))
        self._connections_by_record[record] = record_connections

    def remove_observed_record(self, record: PatientRetinalFundusRecord):
        record_connections = self._connections_by_record.pop(record)
        for connection in record_connections:
            connection.disconnect()

    def _predict_for_record(self, record: PatientRetinalFundusRecord):
        if record.disk_bbox is None:
            return

        disk_region_bbox = record.disk_bbox.margins_added(
            round((record.disk_bbox.width + record.disk_bbox.height) / 2))
        disk_region_bbox.clip_to_shape(record.image.shape)
        disk_region_image = disk_region_bbox.pixels(record.image.pixels)

        self._ms_predictor.predict_async(
            partial(self._on_ms_predicted, record),
            disk_region_image)

    def _on_record_disk_bbox_changed(self, record: PatientRetinalFundusRecord, disk_bbox: BBox):
        self._predict_for_record(record)

    def _on_ms_predicted(self, record: PatientRetinalFundusRecord, ms_prediction_score: float):
        ms_prediction_score_parameter = MsPredictionScoreParameter(ms_prediction_score)
        ms_prediction_score_parameter = record.add_parameter_or_modify_value(ms_prediction_score_parameter)
