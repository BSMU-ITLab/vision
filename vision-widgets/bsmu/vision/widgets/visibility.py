from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import QSize
from PySide2.QtGui import QIcon, QColor
from PySide2.QtWidgets import QWidget, QPushButton, QHBoxLayout, QSizePolicy, QFrame

from bsmu.vision.widgets.combo_slider import ComboSlider

DEFAULT_COLOR = QColor(204, 228, 247)


class VisibilityToggleButton(QPushButton):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setCheckable(True)
        self.setFlat(True)

        self._checked_color = DEFAULT_COLOR

        icons_path = Path(__file__).parent / 'images' / 'icons'
        self._checked_icon = QIcon(str(icons_path / 'eye.svg'))
        self._unchecked_icon = QIcon(str(icons_path / 'crossed-out-eye.svg'))

        self._update_icon()
        self._update_style()

        self.toggled.connect(self._on_button_toggled)

    @property
    def checked_color(self) -> QColor:
        return self._checked_color

    @checked_color.setter
    def checked_color(self, value: QColor):
        if self._checked_color != value:
            self._checked_color = value
            self._update_style()

    def _on_button_toggled(self, checked):
        self._update_icon()

    def _update_style(self):
        self.setStyleSheet(
            f'QPushButton {{ border: none; }}'
            f'QPushButton:checked {{ background-color: {self.checked_color.name()}; }}')

    def _update_icon(self):
        self.setIcon(self._checked_icon if self.isChecked() else self._unchecked_icon)


class VisibilityWidget(QFrame):
    def __init__(self, opacity: float = 50, embedded: bool = False, parent: QWidget = None):
        super().__init__(parent)

        self._embedded = embedded

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        self._toggle_button = VisibilityToggleButton()

        self._combo_slider = ComboSlider('Opacity', opacity, embedded=embedded)
        self._combo_slider.bar_color = DEFAULT_COLOR
        self._combo_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        if self._embedded:
            # Set minimum width, else widget will go beyond the cell width (e.g. a table cell)
            # when column width is small
            self.setMinimumWidth(1)
        else:
            self.setFrameStyle(QFrame.Box)
            self.setStyleSheet(
                f'VisibilityWidget {{ border: {self._combo_slider.frame_width}px solid '
                f'{self._combo_slider.frame_color.name()}; }}')
            self.setMaximumHeight(self._combo_slider.maximumHeight())

        self._combo_slider.setStyleSheet(
            f'ComboSlider {{ border: none; border-left: 1px solid {self._combo_slider.button_color.name()}; }}')

        h_layout.addWidget(self._toggle_button)
        h_layout.addWidget(self._combo_slider)

    @property
    def slider_bar_color(self) -> QColor:
        return self._combo_slider.bar_color

    @slider_bar_color.setter
    def slider_bar_color(self, value: QColor):
        self._combo_slider.bar_color = value

    @property
    def toggle_button_checked_color(self) -> QColor:
        return self._toggle_button.checked_color

    @toggle_button_checked_color.setter
    def toggle_button_checked_color(self, value: QColor):
        self._toggle_button.checked_color = value

    def resizeEvent(self, event: QResizeEvent):
        self._toggle_button.setIconSize(QSize(self.height(), self.height()))
