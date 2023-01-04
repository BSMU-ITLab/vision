from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyle

from bsmu.retinal_fundus.core.ms_prediction import MsPredictionParameter, DiseaseStatus
from bsmu.retinal_fundus.plugins.table_visualizer import StyledItemDelegate
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord


class MsSummaryParameter(ObjectParameter):
    NAME = 'MS Summary'


@dataclass
class MsSummaryParameterValue:
    score: float
    ms_count: int
    norm_count: int

    def __str__(self):
        if self.score is None:
            return ObjectParameter.UNKNOWN_VALUE_STR

        return f'{self.score:.2f}\nN: {self.norm_count}   P: {self.ms_count}'


class MsSummaryTableColumn(TableColumn):
    TITLE = 'MS\nSummary'
    OBJECT_PARAMETER_TYPE = MsSummaryParameter


class MsSummaryItemDelegate(StyledItemDelegate):
    def __init__(self, norm_threshold: float = 0.35, ms_threshold: float = 0.65, parent: QObject = None):
        super().__init__(parent)

        self._norm_threshold = norm_threshold
        self._ms_threshold = ms_threshold

    def _paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        item_parameter = self._item_parameter(index)
        disease_status = None
        if item_parameter and item_parameter.value and item_parameter.value.score is not None:
            pen_color = None
            if item_parameter.value.score < self._norm_threshold:
                disease_status = DiseaseStatus.NORM
                pen_color = QColor.fromHsv(120, 204, 179)
            elif item_parameter.value.score > self._ms_threshold:
                disease_status = DiseaseStatus.PATHOLOGY
                pen_color = Qt.red
            else:
                disease_status = DiseaseStatus.UNDEFINED
                # pen_color = QColor.fromHsv(60, 255, 217)

            if pen_color:
                painter.setPen(pen_color)

        if not option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.alternateBase())

        text = index.data()
        if disease_status:
            text = f'{disease_status}\n{text}'
        painter.drawText(option.rect, Qt.AlignCenter, text)


class RetinalFundusMsPredictionAggregatorPlugin(Plugin):
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

        self._ms_prediction_aggregator: RetinalFundusMsPredictionAggregator | None = None

    @property
    def ms_prediction_aggregator(self) -> RetinalFundusMsPredictionAggregator | None:
        return self._ms_prediction_aggregator

    def _enable(self):
        self._table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer

        self._ms_prediction_aggregator = RetinalFundusMsPredictionAggregator(self._table_visualizer)

        self._table_visualizer.journal.record_added.connect(self._ms_prediction_aggregator.add_observed_record)
        self._table_visualizer.journal.record_removing.connect(self._ms_prediction_aggregator.remove_observed_record)
        self._table_visualizer.journal.record_removed.connect(self._ms_prediction_aggregator.on_journal_record_removed)

    def _enable_gui(self):
        ms_summary_item_delegate = MsSummaryItemDelegate(
            self.config.value('norm-threshold'), self.config.value('ms-threshold'), self._table_visualizer)
        self._table_visualizer.add_column(MsSummaryTableColumn, ms_summary_item_delegate)

    def _disable(self):
        self._ms_prediction_aggregator = None

        self._table_visualizer = None

        raise NotImplementedError


class RetinalFundusMsPredictionAggregator(QObject):
    def __init__(self, table_visualizer: RetinalFundusTableVisualizer):
        super().__init__()

        self._table_visualizer = table_visualizer

        self._connections_by_record = {}

    def add_observed_record(self, record: PatientRetinalFundusRecord):
        self._aggregate_patient_ms_predictions(record)

        record_connections = set()
        record_connections.add(
            record.create_connection(record.parameter_added, self._on_record_parameter_added_or_changed))
        record_connections.add(
            record.create_connection(record.parameter_value_changed, self._on_record_parameter_added_or_changed))
        self._connections_by_record[record] = record_connections

    def remove_observed_record(self, record: PatientRetinalFundusRecord):
        record_connections = self._connections_by_record.pop(record)
        for connection in record_connections:
            connection.disconnect()

    def on_journal_record_removed(self, record: PatientRetinalFundusRecord):
        self._aggregate_patient_ms_predictions(record)

    def _aggregate_patient_ms_predictions(self, record: PatientRetinalFundusRecord):
        patient_ms_scores = []
        for patient_record in record.patient.records:
            for parameter in patient_record.parameters:
                if isinstance(parameter, MsPredictionParameter):
                    patient_ms_scores.append(parameter.score)

        patient_ms_scores = [score for score in patient_ms_scores if score is not None]
        if patient_ms_scores:
            mean_patient_ms_score = statistics.mean(patient_ms_scores)
        else:
            mean_patient_ms_score = None

        ms_count = sum(score > 0.75 for score in patient_ms_scores)
        norm_count = len(patient_ms_scores) - ms_count

        for patient_record in record.patient.records:
            ms_summary_parameter = MsSummaryParameter(
                MsSummaryParameterValue(score=mean_patient_ms_score, ms_count=ms_count, norm_count=norm_count))
            ms_summary_parameter = patient_record.add_parameter_or_modify_value(ms_summary_parameter)

        patient_records_count = len(record.patient.records)
        if patient_records_count < 2:
            return

        ms_summary_column = self._table_visualizer.journal_viewer.column_number(MsSummaryTableColumn)
        first_patient_record = record.patient.records[0]
        first_patient_record_row = self._table_visualizer.journal_viewer.record_row(first_patient_record)
        self._table_visualizer.journal_viewer.set_span(
            first_patient_record_row, ms_summary_column, patient_records_count, 1)

    def _on_record_parameter_added_or_changed(self, record: PatientRetinalFundusRecord, parameter: ObjectParameter):
        if isinstance(parameter, MsPredictionParameter):
            self._aggregate_patient_ms_predictions(record)
