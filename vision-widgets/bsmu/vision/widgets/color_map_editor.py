from PySide2.QtCore import QDateTime, Qt, QPointF, QRectF
from PySide2.QtGui import QPainter, QLinearGradient, QGradient, QColor, qRgb
from PySide2.QtWidgets import (QWidget, QHeaderView, QHBoxLayout, QTableView, QGraphicsEllipseItem, QGraphicsItem,
                               QSizePolicy)
from PySide2.QtCharts import QtCharts


class Widget(QWidget):
    def __init__(self):
        super().__init__()

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
        plotAreaGradient.setColorAt(1.0, QColor('green'))
        plotAreaGradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        self.chart.setPlotAreaBackgroundBrush(plotAreaGradient)
        self.chart.setPlotAreaBackgroundVisible(True)
        # self.chart.setBackgroundBrush(plotAreaGradient)

        # Creating QChartView
        self.chart_view = QtCharts.QChartView(self.chart)
        # self.chart_view.setRubberBand(QtCharts.QChartView.RectangleRubberBand)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        s = self.chart.scene()
        print('scene', s, self.chart_view.scene())

        ppp = self.chart.mapToPosition(QPointF(4, 4))#, self.ser)
        print('ppp', ppp)

        self.circle_r = 20
        self.circle = QGraphicsEllipseItem(QRectF(ppp.x() - self.circle_r, ppp.y() - self.circle_r, 2 * self.circle_r, 2 * self.circle_r), self.chart)
        self.circle.setFlags(QGraphicsItem.ItemIsMovable)
        s.addItem(self.circle)

        # QWidget Layout
        self.main_layout = QHBoxLayout()

        self.main_layout.addWidget(self.chart_view)

        # Set the layout to the QWidget
        self.setLayout(self.main_layout)

    def resizeEvent(self, resize_event: QResizeEvent):
        min_tick_count = self.axis_x.max() - self.axis_x.min() + 1
        tick_count = min(min_tick_count, self.width() / 50)
        self.axis_x.setTickCount(round(tick_count))

        ppp = self.chart.mapToPosition(QPointF(4, 4))#, self.ser)
        print('res ppp', ppp)
        self.circle.setPos(ppp.x(), ppp.y())  # in the scene coordinates

    def add_series(self, name, columns, axis_x):
        # Create QLineSeries
        self.series = QtCharts.QLineSeries()
        self.series.setName(name)

        # Filling QLineSeries
        for i in range(10):
            # Getting the data

            x = y = i

            if x > 0 and y > 0:
                print('append', x, y)
                self.series.append(x, y)

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
