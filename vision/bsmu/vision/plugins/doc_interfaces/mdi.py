from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import Signal
from PySide2.QtGui import QResizeEvent
from PySide2.QtWidgets import QMdiArea

from bsmu.vision.app.plugin import Plugin

if TYPE_CHECKING:
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class MdiPlugin(Plugin):
    DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi: Mdi | None = None

    @property
    def mdi(self) -> Mdi | None:
        return self._mdi

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window

        self._mdi = Mdi()
        self._main_window.setCentralWidget(self._mdi)

    def _disable(self):
        central_widget = self._main_window.centralWidget()
        if central_widget == self._mdi:
            self.main_window.takeCentralWidget()
        self._mdi.deleteLater()
        self._mdi = None


class Mdi(QMdiArea):
    resized = Signal(QResizeEvent)

    def __init__(self):
        super().__init__()

    def resizeEvent(self, resize_event: QResizeEvent):
        super().resizeEvent(resize_event)

        for sub_window in self.subWindowList():
            sub_window.lay_out_to_anchors()

        self.resized.emit(resize_event)
