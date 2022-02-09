from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QSizePolicy, QFrame, QButtonGroup

from bsmu.vision.widgets.styles.base import VisionStyle


class GenderButton(QPushButton):
    def __init__(self, text: str, add_left_border: bool = False, parent: QWidget = None):
        super().__init__(text, parent)

        self.setCheckable(True)
        self.setFlat(True)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        left_border_style_str = ''
        if add_left_border:
            left_border_style_str = f'GenderButton {{ border-left: {VisionStyle.FRAME_WIDTH}px solid '\
                                    f'{VisionStyle.INTERNAL_FRAME_COLOR.name()}; }}'
        self.setStyleSheet(
            f'GenderButton {{ border: none; }}'
            f'GenderButton:checked {{ background-color: {VisionStyle.CHECKED_COLOR.name()}; }}'
            f'{left_border_style_str}'
        )


class GenderWidget(QFrame):
    gender_changed = Signal(bool)

    def __init__(self, embedded: bool = False, parent: QWidget = None):
        super().__init__(parent)

        self._embedded = embedded

        self._frame_width = VisionStyle.FRAME_WIDTH
        self._frame_color = VisionStyle.EXTERNAL_FRAME_COLOR

        self.man_button = GenderButton('M')
        self.man_button.setChecked(True)
        self.man_button.toggled.connect(self.gender_changed)
        self.woman_button = GenderButton('W', add_left_border=True)
        gender_button_group = QButtonGroup(self)
        gender_button_group.addButton(self.man_button)
        gender_button_group.addButton(self.woman_button)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        h_layout.addWidget(self.man_button)
        h_layout.addWidget(self.woman_button)

        if not self._embedded:
            self.setFrameStyle(QFrame.Box)
            self.setStyleSheet(
                f'GenderWidget {{ border: {self.frame_width}px solid '
                f'{self.frame_color.name()}; }}')

    @property
    def frame_width(self) -> int:
        return self._frame_width

    @property
    def frame_color(self) -> QColor:
        return self._frame_color

    @property
    def man(self) -> bool:
        return self.man_button.isChecked()

    @man.setter
    def man(self, value: bool):
        self.man_button.setChecked(True) if value else self.woman_button.setChecked(True)
