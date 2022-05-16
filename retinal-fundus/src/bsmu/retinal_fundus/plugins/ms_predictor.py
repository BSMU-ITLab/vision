from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.inferencer import ModelParams as DnnModelParams
from bsmu.vision.dnn.predictor import Predictor as DnnPredictor

if TYPE_CHECKING:
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.bbox import BBox


class MsProbabilityParameter(ObjectParameter):
    NAME = 'MS Probability'


class MsProbabilityTableColumn(TableColumn):
    TITLE = 'MS\nProbability'
    OBJECT_PARAMETER_TYPE = MsProbabilityParameter


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

        ms_predictor_model_props = self.config.value('ms-predictor-model')
        ms_predictor_model_params = DnnModelParams(
            self.data_path(self._DNN_MODELS_DIR_NAME, ms_predictor_model_props['name']),
            ms_predictor_model_props['input-size'],
            ms_predictor_model_props['preprocessing-mode'],
        )
        self._ms_predictor = RetinalFundusMsPredictor(self._table_visualizer, ms_predictor_model_params)

        self._table_visualizer.add_column(MsProbabilityTableColumn)
        self._table_visualizer.journal.record_added.connect(self._ms_predictor.add_observed_record)

    def _disable(self):
        self._ms_predictor = None

        self._table_visualizer = None

        raise NotImplementedError


class RetinalFundusMsPredictor(QObject):
    def __init__(self, table_visualizer: RetinalFundusTableVisualizer, ms_predictor_model_params: DnnModelParams):
        super().__init__()

        self._table_visualizer = table_visualizer
        self._ms_predictor = DnnPredictor(ms_predictor_model_params)

    def add_observed_record(self, record: PatientRetinalFundusRecord):
        self._predict_for_record(record)

        record.disk_bbox_changed.connect(partial(self._on_record_disk_bbox_changed, record))

    def _predict_for_record(self, record: PatientRetinalFundusRecord):
        print('!!! predict_for_record')
        print('diskBbox', record.disk_bbox)

        if record.disk_bbox is None:
            return

        disk_region_bbox = record.disk_bbox.margins_added(
            round((record.disk_bbox.width + record.disk_bbox.height) / 2))
        disk_region_bbox.clip_to_shape(record.image.shape)
        disk_region_image = disk_region_bbox.pixels(record.image.pixels)


        # import skimage.io
        # skimage.io.imsave(r'D:\Temp\RetinalFundus-DB\test.png', disk_region_image)

        ms_probability = self._ms_predictor.predict(disk_region_image)
        #% temp_ms_probability = 30.3
        ms_probability_parameter = MsProbabilityParameter(ms_probability)

        # Get the parameter, maybe it's already exists
        # If it exists, then just update the value
        record.add_parameter(ms_probability_parameter)

    def _on_record_disk_bbox_changed(self, record: PatientRetinalFundusRecord, disk_bbox: BBox):
        self._predict_for_record(record)
