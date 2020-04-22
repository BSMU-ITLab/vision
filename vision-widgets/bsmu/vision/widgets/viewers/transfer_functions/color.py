from __future__ import annotations

import itertools

from PySide2.QtCharts import QtCharts
from PySide2.QtCore import Qt, QPointF, QRectF
from PySide2.QtGui import QPainter, QLinearGradient, QGradient, QPen, QBrush, QColor, QMatrix
from PySide2.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGridLayout, QColorDialog, QGraphicsItem

from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision_core.transfer_functions.color import ColorTransferFunction


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class ColorTransferFunctionPointView(QGraphicsEllipseItem):
    def __init__(self, viewer: ColorTransferFunctionViewer, point: ColorTransferFunctionPoint):
        super().__init__()

        self.viewer = viewer
        self.point = point
        self.chart = self.viewer.chart
        self.radius = None

        self._moving = False
        self._background_brush = QBrush(QColor(205, 205, 205, 255), Qt.DiagCrossPattern)

        self._update_brush()

        pen = QPen(QColor('#606060'), 2)
        self.setPen(pen)

        self.point.x_changed.connect(self._on_point_x_changed)
        self.point.color_array_changed.connect(self._on_point_color_array_changed)

    def _on_point_x_changed(self, x: float):
        self.update()

    def _on_point_color_array_changed(self, color_array: np.ndarray):
        self._update_brush()

    def _update_brush(self):
        self.setBrush(self.point.color)

    def update(self, rect: QRectF = QRectF()):
        super().update(rect)

        self.radius = min(self.viewer.chart_rect_f.width() / 20, self.viewer.chart_rect_f.height() / 4)

        center_y = (self.viewer.axis_y.max() - self.viewer.axis_y.min()) / 2
        center_pos = self.chart.mapToPosition(QPointF(self.point.x, center_y))
        radius_point = QPointF(self.radius, self.radius)
        self.setRect(QRectF(center_pos - radius_point, center_pos + radius_point))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setBackgroundMode(Qt.OpaqueMode)
        # painter.setBackground(Qt.white)
        painter.setBrush(self._background_brush)
        painter.drawEllipse(self.rect())

        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawEllipse(self.rect())

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseDoubleClickEvent(event)

        selected_color = QColorDialog.getColor(
            self.point.color, title='Select Point Color',
            options=QColorDialog.ColorDialogOptions() | QColorDialog.ShowAlphaChannel)
        if selected_color.isValid():
            self.point.color = selected_color

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self._moving = True

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self._moving = False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._moving:
            chart_pos = self.chart.mapFromScene(event.scenePos())
            self.point.x = self.chart.mapToValue(chart_pos).x()


class ColorTransferFunctionIntervalView(QGraphicsRectItem):
    def __init__(self, viewer: ColorTransferFunctionViewer,
                 begin_point: ColorTransferFunctionPoint, end_point: ColorTransferFunctionPoint):
        super().__init__()

        self.viewer = viewer
        self.begin_point = begin_point
        self.end_point = end_point
        self.chart = self.viewer.chart

        self.brush_gradient = QLinearGradient()
        self.brush_gradient.setStart(QPointF(0, 0))
        self.brush_gradient.setFinalStop(QPointF(1, 0))
        self.brush_gradient.setCoordinateMode(QGradient.ObjectMode)

        self._update_brush()

        self.setPen(QColor('#404040'))

        self.begin_point.x_changed.connect(self._on_point_x_changed)
        self.end_point.x_changed.connect(self._on_point_x_changed)

        self.begin_point.color_array_changed.connect(self._on_begin_point_color_array_changed)
        self.end_point.color_array_changed.connect(self._on_end_point_color_array_changed)

    def _on_point_x_changed(self, x: float):
        self.update()

    def _on_begin_point_color_array_changed(self, color_array: np.ndarray):
        self._update_brush()

    def _on_end_point_color_array_changed(self, color_array: np.ndarray):
        self._update_brush()

    def _update_brush(self):
        self.brush_gradient.setColorAt(0, self.begin_point.color)
        self.brush_gradient.setColorAt(1, self.end_point.color)
        self.setBrush(self.brush_gradient)

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
        # self.chart.legend().hide()
        self.chart_rect_f = None

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
        interval_view = ColorTransferFunctionIntervalView(self, begin_point, end_point)
        self.scene.addItem(interval_view)
        self._interval_views.append(interval_view)

    def _add_point_views(self):
        for point in self.data.points:
            self._add_point_view(point)

    def _add_point_view(self, point: ColorTransferFunctionPoint):
        point_view = ColorTransferFunctionPointView(self, point)
        self.scene.addItem(point_view)
        self._point_views.append(point_view)

    def _update_chart_size(self):
        top_left_pos = self.chart.mapToPosition(QPointF(self.axis_x.min(), self.axis_y.max()))
        bottom_right_pos = self.chart.mapToPosition(QPointF(self.axis_x.max(), self.axis_y.min()))
        self.chart_rect_f = QRectF(top_left_pos, bottom_right_pos)

    def resizeEvent(self, resize_event: QResizeEvent):
        self._update_chart_size()

        # min_tick_count = self.axis_x.max() - self.axis_x.min() + 1
        # tick_count = min(min_tick_count, self.width() / 50)
        tick_count = self.chart_rect_f.width() / 50
        self.axis_x.setTickCount(round(tick_count))

        self.axis_y.setTickCount(round(self.chart_rect_f.height() / 20))

        for interval_view in self._interval_views:
            interval_view.update()
        for point_view in self._point_views:
            point_view.update()

    def add_series(self):
        series = QtCharts.QLineSeries()
        series.setName('Color Transfer Function')
        self.chart.addSeries(series)
        series.attachAxis(self.axis_x)
        series.attachAxis(self.axis_y)
        return series
