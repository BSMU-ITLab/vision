from __future__ import annotations

import os

from PySide2.QtCore import QObject, Qt

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow


class MdiVolumeSliceWalkerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi

        self.mdi_volume_slice_walker = MdiVolumeSliceWalker(mdi)

    def _enable(self):
        self.main_window.add_menu_action(MenuType.VIEW, 'Next Slice',
                                         self.mdi_volume_slice_walker.show_next_slice,
                                         Qt.CTRL + Qt.Key_Up)
        self.main_window.add_menu_action(MenuType.VIEW, 'Previous Slice',
                                         self.mdi_volume_slice_walker.show_previous_slice,
                                         Qt.CTRL + Qt.Key_Down)

    def _disable(self):
        raise NotImplementedError


class MdiVolumeSliceWalker(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self.mdi = mdi

    def show_next_slice(self):
        walker = self._volume_slice_walker()

        if walker is not None:
            walker.show_next_slice()



        ...

    def show_previous_slice(self):
        ...

    def _volume_slice_walker(self):
        active_sub_window = self.mdi.activeSubWindow()





