from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, \
    QAreaSeries
from PySide6.QtCore import Qt, QObject, QMetaObject, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QTextOption

from bsmu.retinal_fundus.plugins.main_window import HistogramsMenu
from bsmu.retinal_fundus.plugins.nrr_mask_calculator import RetinalFundusNrrMaskCalculator, NrrBboxParameter
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Type, List

    from PySide6.QtCharts import QAbstractSeries
    from PySide6.QtWidgets import QWidget, QStyleOptionGraphicsItem, QGraphicsItem

    from bsmu.retinal_fundus.plugins.disk_region_selector import RetinalFundusDiskRegionSelectorPlugin, \
        RetinalFundusDiskRegionSelector
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer, PatientRetinalFundusRecord
    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.core.models.base import ObjectParameter
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class RetinalFundusHistogramVisualizerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
        'retinal_fundus_disk_region_selector_plugin':
            'bsmu.retinal_fundus.plugins.disk_region_selector.RetinalFundusDiskRegionSelectorPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
            retinal_fundus_disk_region_selector_plugin: RetinalFundusDiskRegionSelectorPlugin,
            mdi_plugin: MdiPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._retinal_fundus_table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._retinal_fundus_disk_region_selector_plugin = retinal_fundus_disk_region_selector_plugin
        self._disk_region_selector: RetinalFundusDiskRegionSelector | None = None

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
        self._disk_region_selector = self._retinal_fundus_disk_region_selector_plugin.disk_region_selector
        self._mdi = self._mdi_plugin.mdi

        self._rgb_histogram_visualizer = RetinalFundusHistogramVisualizer(
            self._table_visualizer, self._disk_region_selector, RgbHistogramColorRepresentation)
        self._hsv_histogram_visualizer = RetinalFundusHistogramVisualizer(
            self._table_visualizer, self._disk_region_selector, HsvHistogramColorRepresentation)

        histograms_menu = self._main_window.menu(HistogramsMenu)
        nrr_menu = histograms_menu.addMenu('Neuroretinal Rim')
        rgb_nrr_histogram_action = nrr_menu.addAction('RGB', None, Qt.CTRL | Qt.Key_R)
        hsv_nrr_histogram_action = nrr_menu.addAction('HSV', None, Qt.CTRL | Qt.Key_H)

        rgb_nrr_histogram_action.setCheckable(True)
        hsv_nrr_histogram_action.setCheckable(True)

        rgb_nrr_histogram_action.triggered.connect(
            self._rgb_histogram_visualizer.on_visualize_nrr_histogram_toggled)
        hsv_nrr_histogram_action.triggered.connect(
            self._hsv_histogram_visualizer.on_visualize_nrr_histogram_toggled)

    def _disable(self):
        self._rgb_histogram_visualizer = None
        self._hsv_histogram_visualizer = None

        self._mdi = None
        self._table_visualizer = None
        self._disk_region_selector = None
        self._main_window = None

        raise NotImplementedError


class HistogramColorRepresentation:
    NAME = ''
    CHANNEL_DECIMALS_COUNT = (2, 2, 2)
    CHANNEL_PENS = (
        QPen(QColor(255, 158, 158), 2),
        QPen(QColor(143, 231, 143), 2),
        QPen(QColor(137, 180, 213), 2),
    )
    CHANNEL_BRUSHES = (
        QColor(255, 158, 158, 100),
        QColor(143, 231, 143, 100),
        QColor(137, 180, 213, 100),
    )

    @staticmethod
    def from_rgb(rgb: np.ndarray) -> np.ndarray:
        return rgb


class RgbHistogramColorRepresentation(HistogramColorRepresentation):
    NAME = 'RGB'


class HsvHistogramColorRepresentation(HistogramColorRepresentation):
    NAME = 'HSV'
    CHANNEL_DECIMALS_COUNT = (3, 3, 3)

    @staticmethod
    def from_rgb(rgb: np.ndarray):
        rgb = rgb.astype(np.float32) / 255

        # We can use skimage, but it is slower than OpenCV
        # hsv = skimage.color.rgb2hsv(rgb)

        hsv = cv.cvtColor(rgb, cv.COLOR_RGB2HSV)
        hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

        return hsv


class Chart(QChart):
    class DrawMode(Enum):
        NO_DATA = 1
        CHART = 2

    NO_DATA_TEXT = 'Chart\nNo data to display'

    def __init__(self, name: str = '', parent: QGraphicsItem = None):
        super().__init__(parent)

        self._name = name
        self._no_data_text = self.NO_DATA_TEXT
        if self._name:
            self._no_data_text = f'{self._name} {self._no_data_text}'

        self._draw_mode = None
        self.draw_mode = self.DrawMode.NO_DATA

        self._no_data_text_font = QFont()
        self._no_data_text_font.setPixelSize(12)
        self._no_data_text_font.setBold(True)

        self.setMargins(QMargins(0, 0, 2, 0))

    @property
    def draw_mode(self) -> DrawMode:
        return self._draw_mode

    @draw_mode.setter
    def draw_mode(self, value: DrawMode):
        if self._draw_mode != value:
            self._draw_mode = value

            self.setBackgroundVisible(self._draw_mode == self.DrawMode.CHART)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        super().paint(painter, option, widget)

        if self.draw_mode == self.DrawMode.NO_DATA:
            painter.save()

            painter.setPen(Qt.darkGray)
            painter.setFont(self._no_data_text_font)
            painter.drawText(self.boundingRect(), self._no_data_text, QTextOption(Qt.AlignCenter))

            painter.restore()


class RetinalFundusHistogramVisualizer(QObject):
    BIN_COUNT = 70

    def __init__(
            self,
            table_visualizer: RetinalFundusTableVisualizer,
            disk_region_selector: RetinalFundusDiskRegionSelector,
            histogram_color_representation: Type[HistogramColorRepresentation],
    ):
        super().__init__()

        self._table_visualizer = table_visualizer
        self._disk_region_selector = disk_region_selector
        self._histogram_color_representation = histogram_color_representation

        self._visualized_record: PatientRetinalFundusRecord | None = None
        self._visualized_record_image_layer_added_connection = QMetaObject.Connection()
        self._visualized_record_parameter_added_connection = QMetaObject.Connection()
        self._journal_record_selected_connection = QMetaObject.Connection()
        self._disk_selected_regions_changed_connection = QMetaObject.Connection()

        self._updated_histogram_visualizing: bool = False

        self._chart: Chart | None = None
        self._chart_view: QChartView | None = None

        # Store QAreaSeries and QLineSeries of channels, because otherwise their C++ objects will be destroyed
        self._histogram_channel_area_series = []
        self._histogram_channel_line_series = []

    def on_visualize_nrr_histogram_toggled(self, checked: bool):
        if checked:
            self._create_chart()
            self._create_chart_view()
            self._journal_record_selected_connection = \
                self._table_visualizer.journal_viewer.record_selected.connect(self._on_journal_record_selected)
            self._disk_selected_regions_changed_connection = \
                self._disk_region_selector.selected_regions_changed.connect(self._on_disk_selected_regions_changed)
            self._start_to_visualize_nrr_histogram_for_record(self._table_visualizer.selected_record)
            self._table_visualizer.detailed_info_viewer.add_widget(self._chart_view)
            if len(self._chart.series()) == 0:
                self._hide_chart()
        else:
            self._table_visualizer.detailed_info_viewer.remove_widget(self._chart_view)
            self._stop_to_visualize_nrr_histogram()
            QObject.disconnect(self._journal_record_selected_connection)
            QObject.disconnect(self._disk_selected_regions_changed_connection)
            self._chart_view = None
            self._chart = None

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        self._stop_to_visualize_nrr_histogram()
        self._start_to_visualize_nrr_histogram_for_record(record)

    def _on_disk_selected_regions_changed(self):
        self._updated_histogram_visualizing = False
        self._visualize_histogram()

    def _start_to_visualize_nrr_histogram_for_record(self, record: PatientRetinalFundusRecord):
        if record is None:
            return

        self._visualized_record = record
        # NRR-mask layer or Bbox-parameter can be added later, so we have to be notified about corresponding signals
        self._visualized_record_image_layer_added_connection = \
            self._visualized_record.layered_image.layer_added.connect(self._on_visualized_record_image_layer_added)
        self._visualized_record_parameter_added_connection = \
            self._visualized_record.parameter_added.connect(self._on_visualized_record_parameter_added)

        self._visualize_histogram()

    def _stop_to_visualize_nrr_histogram(self):
        QObject.disconnect(self._visualized_record_image_layer_added_connection)
        QObject.disconnect(self._visualized_record_parameter_added_connection)

        self._visualized_record = None
        self._updated_histogram_visualizing = False

    def _on_visualized_record_image_layer_added(self, image_layer: ImageLayer):
        self._visualize_histogram()

    def _on_visualized_record_parameter_added(self, parameter: ObjectParameter):
        self._visualize_histogram()

    def _show_chart(self):
        self._chart.draw_mode = Chart.DrawMode.CHART

    def _hide_chart(self):
        self._chart.removeAllSeries()
        for axis in self._chart.axes():
            self._chart.removeAxis(axis)

        self._chart.draw_mode = Chart.DrawMode.NO_DATA

    def _visualize_histogram(self):
        if self._updated_histogram_visualizing:
            return

        if self._visualized_record is None \
                or (nrr_mask := RetinalFundusNrrMaskCalculator.record_nrr_mask(self._visualized_record)) is None \
                or (nrr_bbox := self._visualized_record.parameter_value_by_type(NrrBboxParameter)) is None:
            self._hide_chart()
            return

        self._updated_histogram_visualizing = True

        nrr_mask = np.copy(nrr_mask.pixels)

        # Use mask of |self._disk_region_selector| to analyze only selected disk regions
        if self._disk_region_selector.disk_region is not None:
            nrr_mask_in_disk_region = \
                self._disk_region_selector.disk_region.pixels(nrr_mask)
            nrr_mask_in_disk_region[self._disk_region_selector.selected_sectors_mask == 0] = 0

        cropped_nrr_image = nrr_bbox.pixels(self._visualized_record.image.pixels)
        cropped_nrr_mask = nrr_bbox.pixels(nrr_mask)
        cropped_nrr_float_mask = cropped_nrr_mask / 255

        cropped_nrr_bool_mask = cropped_nrr_float_mask > 0.5
        if not cropped_nrr_bool_mask.any():
            self._hide_chart()
            return

        histogram_image_pixels = self._histogram_color_representation.from_rgb(cropped_nrr_image)
        # mean = np.mean(histogram_image_pixels, axis=(0, 1), where=cropped_nrr_bool_mask)
        histogram_range = (histogram_image_pixels.min(), histogram_image_pixels.max())
        self._histogram_channel_area_series.clear()
        self._histogram_channel_line_series.clear()
        for channel in range(histogram_image_pixels.shape[-1]):
            channel_pixels = histogram_image_pixels[..., channel]
            channel_histogram, channel_histogram_bin_edges = np.histogram(
                channel_pixels, bins=self.BIN_COUNT, range=histogram_range, weights=cropped_nrr_float_mask)
            channel_mean = np.mean(channel_pixels, where=cropped_nrr_bool_mask)
            channel_std = np.std(channel_pixels, where=cropped_nrr_bool_mask)
            series_name = self._histogram_color_representation.NAME[channel]
            decimals_count = self._histogram_color_representation.CHANNEL_DECIMALS_COUNT[channel]
            series_name += f': μ={channel_mean:.{decimals_count}f}; σ={channel_std:.{decimals_count}f}'
            area_series, line_series = self._create_histogram_area_series(
                channel_histogram,
                channel_histogram_bin_edges,
                series_name,
                self._histogram_color_representation.CHANNEL_PENS[channel],
                self._histogram_color_representation.CHANNEL_BRUSHES[channel],
            )
            self._histogram_channel_area_series.append(area_series)
            self._histogram_channel_line_series.append(line_series)
        self._visualize_chart_with_series_list(self._histogram_channel_area_series)

        self._show_chart()

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

        self._chart = Chart(self._histogram_color_representation.NAME)
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
