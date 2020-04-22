from __future__ import annotations

import itertools

from PySide2.QtCharts import QtCharts
from PySide2.QtCore import Qt, QPointF, QRectF
from PySide2.QtGui import QPainter, QLinearGradient, QGradient, QColor
from PySide2.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGridLayout

from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision_core.transfer_functions.color import ColorTransferFunction


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class ColorTransferFunctionPointView(QGraphicsEllipseItem):
    def __init__(self, chart: QtCharts.QChart, point: ColorTransferFunctionPoint):
        super().__init__()


class ColorTransferFunctionIntervalView(QGraphicsRectItem):
    def __init__(self, chart, begin_point: ColorTransferFunctionPoint, end_point: ColorTransferFunctionPoint):
        super().__init__()

        self.chart = chart
        self.begin_point = begin_point
        self.end_point = end_point

        plotAreaGradient = QLinearGradient()
        plotAreaGradient.setStart(QPointF(0, 0))
        plotAreaGradient.setFinalStop(QPointF(1, 0))
        plotAreaGradient.setColorAt(0, QColor(*self.begin_point.color_array))
        plotAreaGradient.setColorAt(1, QColor(*self.end_point.color_array))
        plotAreaGradient.setCoordinateMode(QGradient.ObjectMode)
        self.setBrush(plotAreaGradient)

    def update(self, rect: QRectF = QRectF()):
        print('interval view UPDATE')
        super().update(rect)

        top_left_interval_pos = self.chart.mapToPosition(QPointF(self.begin_point.x, 1))
        bottom_right_interval_pos = self.chart.mapToPosition(QPointF(self.end_point.x, 0))
        print('points', top_left_interval_pos, bottom_right_interval_pos)
        self.setRect(QRectF(top_left_interval_pos, bottom_right_interval_pos))


class ColorTransferFunctionViewer(DataViewer):
    def __init__(self, data: ColorTransferFunction = None):
        super().__init__(data)

        self.chart = QtCharts.QChart()

        self.axis_x = QtCharts.QValueAxis()
        # self.axis_x.setLabelFormat('%d')
        self.axis_x.setLabelFormat('%.1f')
        self.axis_x.setTitleText('Intensity')
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)

        self.axis_y = QtCharts.QValueAxis()
        # self.axis_y.setTickCount(10)
        self.axis_y.setLabelFormat('%.2f')
        # self.axis_y.setTitleText('Magnitude')
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)

        self.axis_x.setRange(0, self.data.points[-1].x)
        self.axis_y.setRange(0, 1)
        # Add an empty series, else |chart.mapToPosition| will no work
        self.series = self.add_series()

        self.chart_view = QtCharts.QChartView(self.chart)
        # self.chart_view.setRubberBand(QtCharts.QChartView.RectangleRubberBand)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        self.scene = self.chart_view.scene()

        self._interval_views = []
        self._point_views = []
        if self.data is not None:
            self._add_interval_views()
            self._add_point_views()

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.chart_view)
        self.setLayout(grid_layout)

    def _add_interval_views(self):
        for point, next_point in pairwise(self.data.points):
            if next_point is not None:
                self._add_interval_view(point, next_point)

    def _add_interval_view(self, begin_point: ColorTransferFunctionPoint, end_point: ColorTransferFunctionPoint):
        print('p:', begin_point.x, begin_point.color_array, '         --- next_p:', end_point.x, end_point.color_array)
        interval_view = ColorTransferFunctionIntervalView(self.chart, begin_point, end_point)
        self.scene.addItem(interval_view)
        self._interval_views.append(interval_view)

    def _add_point_views(self):
        for point in self.data.points:
            self._add_point_view(point)

    def _add_point_view(self, point: ColorTransferFunctionPoint):
        point_view = ColorTransferFunctionPointView(self.chart, point)
        self.scene.addItem(point_view)
        self._point_views.append(point_view)

    def resizeEvent(self, resize_event: QResizeEvent):
        # min_tick_count = self.axis_x.max() - self.axis_x.min() + 1
        # tick_count = min(min_tick_count, self.width() / 50)
        tick_count = self.width() / 70
        self.axis_x.setTickCount(round(tick_count))

        self.axis_y.setTickCount(round(self.height() / 70))

        for interval_view in self._interval_views:
            interval_view.update()

    def add_series(self):
        series = QtCharts.QLineSeries()
        series.setName('Color Transfer Function')
        self.chart.addSeries(series)
        series.attachAxis(self.axis_x)
        series.attachAxis(self.axis_y)
        return series
