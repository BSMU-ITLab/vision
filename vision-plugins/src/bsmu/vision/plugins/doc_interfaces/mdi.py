from __future__ import annotations

from typing import TYPE_CHECKING

# import PySide6QtAds as QtAds
from PySide6QtAds import CDockManager, CDockWidget, DockWidgetArea, TopDockWidgetArea, CenterDockWidgetArea, NoDockWidgetArea, RightDockWidgetArea
from PySide6.QtCore import Signal, QObject, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QMdiArea, QMessageBox, QMdiSubWindow, QWidget, QHBoxLayout, QLabel

from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Type, Protocol

    # from PySide6.QtWidgets import QMdiSubWindow

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
        self._main_window.setCentralWidget(self._mdi.main_dock_container)

    def _disable(self):
        central_widget = self._main_window.centralWidget()
        if central_widget == self._mdi.main_dock_container:
            self._main_window.takeCentralWidget()
        self._mdi.deleteLater()
        self._mdi = None


class Mdi(QObject):
    resized = Signal(QResizeEvent)
    subWindowActivated = Signal(QMdiSubWindow)

    def __init__(self):
        super().__init__()

        CDockManager.setConfigFlag(CDockManager.FocusHighlighting, True)
        self._main_dock_container = CDockManager()

        central_label = QLabel('Drop files here to open them')
        central_label.setAlignment(Qt.AlignCenter)
        font = central_label.font()
        font.setPointSize(10)
        central_label.setFont(font)
        central_dock_widget = CDockWidget('Central Widget', self._main_dock_container)
        central_dock_widget.setWidget(central_label)
        # central_dock_widget.setFeature(CDockWidget.NoTab, True)
        central_dock_widget.setFeature(CDockWidget.NoTab, False)
        # central_dock_area = self._main_dock_container.setCentralWidget(central_dock_widget)
        central_dock_widget.setFeature(CDockWidget.DockWidgetClosable, False)
        central_dock_widget.setFeature(CDockWidget.DockWidgetMovable, False)
        central_dock_widget.setFeature(CDockWidget.DockWidgetFloatable, False)
        central_dock_area = self._main_dock_container.addDockWidget(RightDockWidgetArea, central_dock_widget)

        self.central_label = central_label
        self.central_dock_widget = central_dock_widget
        self.central_dock_area = central_dock_area

        self._main_dock_container.focusedDockWidgetChanged.connect(self._on_focused_dock_widget_changed)

    @property
    def main_dock_container(self) -> CDockManager:
        return self._main_dock_container

    def add_dockable_widget(
            self, area: DockWidgetArea, title: str, widget: QWidget, focusable: bool = False) -> CDockWidget:
        dock_widget = CDockWidget(title, self._main_dock_container)
        dock_widget.setWidget(widget)
        dock_widget.setFeature(CDockWidget.DockWidgetFocusable, focusable)
        self._main_dock_container.addDockWidget(area, dock_widget)
        return dock_widget

    # def add_dock_widget(self, area: DockWidgetArea, dock_widget: CDockWidget, focusable: bool = False):
    def add_dock_widget(self, dock_widget: CDockWidget, focusable: bool = False):
        dock_widget.setFeature(CDockWidget.DockWidgetFocusable, focusable)
        # self._main_dock_container.addDockWidget(NoDockWidgetArea, dock_widget)
        self.central_dock_area.addDockWidget(dock_widget)
        return dock_widget

    def _on_focused_dock_widget_changed(self, old: CDockWidget, new: CDockWidget):
        print('Changed')

    # def _

    def active_sub_window_with_type(
            self, window_type: Type[Protocol], show_message: bool = True) -> QMdiSubWindow | None:
        active_sub_window = self.activeSubWindow()
        if not isinstance(active_sub_window, window_type):
            if show_message:
                QMessageBox.warning(
                    self,
                    'Wrong Active Window Type',
                    f'The active window must have {window_type.__name__} type.')
            return None

        return active_sub_window

    # def resizeEvent(self, resize_event: QResizeEvent):
    #     super().resizeEvent(resize_event)
    #
    #     for sub_window in self.subWindowList():
    #         sub_window.lay_out_to_anchors()
    #
    #     self.resized.emit(resize_event)
