from __future__ import annotations

import numpy as np
from PySide2.QtCore import QPoint, QRect
from PySide2.QtWidgets import QMdiSubWindow


class DataViewerSubWindow(QMdiSubWindow):
    def __init__(self, viewer: DataViewer):
        super().__init__()

        self.viewer = viewer
        self.layout_anchors = None

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
        mdi = self.mdiArea()
        mdi_size = np.array([mdi.width(), mdi.height()])
        layout_rect_angle_point_coords = self.layout_anchors * mdi_size
        layout_rect = QRect(QPoint(*layout_rect_angle_point_coords[0]), QPoint(*layout_rect_angle_point_coords[1]))
        self.setGeometry(layout_rect)
