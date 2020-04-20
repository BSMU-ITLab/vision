from __future__ import annotations

from PySide2.QtCharts import QtCharts
from PySide2.QtCore import Qt, QPointF, QRectF
from PySide2.QtGui import QPainter, QLinearGradient, QGradient, QColor
from PySide2.QtWidgets import QHBoxLayout, QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem

from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision_core.transfer_functions.color import ColorTransferFunction

import itertools


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


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

        top_left_interval_pos = self.chart.mapToPosition(QPointF(self.begin_point.x, 3))
        bottom_right_interval_pos = self.chart.mapToPosition(QPointF(self.end_point.x, 0))
        self.setRect(QRectF(top_left_interval_pos, bottom_right_interval_pos))


class ColorTransferFunctionViewer(DataViewer):
    def __init__(self, data: ColorTransferFunction = None):
        super().__init__(data)

        # Creating QChart
        self.chart = QtCharts.QChart()
        # self.chart.setAnimationOptions(QtCharts.QChart.AllAnimations)

        self.axis_x = QtCharts.QValueAxis()
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setTitleText('Intensity')
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)

        self.ser = self.add_series("Magnitude (Column 1)", [0, 1], self.axis_x)

        plotAreaGradient = QLinearGradient()
        plotAreaGradient.setStart(QPointF(0, 0))
        plotAreaGradient.setFinalStop(QPointF(1, 0))
        plotAreaGradient.setColorAt(0.0, QColor('red'))
        plotAreaGradient.setColorAt(0.5, QColor('yellow'))
        plotAreaGradient.setColorAt(1, QColor('green'))
        plotAreaGradient.setCoordinateMode(QGradient.ObjectMode)
        self.chart.setPlotAreaBackgroundBrush(plotAreaGradient)
        self.chart.setPlotAreaBackgroundVisible(True)

        # Creating QChartView
        self.chart_view = QtCharts.QChartView(self.chart)
        # self.chart_view.setRubberBand(QtCharts.QChartView.RectangleRubberBand)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        s = self.chart.scene()
        print('scene', s, self.chart_view.scene())

        ppp = self.chart.mapToPosition(QPointF(4, 4))#, self.ser)
        print('ppp', ppp)


        self._interval_views = []
        self._add_interval_views()


        self.circle_r = 20
        self.circle = QGraphicsEllipseItem(QRectF(ppp.x() - self.circle_r, ppp.y() - self.circle_r, 2 * self.circle_r, 2 * self.circle_r), self.chart)
        self.circle.setFlags(QGraphicsItem.ItemIsMovable)
        s.addItem(self.circle)

        # QWidget Layout
        self.main_layout = QHBoxLayout()

        self.main_layout.addWidget(self.chart_view)

        # Set the layout to the QWidget
        self.setLayout(self.main_layout)

    def _add_interval_views(self):
        if self.data is None:
            return

        for point, next_point in pairwise(self.data.points):
            if next_point is not None:
                self._add_interval_view(point, next_point)

    def _add_interval_view(self, begin_point: ColorTransferFunctionPoint, end_point: ColorTransferFunctionPoint):
        print('p:', begin_point.x, begin_point.color_array, '         --- next_p:', end_point.x, end_point.color_array)
        interval_view = ColorTransferFunctionIntervalView(self.chart, begin_point, end_point)
        self.chart.scene().addItem(interval_view)
        self._interval_views.append(interval_view)

    def resizeEvent(self, resize_event: QResizeEvent):
        min_tick_count = self.axis_x.max() - self.axis_x.min() + 1
        tick_count = min(min_tick_count, self.width() / 50)
        self.axis_x.setTickCount(round(tick_count))

        ppp = self.chart.mapToPosition(QPointF(4, 4))#, self.ser)
        print('res ppp', ppp)
        self.circle.setPos(ppp.x(), ppp.y())  # in the scene coordinates

        for interval_view in self._interval_views:
            interval_view.update()

    def add_series(self, name, columns, axis_x):
        # Create QLineSeries
        self.series = QtCharts.QLineSeries()
        self.series.setName(name)

        # Filling QLineSeries
        import scipy.interpolate as ip
        import numpy as np
        interpolator = ip.PchipInterpolator(np.array([-10, 1, 3, 9]), np.array([0, 0, 6, 9]))  # interpolator object
        x_new = np.linspace(0, 10, 50)  # example new x-axis
        y_new = interpolator(x_new)
        print('x_new', x_new)
        print('y_new', y_new)

        for i in range(50):
            # Getting the data
            # x = i
            # y = x * x

            # print('append', x, y)
            # self.series.append(x, y)
            self.series.append(x_new[i], y_new[i])

        self.chart.addSeries(self.series)

        # Setting X-axis
        self.series.attachAxis(self.axis_x)

        # Setting Y-axis
        self.axis_y = QtCharts.QValueAxis()
        self.axis_y.setTickCount(10)
        self.axis_y.setLabelFormat("%.2f")
        self.axis_y.setTitleText("Magnitude")
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        self.series.attachAxis(self.axis_y)
        return self.series
