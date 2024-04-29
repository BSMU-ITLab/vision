from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import ViewMenu
from bsmu.vision.widgets.mdi.windows.image.layered import VolumeSliceImageViewerSubWindow

if TYPE_CHECKING:
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class MdiVolumeSliceWalkerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin, mdi_plugin: MdiPlugin):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._mdi_volume_slice_walker: MdiVolumeSliceWalker | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._mdi_volume_slice_walker = MdiVolumeSliceWalker(self._mdi)

        self._main_window.add_menu_action(
            ViewMenu, 'Next Slice', self._mdi_volume_slice_walker.show_next_slice, Qt.CTRL + Qt.Key_Up)
        self._main_window.add_menu_action(
            ViewMenu, 'Previous Slice', self._mdi_volume_slice_walker.show_prev_slice, Qt.CTRL + Qt.Key_Down)

    def _disable(self):
        self._mdi_volume_slice_walker = None

        raise NotImplementedError


class MdiVolumeSliceWalker(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self.mdi = mdi

    def show_next_slice(self):
        for volume_slice_image_viewer in self._volume_slice_image_viewers():
            volume_slice_image_viewer.show_next_slice()

    def show_prev_slice(self):
        for volume_slice_image_viewer in self._volume_slice_image_viewers():
            volume_slice_image_viewer.show_prev_slice()

    def _volume_slice_image_viewers(self):
        active_sub_window = self.mdi.activeSubWindow()
        if isinstance(active_sub_window, VolumeSliceImageViewerSubWindow):
            return [active_sub_window.viewer]
        else:
            return []
