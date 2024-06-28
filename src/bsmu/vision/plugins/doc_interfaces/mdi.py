from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QMdiArea, QMdiSubWindow, QMessageBox

from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Protocol

    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class MdiPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
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
    sub_window_adding = Signal(QMdiSubWindow)
    sub_window_added = Signal(QMdiSubWindow)

    resized = Signal(QResizeEvent)

    def __init__(self):
        super().__init__()

    def add_sub_window(self, sub_window: QMdiSubWindow) -> QMdiSubWindow:
        self.sub_window_adding.emit(sub_window)
        super().addSubWindow(sub_window)
        self.sub_window_added.emit(sub_window)
        return sub_window

    def active_sub_window_with_type(
            self, window_type: type[Protocol], show_message: bool = True) -> QMdiSubWindow | None:
        active_sub_window = self.activeSubWindow()
        if not isinstance(active_sub_window, window_type):
            if show_message:
                QMessageBox.warning(
                    self,
                    'Wrong Active Window Type',
                    f'The active window must have {window_type.__name__} type.')
            return None

        return active_sub_window

    def resizeEvent(self, resize_event: QResizeEvent):
        super().resizeEvent(resize_event)

        for sub_window in self.subWindowList():
            sub_window.lay_out_to_anchors()

        self.resized.emit(resize_event)
