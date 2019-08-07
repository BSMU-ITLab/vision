from PySide2.QtWidgets import QMainWindow

from bsmu.vision.plugin import Plugin


class MainWindowPlugin(Plugin):
    def __init__(self):
        super().__init__()

        self.main_window = MainWindow()

    def _enable(self):
        self.main_window.show()

    def disable(self):
        self.main_window.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(800, 600)
        self.move(300, 300)
        self.setWindowTitle('Vision')
