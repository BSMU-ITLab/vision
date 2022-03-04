from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import skimage.color
from PySide6.QtCharts import QChart, QChartView, QLineSeries, \
    QAreaSeries
from PySide6.QtCore import Qt, QObject, QMetaObject
from PySide6.QtGui import QPainter, QColor, QPen

from bsmu.retinal_fundus.plugins.main_window import HistogramsMenu
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Type, List

    from PySide6.QtCharts import QAbstractSeries

    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class RetinalFundusHistogramVisualizerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
            mdi_plugin: MdiPlugin
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._retinal_fundus_table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._rgb_histogram_visualizer: RetinalFundusHistogramVisualizer | None = None
        self._hsv_histogram_visualizer: RetinalFundusHistogramVisualizer | None = None

    @property
    def rgb_histogram_visualizer(self) -> RetinalFundusHistogramVisualizer | None:
        return self._rgb_histogram_visualizer

    @property
    def hsv_histogram_visualizer(self) -> RetinalFundusHistogramVisualizer | None:
        return self._hsv_histogram_visualizer

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer
        self._mdi = self._mdi_plugin.mdi

        self._rgb_histogram_visualizer = RetinalFundusHistogramVisualizer(
            self._table_visualizer, RgbHistogramColorRepresentation)
        self._hsv_histogram_visualizer = RetinalFundusHistogramVisualizer(
            self._table_visualizer, HsvHistogramColorRepresentation)

        histograms_menu = self._main_window.menu(HistogramsMenu)
        neuroretinal_rim_menu = histograms_menu.addMenu('Neuroretinal Rim')
        rgb_neuroretinal_rim_histogram_action = neuroretinal_rim_menu.addAction('RGB', None, Qt.CTRL + Qt.Key_R)
        hsv_neuroretinal_rim_histogram_action = neuroretinal_rim_menu.addAction('HSV', None, Qt.CTRL + Qt.Key_H)

        rgb_neuroretinal_rim_histogram_action.setCheckable(True)
        hsv_neuroretinal_rim_histogram_action.setCheckable(True)

        rgb_neuroretinal_rim_histogram_action.triggered.connect(
            self._rgb_histogram_visualizer.on_visualize_neuroretinal_rim_histogram_toggled)
        hsv_neuroretinal_rim_histogram_action.triggered.connect(
            self._hsv_histogram_visualizer.on_visualize_neuroretinal_rim_histogram_toggled)

    def _disable(self):
        self._rgb_histogram_visualizer = None
        self._hsv_histogram_visualizer = None

        self._mdi = None
        self._table_visualizer = None
        self._main_window = None

        raise NotImplementedError


class HistogramColorRepresentation:
    name = ''
    channel_pens = (
        QPen(QColor(144, 58, 58), 2),
        QPen(QColor(58, 144, 67), 2),
        QPen(QColor(58, 59, 144), 2),
    )
    channel_brushes = (
        QColor(180, 71, 71, 50),
        QColor(71, 178, 84, 50),
        QColor(73, 77, 178, 50),
    )

    @staticmethod
    def from_rgb(rgb: np.ndarray) -> np.ndarray:
        return rgb


class RgbHistogramColorRepresentation(HistogramColorRepresentation):
    name = 'RGB'


class HsvHistogramColorRepresentation(HistogramColorRepresentation):
    name = 'HSV'

    @staticmethod
    def from_rgb(rgb: np.ndarray):
        return skimage.color.rgb2hsv(rgb)


class RetinalFundusHistogramVisualizer(QObject):
    BIN_COUNT = 70

    NEURORETINAL_RIM_BINARY_MASK_LAYER_NAME = 'neuroretinal-rim-binary-mask'
    NEURORETINAL_RIM_SOFT_MASK_LAYER_NAME = 'neuroretinal-rim-soft-mask'

    def __init__(
            self,
            table_visualizer: RetinalFundusTableVisualizer,
            histogram_color_representation: Type[HistogramColorRepresentation]
    ):
        super().__init__()

        self._table_visualizer = table_visualizer
        self._histogram_color_representation = histogram_color_representation

        self._visualized_record: PatientRetinalFundusRecord | None = None
        self._visualized_record_image_layer_added_connection = QMetaObject.Connection()
        self._journal_record_selected_connection = QMetaObject.Connection()

        self._chart: QChart | None = None
        self._chart_view: QChartView | None = None

        # Store QAreaSeries and QLineSeries of channels, because otherwise their C++ objects will be destroyed
        self._histogram_channel_area_series = []
        self._histogram_channel_line_series = []

        self._neuroretinal_rim_mask_binary_palette = Palette.default_binary(255, [16, 107, 107])
        self._neuroretinal_rim_mask_soft_palette = Palette.default_soft([16, 107, 107])

    def on_visualize_neuroretinal_rim_histogram_toggled(self, checked: bool):
        if checked:
            self._create_chart()
            self._create_chart_view()
            self._journal_record_selected_connection = \
                self._table_visualizer.journal_viewer.record_selected.connect(self._on_journal_record_selected)
            self._start_to_visualize_neuroretinal_rim_histogram_for_record(self._table_visualizer.selected_record)
            self._table_visualizer.detailed_info_viewer.add_widget(self._chart_view)
            if len(self._chart.series()) == 0:
                self._hide_chart_view()
        else:
            self._table_visualizer.detailed_info_viewer.remove_widget(self._chart_view)
            self._stop_to_visualize_neuroretinal_rim_histogram()
            QObject.disconnect(self._journal_record_selected_connection)
            self._chart_view = None
            self._chart = None

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        self._stop_to_visualize_neuroretinal_rim_histogram()
        self._start_to_visualize_neuroretinal_rim_histogram_for_record(record)

    def _start_to_visualize_neuroretinal_rim_histogram_for_record(self, record: PatientRetinalFundusRecord):
        if record is None:
            return

        self._visualized_record = record
        # Disk, cup or vessels mask layers can be added later, so we have to be notified about |layer_added| signal
        self._visualized_record_image_layer_added_connection = \
            self._visualized_record.layered_image.layer_added.connect(self._on_visualized_record_image_layer_added)
        self._visualize_neuroretinal_rim_histogram()

    def _stop_to_visualize_neuroretinal_rim_histogram(self):
        QObject.disconnect(self._visualized_record_image_layer_added_connection)
        self._visualized_record = None

    def _on_visualized_record_image_layer_added(self, image_layer: ImageLayer):
        self._visualize_neuroretinal_rim_histogram()

    def _calculate_record_neuroretinal_rim_mask(
            self, record: PatientRetinalFundusRecord, binary: bool = False) -> np.ndarray | None:
        if record.disk_mask is None or record.cup_mask is None or record.vessels_mask is None:
            return None

        neuroretinal_rim_mask = np.copy(record.disk_mask.array)
        if binary:
            neuroretinal_rim_mask[(record.cup_mask.array > 31) | (record.vessels_mask.array > 31)] = 0
        else:
            cup_and_vessels_union = np.maximum(record.cup_mask.array, record.vessels_mask.array)
            cup_and_vessels_union_in_disk_region = np.minimum(cup_and_vessels_union, neuroretinal_rim_mask)

            neuroretinal_rim_mask -= cup_and_vessels_union_in_disk_region

            # cup_and_vessels_union_in_disk_region_layer_name = 'cup-and-vessels-union-in-disk-region-mask'
            # cup_and_vessels_union_in_disk_region_layer = record.layered_image.add_layer_or_modify_pixels(
            #     cup_and_vessels_union_in_disk_region_layer_name, cup_and_vessels_union_in_disk_region, FlatImage)

        neuroretinal_rim_mask_layer = record.layered_image.add_layer_or_modify_pixels(
            self.NEURORETINAL_RIM_BINARY_MASK_LAYER_NAME if binary else self.NEURORETINAL_RIM_SOFT_MASK_LAYER_NAME,
            neuroretinal_rim_mask,
            FlatImage,
            self._neuroretinal_rim_mask_binary_palette if binary else self._neuroretinal_rim_mask_soft_palette)

        return neuroretinal_rim_mask

    def _show_chart_view(self):
        if self._chart_view is not None and self._chart_view.isHidden() and self._chart_view.parentWidget() is not None:
            self._chart_view.show()

    def _hide_chart_view(self):
        if self._chart_view is not None and self._chart_view.isVisible():
            self._chart_view.hide()

    def _visualize_neuroretinal_rim_histogram(self):
        if self._visualized_record is None:
            self._hide_chart_view()
            return

        neuroretinal_rim_mask = self._calculate_record_neuroretinal_rim_mask(self._visualized_record)
        if neuroretinal_rim_mask is None:
            self._hide_chart_view()
            return

        neuroretinal_rim_float_mask = neuroretinal_rim_mask / 255

        histogram_image_pixels = self._histogram_color_representation.from_rgb(self._visualized_record.image.array)
        # mean = np.mean(histogram_image_pixels, axis=(0, 1), where=neuroretinal_rim_float_mask > 0.5)
        histogram_range = (histogram_image_pixels.min(), histogram_image_pixels.max())
        self._histogram_channel_area_series.clear()
        self._histogram_channel_line_series.clear()
        for channel in range(histogram_image_pixels.shape[-1]):
            channel_pixels = histogram_image_pixels[..., channel]
            channel_histogram, channel_histogram_bin_edges = np.histogram(
                channel_pixels, bins=self.BIN_COUNT, range=histogram_range, weights=neuroretinal_rim_float_mask)
            channel_mean = np.mean(channel_pixels, where=neuroretinal_rim_float_mask > 0.5)
            channel_std = np.std(channel_pixels, where=neuroretinal_rim_float_mask > 0.5)
            series_name = self._histogram_color_representation.name[channel]
            series_name += f': μ={channel_mean:.2f}; σ={channel_std:.2f}'
            area_series, line_series = self._create_histogram_area_series(
                channel_histogram,
                channel_histogram_bin_edges,
                series_name,
                self._histogram_color_representation.channel_pens[channel],
                self._histogram_color_representation.channel_brushes[channel],
            )
            self._histogram_channel_area_series.append(area_series)
            self._histogram_channel_line_series.append(line_series)
        self._visualize_chart_with_series_list(self._histogram_channel_area_series)

        self._show_chart_view()

    @staticmethod
    def _create_histogram_area_series(hist: np.ndarray, bin_edges: np.ndarray, name: str, pen: QPen, brush):
        line_series = QLineSeries()
        for i, hist_value in enumerate(hist):
            if i == 0:
                line_series.append(bin_edges[i], 0)
            line_series.append(bin_edges[i], hist_value)
            line_series.append(bin_edges[i + 1], hist_value)
            # line_series.append(bin_edges[i + 1], 0)

        area_series = QAreaSeries(line_series)
        area_series.setName(name)
        area_series.setPen(pen)
        area_series.setBrush(brush)

        return area_series, line_series

    def _create_chart(self):
        if self._chart is not None:
            return

        self._chart = QChart()
        self._chart.layout().setContentsMargins(0, 0, 0, 0)
        self._chart.setBackgroundRoundness(0)

    def _create_chart_view(self):
        if self._chart_view is not None:
            return

        self._chart_view = QChartView()
        self._chart_view.setRenderHint(QPainter.Antialiasing)

        self._chart_view.setChart(self._chart)

    def _visualize_chart_with_series_list(self, series_list: List[QAbstractSeries]):
        self._chart.removeAllSeries()
        for series in series_list:
            self._chart.addSeries(series)
        self._chart.createDefaultAxes()
