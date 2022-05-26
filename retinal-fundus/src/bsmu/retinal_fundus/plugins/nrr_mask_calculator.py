from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.widgets.visibility_v2 import Visibility

if TYPE_CHECKING:
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.image.layered import ImageLayer


class NrrBboxParameter(ObjectParameter):
    NAME = 'NRR BBox'


class RetinalFundusNrrMaskCalculatorPlugin(Plugin):
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

        self._nrr_mask_calculator: RetinalFundusNrrMaskCalculator | None = None

    @property
    def nrr_mask_calculator(self) -> RetinalFundusNrrMaskCalculator | None:
        return self._nrr_mask_calculator

    def _enable(self):
        self._table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer

        binary_mask = self.config.value('binary-mask')
        self._nrr_mask_calculator = RetinalFundusNrrMaskCalculator(binary_mask)

        self._table_visualizer.journal.record_added.connect(self._nrr_mask_calculator.add_observed_record)
        self._table_visualizer.journal.record_removing.connect(self._nrr_mask_calculator.remove_observed_record)

    def _disable(self):
        self._nrr_mask_calculator = None

        self._table_visualizer = None

        raise NotImplementedError


class RetinalFundusNrrMaskCalculator(QObject):
    NRR_BINARY_MASK_LAYER_NAME = 'nrr-binary-mask'
    NRR_SOFT_MASK_LAYER_NAME = 'nrr-soft-mask'

    def __init__(self, binary_mask: bool = False):
        super().__init__()

        self._binary_mask = binary_mask

        self._nrr_mask_binary_palette = Palette.default_binary(255, [16, 107, 107])
        self._nrr_mask_soft_palette = Palette.default_soft([16, 107, 107])

        self._nrr_mask_layer_visibility = Visibility(False, 0.2)

        self._connections_by_record = {}

    def add_observed_record(self, record: PatientRetinalFundusRecord):
        self._calculate_nrr_mask_for_record(record)
        self._calculate_nrr_bbox_for_record(record)

        record_connections = set()
        record_connections.add(
            record.create_connection(record.layered_image.layer_added, self._on_record_image_layer_added))
        record_connections.add(
            record.create_connection(record.disk_bbox_changed, self._on_record_disk_bbox_changed)
        )
        self._connections_by_record[record] = record_connections

    def remove_observed_record(self, record: PatientRetinalFundusRecord):
        record_connections = self._connections_by_record.pop(record)
        for connection in record_connections:
            connection.disconnect()

    @property
    def _mask_layer_name(self) -> str:
        return self.NRR_BINARY_MASK_LAYER_NAME if self._binary_mask else self.NRR_SOFT_MASK_LAYER_NAME

    @property
    def _mask_palette(self) -> Palette:
        return self._nrr_mask_binary_palette if self._binary_mask else self._nrr_mask_soft_palette

    def _calculate_nrr_mask_for_record(self, record: PatientRetinalFundusRecord):
        if record.image_by_layer_name(self._mask_layer_name) is not None:
            return

        if record.disk_mask is None or record.cup_mask is None or record.vessels_mask is None:
            return

        nrr_mask = np.copy(record.disk_mask.pixels)
        if self._binary_mask:
            nrr_mask[(record.cup_mask.pixels > 31) | (record.vessels_mask.pixels > 31)] = 0
        else:
            cup_and_vessels_union = np.maximum(record.cup_mask.pixels, record.vessels_mask.pixels)
            cup_and_vessels_union_in_disk_region = np.minimum(cup_and_vessels_union, nrr_mask)

            nrr_mask -= cup_and_vessels_union_in_disk_region

            # cup_and_vessels_union_in_disk_region_layer_name = 'cup-and-vessels-union-in-disk-region-mask'
            # cup_and_vessels_union_in_disk_region_layer = record.layered_image.add_layer_or_modify_pixels(
            #     cup_and_vessels_union_in_disk_region_layer_name, cup_and_vessels_union_in_disk_region, FlatImage)

        nrr_mask_layer = record.layered_image.add_layer_or_modify_pixels(
            self._mask_layer_name,
            nrr_mask,
            FlatImage,
            self._mask_palette,
            self._nrr_mask_layer_visibility)

    def _calculate_nrr_bbox_for_record(self, record: PatientRetinalFundusRecord):
        nrr_bbox_parameter = NrrBboxParameter(record.disk_bbox)
        record.add_parameter_or_update_value(nrr_bbox_parameter)

    def _on_record_image_layer_added(
            self, record: PatientRetinalFundusRecord, image_layer: ImageLayer, layer_index: int):
        self._calculate_nrr_mask_for_record(record)

    def _on_record_disk_bbox_changed(self, record: PatientRetinalFundusRecord, disk_bbox: BBox):
        self._calculate_nrr_bbox_for_record(record)
