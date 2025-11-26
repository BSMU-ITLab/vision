from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtWidgets import QWidget, QApplication, QGridLayout

from bsmu.vision.core.data import Data

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QCloseEvent

DataT = TypeVar('DataT', bound=Data)


class DataViewer(QWidget, Generic[DataT]):
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

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError(f'QApplication must be created before {self.__class__.__name__}.')
        app.focusChanged.connect(self._on_app_focus_changed)

    def set_content_widget(self, widget: QWidget | None):
        if self._content_widget is not None:
            self._layout.removeWidget(self._content_widget)

        self._content_widget = widget

        if self._content_widget is not None:
            self._content_widget.setObjectName(self.CONTENT_WIDGET_OBJECT_NAME)
            self._layout.addWidget(self._content_widget)

    def _on_app_focus_changed(self, old: QWidget, now: QWidget):
        """Highlight this DataViewer if the newly focused widget is our descendant."""
        has_focus_within = isinstance(now, QWidget) and self.isAncestorOf(now)
        self.setStyleSheet(self._focus_style if has_focus_within else self._default_style)

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
        if self._data != value:
            self._on_data_changing()
            self._data = value
            self._on_data_changed()

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

    def _on_data_changing(self):
        pass

    def _on_data_changed(self):
        pass
