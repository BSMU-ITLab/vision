from __future__ import annotations

from typing import Type

from PySide2.QtWidgets import QWidget

from bsmu.vision.plugin import Plugin


class DataViewerPlugin(Plugin):
    def __init__(self, app: App, data_viewer_cls: Type[DataViewer]):
        super().__init__(app)

        self.data_viewer_cls = data_viewer_cls


class DataViewer(QWidget):
    def __init__(self, data: Data = None):
        super().__init__()

        self.data = data
