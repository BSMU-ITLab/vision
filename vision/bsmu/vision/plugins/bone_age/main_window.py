from __future__ import annotations

from enum import IntEnum
from typing import Optional

from PySide2.QtWidgets import QMainWindow, QMenuBar, QMenu
from sortedcontainers import SortedDict

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class BoneAgeMainWindowPlugin(MainWindowPlugin):
    # setup_info = SetupInfo(name='bsmu-vision-main-window',
    #                        version=Version(0, 0, 1),
    #                        py_modules=('main',))

    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = BoneAgeMainWindow()

    def _enable(self):
        self.main_window.show()

    def _disable(self):
        self.main_window.hide()


class BoneAgeMainWindow(MainWindow):
    def __init__(self, title: str = ''):
        super().__init__()

        self.resize(800, 600)
        self.move(300, 300)
        self.setWindowTitle(title)
