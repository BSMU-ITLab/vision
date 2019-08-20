from __future__ import annotations

from PySide2.QtWidgets import QMainWindow

from bsmu.vision.app.plugin import Plugin


class MainWindowPlugin(Plugin):
    # setup_info = SetupInfo(name='bsmu-vision-main-window',
    #                        version=Version(0, 0, 1),
    #                        py_modules=('main',))

    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = MainWindow()

    def _enable(self):
        self.main_window.show()

    def _disable(self):
        self.main_window.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(800, 600)
        self.move(300, 300)
        self.setWindowTitle('Vision')