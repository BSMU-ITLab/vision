from __future__ import annotations

from PySide2.QtWidgets import QMdiArea

from bsmu.vision.app.plugin import Plugin


class MdiPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window

        self.mdi = Mdi()

    def _enable(self):
        self.main_window.setCentralWidget(self.mdi)

    def _disable(self):
        self.main_window.takeCentralWidget()


class Mdi(QMdiArea):
    def __init__(self):
        super().__init__()
