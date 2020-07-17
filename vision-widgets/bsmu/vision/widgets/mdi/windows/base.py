from __future__ import annotations

import numpy as np
from PySide2.QtCore import QPoint, QRect
from PySide2.QtWidgets import QMdiSubWindow


class DataViewerSubWindow(QMdiSubWindow):
    def __init__(self, viewer: DataViewer):
        super().__init__()

        self.viewer = viewer

        self.layout_anchors = None
        self._laying_out = False

        self.update_window_title()

    @property
    def viewer(self):
        return self.widget()

    @viewer.setter
    def viewer(self, value):
        self.setWidget(value)

    def update_window_title(self):
        self.setWindowTitle(self.viewer.data_path_name)

    def lay_out_to_anchors(self):
        if self.layout_anchors is None:
            return

        mdi = self.mdiArea()
        mdi_size = np.array([mdi.width(), mdi.height()])
        layout_rect_angle_point_coords = self.layout_anchors * mdi_size
        layout_rect = QRect(QPoint(*layout_rect_angle_point_coords[0]), QPoint(*layout_rect_angle_point_coords[1]))

        self._laying_out = True
        self.setGeometry(layout_rect)
        self._laying_out = False

    def resizeEvent(self, resize_event: QResizeEvent):
        super().resizeEvent(resize_event)

        if not self._laying_out and self.layout_anchors is not None:
            mdi = self.mdiArea()

            top_left_point = self.mapTo(mdi, self.rect().topLeft())
            bottom_right_point = self.mapTo(mdi, self.rect().bottomRight())

            mdi_size = np.array([mdi.width(), mdi.height()])
            self.layout_anchors[0] = np.array([top_left_point.x(), top_left_point.y()]) / mdi_size
            self.layout_anchors[1] = np.array([bottom_right_point.x(), bottom_right_point.y()]) / mdi_size
