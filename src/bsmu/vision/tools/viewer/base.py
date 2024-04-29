from __future__ import annotations

from PySide6.QtCore import QObject


class DataViewerTool(QObject):
    def __init__(self, viewer: DataViewer):
        super().__init__()

        self.viewer = viewer
