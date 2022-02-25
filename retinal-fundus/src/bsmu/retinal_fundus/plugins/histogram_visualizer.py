from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, \
    QAreaSeries
from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QPainter, QColor, QPen

import bsmu.vision.core.converters.image as image_converter
from bsmu.retinal_fundus.plugins.main_window import HistogramsMenu
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer
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
        self._retinal_fundus_table_visualizer: RetinalFundusTableVisualizer | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._histogram_visualizer: RetinalFundusHistogramVisualizer | None = None

    @property
    def histogram_visualizer(self) -> RetinalFundusHistogramVisualizer | None:
        return self._histogram_visualizer

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._retinal_fundus_table_visualizer = self._retinal_fundus_table_visualizer_plugin.table_visualizer
        self._mdi = self._mdi_plugin.mdi

        self._histogram_visualizer = RetinalFundusHistogramVisualizer(self._retinal_fundus_table_visualizer)

        self._main_window.add_menu_action(
            HistogramsMenu,
            'Neuroretinal Rim',
            self._histogram_visualizer.visualize_neuroretinal_rim_histogram,
            Qt.CTRL + Qt.Key_H
        )

    def _disable(self):
        self._histogram_visualizer = None

        self._mdi = None
        self._retinal_fundus_table_visualizer = None
        self._main_window = None

        raise NotImplementedError


class RetinalFundusHistogramVisualizer(QObject):
    def __init__(self, table_visualizer: RetinalFundusTableVisualizer):
        super().__init__()

        self._table_visualizer = table_visualizer

        # self._neuroretinal_rim_mask_palette = Palette.default_binary(255, [16, 107, 107])
        self._neuroretinal_rim_mask_palette = Palette.default_soft([16, 107, 107])

    def visualize_neuroretinal_rim_histogram(self):
        print('SE', self._table_visualizer.selected_record.image.path_name)

        # self._create_histogram_chart()
        # return

        # a = np.array([1, 2, 2, 3, 3, 4, 4, 4, 5])
        # w = np.array([0, 1, 1, 0, 0, 1, 1, 0, 1])
        # hist, bin_edges = np.histogram(a, bins=5, weights=w)
        # print('HHHH', hist)
        # print('bins', bin_edges)

        selected_record = self._table_visualizer.selected_record
        neuroretinal_rim_mask_pixels = selected_record.disk_mask.array
        # neuroretinal_rim_mask_pixels[(selected_record.cup_mask.array > 31) | (selected_record.vessels_mask.array > 31)] = 0
        # selected_record.layered_image.add_layer_from_image(
        #     FlatImage(neuroretinal_rim_mask_pixels, palette=self._neuroretinal_rim_mask_palette), 'neuroretinal-rim')

        cup_and_vessels_union = np.maximum(selected_record.cup_mask.array, selected_record.vessels_mask.array)
        cup_and_vessels_union_in_disk_region = np.minimum(cup_and_vessels_union, neuroretinal_rim_mask_pixels)

        neuroretinal_rim_mask_pixels -= cup_and_vessels_union_in_disk_region
        selected_record.layered_image.add_layer_from_image(
            FlatImage(cup_and_vessels_union_in_disk_region), 'cup-and-vessels-union-in-disk-region')

        selected_record.layered_image.add_layer_from_image(
            FlatImage(neuroretinal_rim_mask_pixels, palette=self._neuroretinal_rim_mask_palette), 'neuroretinal-rim')


        print('ssss', neuroretinal_rim_mask_pixels.shape, neuroretinal_rim_mask_pixels.min(),
              neuroretinal_rim_mask_pixels.max(), np.unique(neuroretinal_rim_mask_pixels))

        neuroretinal_rim_mask_normalized_pixels = image_converter.normalized(neuroretinal_rim_mask_pixels)

        print('ssss-normalized', neuroretinal_rim_mask_normalized_pixels.shape, neuroretinal_rim_mask_normalized_pixels.min(),
              neuroretinal_rim_mask_normalized_pixels.max(), np.unique(neuroretinal_rim_mask_normalized_pixels))

        print('weights-mean', np.mean(neuroretinal_rim_mask_normalized_pixels))

        r_channel = selected_record.image.array[..., 0]
        g_channel = selected_record.image.array[..., 1]
        b_channel = selected_record.image.array[..., 2]
        range_min = selected_record.image.array.min()
        range_max = selected_record.image.array.max()
        hist_range = (range_min, range_max)
        bins = 70

        r_hist, r_bin_edges = np.histogram(r_channel, bins=bins, range=hist_range, weights=neuroretinal_rim_mask_normalized_pixels)
        print('HHHH', r_hist)
        print('bins', r_bin_edges)
        print('LEN', len(r_hist), len(r_bin_edges))
        # self._r_series, self._r_line_series = self._create_histogram_area_series(r_hist, r_bin_edges, QPen(QColor(180, 50, 0), 2), QColor(255, 0, 0, 50))
        self._r_series, self._r_line_series = self._create_histogram_area_series(r_hist, r_bin_edges,
                                                                                 QPen(QColor(144, 58, 58), 2),
                                                                                 QColor(180, 71, 71, 50))

        g_hist, g_bin_edges = np.histogram(g_channel, bins=bins, range=hist_range, weights=neuroretinal_rim_mask_normalized_pixels)
        self._g_series, self._g_line_series = self._create_histogram_area_series(g_hist, g_bin_edges, QPen(QColor(58, 144, 67), 2),
                                                      QColor(71, 178, 84, 50))

        b_hist, b_bin_edges = np.histogram(b_channel, bins=bins, range=hist_range, weights=neuroretinal_rim_mask_normalized_pixels)
        self._b_series, self._b_line_series = self._create_histogram_area_series(b_hist, b_bin_edges,
                                                                                 QPen(QColor(58, 59, 144), 2),
                                                                                 QColor(73, 77, 178, 50))

        self._create_histogram_chart_for_data([self._r_series, self._g_series, self._b_series])

    def _create_histogram_area_series(self, hist, bin_edges, pen, brush):
        line_series = QLineSeries()
        for i, hist_value in enumerate(hist):
            if i == 0:
                line_series.append(bin_edges[i], 0)
            line_series.append(bin_edges[i], hist_value)
            line_series.append(bin_edges[i + 1], hist_value)
            # line_series.append(bin_edges[i + 1], 0)

        area_series = QAreaSeries(line_series)
        area_series.setPen(pen)
        area_series.setBrush(brush)

        return area_series, line_series

    def _create_histogram_chart_for_data(self, series):
        chart = QChart()
        for s in series:
            chart.addSeries(s)

        chart.createDefaultAxes()

        self._chart_view = QChartView(chart)
        self._chart_view.setRenderHint(QPainter.Antialiasing)

        self._chart_view.show()

    def _create_histogram_chart(self):
        # from PySide6.QtCharts import QChart, QChartView, QLineSeries, QAreaSeries
        # from PySide6.QtGui import QPainter, QColor, QPen

        pen = QPen(QColor(0, 50, 180), 3)
        pen_r = QPen(QColor(180, 50, 0), 3)

        self._line_series = QLineSeries()
        self._line_series.append(0, 10)
        self._line_series.append(1, 10)
        self._line_series.append(1, 0)
        self._line_series.append(1, 3)
        self._line_series.append(2, 3)
        self._line_series.append(2, 0)

        self._line_series_b = QLineSeries()
        self._line_series_b.append(0, 5)
        self._line_series_b.append(1, 5)
        self._line_series_b.append(1, 0)
        self._line_series_b.append(1, 8)
        self._line_series_b.append(2, 8)
        self._line_series_b.append(2, 0)
        # line_series.setBrush(QBrush(QColor(255, 0, 0)))
        # self._line_series.setPen(pen)
        # line_series.setColor(QColor(255, 0, 0))

        self._line_series_bot = QLineSeries()
        self._line_series_bot.append(0, 0)
        self._line_series_bot.append(2, 0)

        self._area_series_b = QAreaSeries(self._line_series_b)
        self._area_series_b.setBrush(QColor(0, 0, 255, 50))
        self._area_series_b.setPen(pen)

        self._area_series = QAreaSeries(self._line_series)
        self._area_series.setBrush(QColor(255, 0, 0, 50))
        self._area_series.setPen(pen_r)
        # self._area_series.setColor(QColor(255, 0, 0))

        chart = QChart()
        chart.addSeries(self._area_series_b)
        chart.addSeries(self._area_series)
        # chart.setTitle("Simple barchart example")
        # chart.setAnimationOptions(QChart.SeriesAnimations)

        # chart.legend().setVisible(True)
        # chart.legend().setAlignment(Qt.AlignBottom)

        chart.createDefaultAxes()
        # chart.scene().addItem()
        # chart.axes(Qt.Horizontal)[0].setRange(0, 3)
        # chart.axes(Qt.Vertical)[0].setRange(0, 2)

        self._chart_view = QChartView(chart)
        self._chart_view.setRenderHint(QPainter.Antialiasing)

        self._chart_view.show()

        # self._chart_view.setRubberBand(QChartView.HorizontalRubberBand)
        #
        # self._chart_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self._chart_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # chart.zoomReset()


    def _create_histogram_chart_OLD(self):
        from PySide6.QtCharts import QBarSet, QBarSeries, QChart, QValueAxis, QChartView, QLineSeries, QAreaSeries
        from PySide6.QtGui import QPainter, QColor

        line_series = QLineSeries()
        line_series.append(0, 0)
        line_series.append(0, 5)
        line_series.append(1, 5)
        # line_series.append(1, 0)
        line_series.append(1, 8)
        line_series.append(2, 8)
        line_series.append(2, 0)
        # line_series.setBrush(QBrush(QColor(255, 0, 0)))
        # line_series.setPen(QColor(0, 255, 0))
        # line_series.setColor(QColor(255, 0, 0))

        line_series_bot = QLineSeries()
        line_series_bot.append(0, 0)
        line_series_bot.append(2, 0)

        self._area_series_b = QAreaSeries(line_series, line_series_bot)
        # area_series.setBrush(QColor(255, 0, 0))
        self._area_series_b.setColor(QColor(255, 0, 0))

        bar_set_r = QBarSet('R')
        bar_set_g = QBarSet('G')
        bar_set_b = QBarSet('B')

        bar_set_r.append([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30])
        # bar_set_r.append(1)
        # bar_set_r.append(2)
        # bar_set_r.append(3)
        bar_set_g.append(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
             30])

        bar_series = QBarSeries()
        bar_series.append(bar_set_r)#, bar_set_g, bar_set_b])

        bar_series_2 = QBarSeries()
        bar_series_2.append(bar_set_g)
        # bar_series.setBarWidth(1.5)
        # bar_series.append(bar_set_r)
        # bar_series.append(bar_set_g)
        # bar_series.append(bar_set_b)

        chart = QChart()
        # chart.addSeries(bar_series)
        # chart.addSeries(bar_series_2)
        # chart.addSeries(line_series)
        chart.addSeries(self._area_series_b)
        chart.setTitle("Simple barchart example")
        # chart.setAnimationOptions(QChart.SeriesAnimations)

        categories = [str(i * 8.5) for i in range(30)]
        print('cat', categories)
        # categories = ['Jan', 'Feb', 'Mar']
        # axis_x = QBarCategoryAxis()
        # axis_x.append(categories)

        axis_x = QValueAxis()
        # axis_x.setRange(0, 255)
        axis_x.setMin(0)
        axis_x.setMax(255)
        axis_x.setTickInterval(8.5)
        axis_x.setTickType(QValueAxis.TicksFixed)
        axis_x.setMinorTickCount(0)

        # chart.addAxis(axis_x, Qt.AlignBottom)
        bar_series.attachAxis(axis_x)
        bar_series_2.attachAxis(axis_x)

        axis_y = QValueAxis()
        # axis_y.setRange(0, 15)
        # chart.addAxis(axis_y, Qt.AlignLeft);
        bar_series.attachAxis(axis_y)
        bar_series_2.attachAxis(axis_y)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)

        chart.createDefaultAxes()

        self._chart_view = QChartView(chart)
        # self._chart_view.scene().addItem()
        self._chart_view.setRenderHint(QPainter.Antialiasing)

        self._chart_view.show()

        # self._chart_view.setRubberBand(QChartView.HorizontalRubberBand)
        #
        # self._chart_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self._chart_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # chart.zoomReset()
