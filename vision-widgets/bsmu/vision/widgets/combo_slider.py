from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import Qt, Signal, QLocale
from PySide2.QtGui import QDoubleValidator, QPainter, QColor, QPaintEvent, QIcon
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QPushButton, QFrame, QApplication

from bsmu.vision.widgets.images import icons_rc  # noqa

if TYPE_CHECKING:
    from PySide2.QtGui import QMouseEvent, QKeyEvent, QWheelEvent


DEFAULT_FRAME_WIDTH = 1
DEFAULT_FRAME_COLOR = QColor(128, 128, 128)
DEFAULT_BAR_COLOR = QColor(240, 206, 164)
DEFAULT_BUTTON_COLOR = QColor('gainsboro')


class ComboSlider(QFrame):
    value_changed = Signal(float)

    def __init__(self, title: str = '', value: float = 0, min_value: float = 0, max_value: float = 100,
                 displayed_value_factor: float = 1, embedded: bool = False, parent: QWidget = None):
        super().__init__(parent)

        self._embedded = embedded

        self._slider_bar = SliderBar(title, value, min_value, max_value, displayed_value_factor)
        self._slider_bar.value_changed.connect(self.value_changed)

        self._buttons_layout = QVBoxLayout()
        self._buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._buttons_layout.setSpacing(0)

        self._button_color = DEFAULT_BUTTON_COLOR

        self._up_button = self._add_spin_button(':/icons/arrow-up.svg', self._on_up_button_clicked)
        self._down_button = self._add_spin_button(':/icons/arrow-down.svg', self._on_down_button_clicked)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        h_layout.addWidget(self._slider_bar)
        h_layout.addLayout(self._buttons_layout)

        if not self._embedded:
            self.setMaximumHeight(self._slider_bar.font_height + 9)
            self.setFrameStyle(QFrame.Box)

        self._frame_width = DEFAULT_FRAME_WIDTH
        self._frame_color = DEFAULT_FRAME_COLOR
        self._update_style()

    @property
    def frame_width(self) -> int:
        return self._frame_width

    @frame_width.setter
    def frame_width(self, value: int):
        if self._frame_width != value:
            self._frame_width = value
            self._update_style()

    @property
    def frame_color(self) -> QColor:
        return self._frame_color

    @frame_color.setter
    def frame_color(self, value: QColor):
        if self._frame_color != value:
            self._frame_color = value
            self._update_style()

    @property
    def bar_color(self) -> QColor:
        return self._slider_bar.color

    @bar_color.setter
    def bar_color(self, value: QColor):
        self._slider_bar.color = value

    @property
    def button_color(self) -> QColor:
        return self._button_color

    @button_color.setter
    def button_color(self, value: QColor):
        if self._button_color != value:
            self._button_color = value

            self._up_button.setPalette(self._button_color)
            self._down_button.setPalette(self._button_color)

    def _update_style(self):
        self.setStyleSheet(f'ComboSlider {{ border: {self.frame_width}px solid {self.frame_color.name()}; }}')

    def _add_spin_button(self, icon_path_str: str, on_button_clicked_callback) -> QPushButton:
        button = QPushButton(QIcon(icon_path_str), '')
        button.setAutoRepeat(True)
        button.setFocusPolicy(Qt.NoFocus)
        button.setMaximumWidth(20)
        # button.setMaximumHeight(15)
        button.setFlat(True)
        button.setAutoFillBackground(True)
        button.setPalette(self._button_color)

        button.clicked.connect(on_button_clicked_callback)
        self._buttons_layout.addWidget(button)
        return button

    def increase_value(self, factor: float = 1):
        self._slider_bar.increase_value(factor)

    def decrease_value(self, factor: float = 1):
        self._slider_bar.decrease_value(factor)

    def _on_up_button_clicked(self):
        self.increase_value(10 if QApplication.keyboardModifiers() & Qt.ControlModifier else 1)
        self._slider_bar.set_focus()

    def _on_down_button_clicked(self):
        self.decrease_value(10 if QApplication.keyboardModifiers() & Qt.ControlModifier else 1)
        self._slider_bar.set_focus()

    @property
    def title(self) -> str:
        return self._slider_bar.title

    @title.setter
    def title(self, value: str):
        self._slider_bar.title = value

    @property
    def value(self) -> float:
        return self._slider_bar.value

    @value.setter
    def value(self, value: float):
        self._slider_bar.value = value

    @property
    def min_value(self) -> float:
        return self._slider_bar.min_value

    @min_value.setter
    def min_value(self, value: float):
        self._slider_bar.min_value = value

    @property
    def max_value(self) -> float:
        return self._slider_bar.max_value

    @max_value.setter
    def max_value(self, value: float):
        self._slider_bar.max_value = value


class SliderValueLineEdit(QLineEdit):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setAlignment(Qt.AlignRight)
        self.setCursor(Qt.ArrowCursor)
        self.setFrame(False)
        self.setStyleSheet('QLineEdit { background-color: transparent; }')

    def mousePressEvent(self, event: QMouseEvent):
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent):
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent):
        event.ignore()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.selectAll()

        event.accept()


class SliderBar(QWidget):
    value_changed = Signal(float)

    def __init__(self, title: str = '', value: float = 0, min_value: float = 0, max_value: float = 100,
                 displayed_value_factor: float = 1, parent: QWidget = None):
        super().__init__(parent)

        self._value = value
        self._min_value = min_value
        self._max_value = max_value
        self._displayed_value_factor = displayed_value_factor

        self._title_label = QLabel(title)

        self._color = DEFAULT_BAR_COLOR

        self._locale = QLocale(QLocale.English)
        self._locale.setNumberOptions(self._locale.numberOptions() | QLocale.RejectGroupSeparator)

        validator = QDoubleValidator(self._min_value, self._max_value, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        validator.setLocale(self._locale)

        self._value_line_edit = SliderValueLineEdit()
        self._value_line_edit.setValidator(validator)
        max_label_width = self._value_line_edit.fontMetrics().width(self._value_to_str(self.max_value))
        self._value_line_edit.setFixedWidth(6 + max_label_width)
        self._value_line_edit.editingFinished.connect(self._on_value_line_edit_editing_finished)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(4, 0, 4, 0)
        # h_layout.setSpacing(0)

        h_layout.addWidget(self._title_label, 0, Qt.AlignLeft)
        h_layout.addWidget(self._value_line_edit, 0, Qt.AlignRight)

        self._update_value_line_edit()

    @property
    def title(self) -> str:
        return self._title_label.text()

    @title.setter
    def title(self, value: str):
        self._title_label.setText(value)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        value = max(min(value, self._max_value), self._min_value)
        if self._value != value:
            self._value = value

            self._update_value_line_edit()
            self.update()

            self.value_changed.emit(self._value)

    @property
    def min_value(self) -> float:
        return self._min_value

    @min_value.setter
    def min_value(self, value: float):
        if self._min_value != value:
            self._min_value = value

            if self.value < self._min_value:
                self.value = self._min_value
            else:
                self.update()

    @property
    def max_value(self) -> float:
        return self._max_value

    @max_value.setter
    def max_value(self, value: float):
        if self._max_value != value:
            self._max_value = value

            if self.value > self._max_value:
                self.value = self._max_value
            else:
                self.update()

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        if self._color != value:
            self._color = value
            self.update()

    @property
    def font_height(self):
        return self._title_label.fontMetrics().height()

    def set_focus(self):
        self._value_line_edit.setFocus()

    def increase_value(self, factor: float = 1):
        self.change_value_by_delta(1 * factor)

    def decrease_value(self, factor: float = 1):
        self.change_value_by_delta(-1 * factor)

    def change_value_by_delta(self, delta: float):
        self.value += delta
        self._value_line_edit.selectAll()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)
        painter.drawRect(0, 0,
                         round((self._value - self._min_value) / (self._max_value - self._min_value) * self.width()),
                         self.height())

    def mouseMoveEvent(self, event: QMouseEvent):
        self._update_value_by_x(event.x())

        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        self.set_focus()

        self._update_value_by_x(event.x())

        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self._value_line_edit.selectAll()

        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Up:
            self.increase_value()
        elif event.key() == Qt.Key_Down:
            self.decrease_value()
        elif event.key() == Qt.Key_PageUp:
            self.increase_value(10)
        elif event.key() == Qt.Key_PageDown:
            self.decrease_value(10)

    def wheelEvent(self, event: QWheelEvent):
        value_delta = event.angleDelta().y() / 120
        if event.modifiers() & Qt.ControlModifier:
            value_delta *= 10
        self.set_focus()
        self.increase_value(value_delta)

        event.accept()

    def _on_value_line_edit_editing_finished(self):
        self.value, ok = self._locale.toFloat(self._value_line_edit.text())

    def _update_value_by_x(self, x: int):
        self.value = (self.max_value - self.min_value) * x / self.width() + self.min_value

    def _update_value_line_edit(self):
        self._value_line_edit.setText(self._value_to_str(self.value))

    def _value_to_str(self, value: float) -> str:
        return self._locale.toString(float(value * self._displayed_value_factor), 'f', 2)
