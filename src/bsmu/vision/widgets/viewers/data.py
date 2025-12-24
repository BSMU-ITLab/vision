from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QApplication, QGridLayout

from bsmu.vision.core.data import Data

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QCloseEvent

DataT = TypeVar('DataT', bound=Data)


class DataViewer(QWidget, Generic[DataT]):
    data_about_to_change = Signal(Data, Data)
    data_changed = Signal(Data)

    CONTENT_WIDGET_OBJECT_NAME = 'content_widget'

    def __init__(self, data: DataT | None = None, parent: QWidget | None = None):
        super().__init__(parent)

        self._data: DataT | None = None
        self.data = data

        # Cursor shape should only be changed by the current cursor owner
        self._cursor_owner: QObject | None = None

        self._content_widget: QWidget | None = None

        self._layout = QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        highlight_color = self.palette().color(self.palette().ColorRole.Highlight).name()
        self._default_style = f'#{self.CONTENT_WIDGET_OBJECT_NAME}'
        self._focus_style = f'#{self.CONTENT_WIDGET_OBJECT_NAME} {{ border: 1px solid {highlight_color}; }}'
        self._is_focus_style_used: bool = False

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError(f'QApplication must be created before {self.__class__.__name__}.')
        app.focusChanged.connect(self._on_app_focus_changed)

    def set_content_widget(self, widget: QWidget | None):
        if self._content_widget is not None:
            self._layout.removeWidget(self._content_widget)

        self._content_widget = widget
        self._is_focus_style_used = False

        if self._content_widget is not None:
            self._content_widget.setObjectName(self.CONTENT_WIDGET_OBJECT_NAME)
            self._layout.addWidget(self._content_widget)

    def _on_app_focus_changed(self, _old: QWidget, now: QWidget):
        """Highlight content widget when the newly focused widget is our descendant."""
        if self._content_widget is None:
            return

        has_focus_within = isinstance(now, QWidget) and self.isAncestorOf(now)
        if has_focus_within:
            if not self._is_focus_style_used:
                self._content_widget.setStyleSheet(self._focus_style)
                self._is_focus_style_used = True
        else:
            if self._is_focus_style_used:
                self._content_widget.setStyleSheet(self._default_style)
                self._is_focus_style_used = False

    def closeEvent(self, event: QCloseEvent):
        app = QApplication.instance()
        try:
            app.focusChanged.disconnect(self._on_app_focus_changed)
        except Exception:
            pass
        super().closeEvent(event)

    @property
    def data(self) -> DataT | None:
        return self._data

    @data.setter
    def data(self, value: DataT | None):
        if self._data == value:
            return

        self.data_about_to_change.emit(self._data, value)
        self._data_about_to_change(value)

        self._data = value

        self._data_changed()
        self.data_changed.emit(self._data)

    @property
    def data_path_name(self):
        return '' if self.data is None else self.data.path_name

    @property
    def cursor_owner(self) -> QObject | None:
        return self._cursor_owner

    @cursor_owner.setter
    def cursor_owner(self, value: QObject | None):
        if value is not None and self._cursor_owner is not None:
            raise RuntimeError(
                f'Cursor ownership conflict: current owner is "{type(self._cursor_owner).__name__}", '
                f'attempted reassignment to "{type(value).__name__}"'
            )

        self._cursor_owner = value
        self._on_cursor_owner_changed()

    def _on_cursor_owner_changed(self):
        pass

    def _data_about_to_change(self, new_data: DataT | None):
        pass

    def _data_changed(self):
        pass
