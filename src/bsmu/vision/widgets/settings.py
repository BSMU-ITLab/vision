from PySide6.QtWidgets import QWidget

from bsmu.vision.core.settings import Settings


class SettingsWidget(QWidget):
    def __init__(self, settings: Settings, parent: QWidget = None):
        super().__init__(parent)

        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings
