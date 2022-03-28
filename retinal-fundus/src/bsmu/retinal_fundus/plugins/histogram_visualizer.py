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
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
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
        self._disk_region_selector = None
        self._main_window = None

        raise NotImplementedError


class HistogramColorRepresentation:
    NAME = ''
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

    NEURORETINAL_RIM_BINARY_MASK_LAYER_NAME = 'neuroretinal-rim-binary-mask'
    NEURORETINAL_RIM_SOFT_MASK_LAYER_NAME = 'neuroretinal-rim-soft-mask'

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
        self._journal_record_selected_connection = QMetaObject.Connection()
        self._disk_selected_regions_changed_connection = QMetaObject.Connection()

        self._neuroretinal_rim_histogram_visualizing: bool = False

        self._chart: Chart | None = None
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
            self._disk_selected_regions_changed_connection = \
                self._disk_region_selector.selected_regions_changed.connect(self._on_disk_selected_regions_changed)
            self._start_to_visualize_neuroretinal_rim_histogram_for_record(self._table_visualizer.selected_record)
            self._table_visualizer.detailed_info_viewer.add_widget(self._chart_view)
            if len(self._chart.series()) == 0:
                self._hide_chart()
        else:
            self._table_visualizer.detailed_info_viewer.remove_widget(self._chart_view)
            self._stop_to_visualize_neuroretinal_rim_histogram()
            QObject.disconnect(self._journal_record_selected_connection)
            QObject.disconnect(self._disk_selected_regions_changed_connection)
            self._chart_view = None
            self._chart = None

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        self._stop_to_visualize_neuroretinal_rim_histogram()
        self._start_to_visualize_neuroretinal_rim_histogram_for_record(record)

    def _on_disk_selected_regions_changed(self):
        self._visualize_neuroretinal_rim_histogram_without_repeated_calls()

    def _start_to_visualize_neuroretinal_rim_histogram_for_record(self, record: PatientRetinalFundusRecord):
        if record is None:
            return

        self._visualized_record = record
        # Disk, cup or vessels mask layers can be added later, so we have to be notified about |layer_added| signal
        self._visualized_record_image_layer_added_connection = \
            self._visualized_record.layered_image.layer_added.connect(self._on_visualized_record_image_layer_added)
        self._visualize_neuroretinal_rim_histogram_without_repeated_calls()

    def _stop_to_visualize_neuroretinal_rim_histogram(self):
        QObject.disconnect(self._visualized_record_image_layer_added_connection)
        self._visualized_record = None

    def _on_visualized_record_image_layer_added(self, image_layer: ImageLayer):
        self._visualize_neuroretinal_rim_histogram_without_repeated_calls()

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

    def _show_chart(self):
        self._chart.draw_mode = Chart.DrawMode.CHART

    def _hide_chart(self):
        self._chart.removeAllSeries()
        for axis in self._chart.axes():
            self._chart.removeAxis(axis)

        self._chart.draw_mode = Chart.DrawMode.NO_DATA

    def _visualize_neuroretinal_rim_histogram_without_repeated_calls(self):
        if self._neuroretinal_rim_histogram_visualizing:
            return

        self._neuroretinal_rim_histogram_visualizing = True
        self._visualize_neuroretinal_rim_histogram()
        self._neuroretinal_rim_histogram_visualizing = False

    def _visualize_neuroretinal_rim_histogram(self):
        if self._visualized_record is None:
            self._hide_chart()
            return

        neuroretinal_rim_mask = self._calculate_record_neuroretinal_rim_mask(self._visualized_record)
        if neuroretinal_rim_mask is None:
            self._hide_chart()
            return

        neuroretinal_rim_float_mask = neuroretinal_rim_mask / 255

        # Use mask of |self._disk_region_selector| to analyze only selected disk regions
        if self._disk_region_selector.disk_region is not None:
            neuroretinal_rim_float_mask_in_disk_region = \
                self._disk_region_selector.disk_region.pixels(neuroretinal_rim_float_mask)
            neuroretinal_rim_float_mask_in_disk_region[self._disk_region_selector.selected_sectors_mask == 0] = 0

        neuroretinal_rim_bool_mask = neuroretinal_rim_float_mask > 0.5
        if not neuroretinal_rim_bool_mask.any():
            self._hide_chart()
            return

        histogram_image_pixels = self._histogram_color_representation.from_rgb(self._visualized_record.image.array)
        # mean = np.mean(histogram_image_pixels, axis=(0, 1), where=neuroretinal_rim_bool_mask)
        histogram_range = (histogram_image_pixels.min(), histogram_image_pixels.max())
        self._histogram_channel_area_series.clear()
        self._histogram_channel_line_series.clear()
        for channel in range(histogram_image_pixels.shape[-1]):
            channel_pixels = histogram_image_pixels[..., channel]
            channel_histogram, channel_histogram_bin_edges = np.histogram(
                channel_pixels, bins=self.BIN_COUNT, range=histogram_range, weights=neuroretinal_rim_float_mask)
            channel_mean = np.mean(channel_pixels, where=neuroretinal_rim_bool_mask)
            channel_std = np.std(channel_pixels, where=neuroretinal_rim_bool_mask)
            series_name = self._histogram_color_representation.NAME[channel]
            series_name += f': μ={channel_mean:.2f}; σ={channel_std:.2f}'
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
