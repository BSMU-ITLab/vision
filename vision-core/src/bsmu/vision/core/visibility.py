from PySide6.QtCore import QObject


class Visibility(QObject):
    def __init__(self, visible: bool = True, opacity: float = 1):
        super().__init__()

        self._visible = visible
        self._opacity = opacity

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self._visible = value

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        self._opacity = value
