from __future__ import annotations

import typing
from functools import partial
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt, QModelIndex
from PySide2.QtWidgets import QTableView, QDockWidget

from bsmu.vision.core.models.table import RecordTableModel, TableColumn
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.base import ImageLayerView
from bsmu.vision.widgets.visibility_v2 import Visibility, VisibilityDelegate

if TYPE_CHECKING:
    from typing import List, Tuple, Any

    from PySide2.QtCore import QAbstractItemModel
    from PySide2.QtWidgets import QWidget, QMdiSubWindow

    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


class LayersTableViewPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin, mdi_plugin: MdiPlugin):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._layers_table_view: LayersTableView | None = None
        self._layers_table_view_dock_widget: QDockWidget | None = None

        self._layers_table_model: LayersTableModel | None = None
        self._visibility_delegate: VisibilityDelegate | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._layers_table_view = LayersTableView()
        self._layers_table_view_dock_widget = QDockWidget('Layers', self._main_window)
        self._layers_table_view_dock_widget.setWidget(self._layers_table_view)

        self._layers_table_model = LayersTableModel()
        self._layers_table_view.setModel(self._layers_table_model)

        self._visibility_delegate = VisibilityDelegate()
        visibility_column_number = self._layers_table_model.column_number(VisibilityTableColumn)
        self._layers_table_view.setItemDelegateForColumn(visibility_column_number, self._visibility_delegate)

        self._mdi.subWindowActivated.connect(self._on_mdi_sub_window_activated)

        self._main_window.addDockWidget(Qt.LeftDockWidgetArea, self._layers_table_view_dock_widget, Qt.Vertical)

    def _disable(self):
        self._main_window.removeDockWidget(self._layers_table_view_dock_widget)

        self._mdi.subWindowActivated.disconnect(self._on_mdi_sub_window_activated)

        self._layers_table_view_dock_widget = None
        self._layers_table_view = None

        self._mdi = None
        self._main_window = None

        raise NotImplementedError

    def _on_mdi_sub_window_activated(self, sub_window: QMdiSubWindow):
        if isinstance(sub_window, LayeredImageViewerSubWindow):
            self._layers_table_model.record_storage = sub_window.viewer
        else:
            self._layers_table_model.record_storage = None


class NameTableColumn(TableColumn):
    TITLE = 'Name'


class VisibilityTableColumn(TableColumn):
    TITLE = 'Visibility'


class LayersTableModel(RecordTableModel):
    def __init__(self, record_storage: LayeredImageViewer = None, parent: QObject = None):
        # Store handlers to disconnect signals.
        # When https://bugreports.qt.io/projects/PYSIDE/issues/PYSIDE-1334?filter=allissues will be fixed
        # we will be able to store connection objects instead.
        self.visibility_changed_handler_by_record = {}
        self.opacity_changed_handler_by_record = {}

        super().__init__(record_storage, ImageLayerView, (NameTableColumn, VisibilityTableColumn), parent)

    @property
    def storage_records(self) -> List[ImageLayerView]:
        return self.record_storage.layer_views

    def _record_data(self, record: ImageLayerView, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(NameTableColumn):
                return record.name
            elif index.column() == self.column_number(VisibilityTableColumn):
                return Visibility(record.visible, record.opacity)

    def _set_record_data(self, record: ImageLayerView, index: QModelIndex, value: Any) -> bool | Tuple[bool, bool]:
        if index.column() == self.column_number(NameTableColumn):
            record.name = value
        elif index.column() == self.column_number(VisibilityTableColumn):
            record.visible = value.visible
            record.opacity = value.opacity
        else:
            return False
        return True

    def _on_record_storage_changing(self):
        self.record_storage.layer_view_adding.disconnect(self._on_storage_record_adding)
        self.record_storage.layer_view_added.disconnect(self._on_storage_record_added)

    def _on_record_storage_changed(self):
        self.record_storage.layer_view_adding.connect(self._on_storage_record_adding)
        self.record_storage.layer_view_added.connect(self._on_storage_record_added)

    def _on_record_added(self, record: ImageLayerView, row: int):
        visibility_changed_handler = partial(self._on_visibility_changed, record, row)
        self.visibility_changed_handler_by_record[record] = visibility_changed_handler
        record.visibility_changed.connect(visibility_changed_handler)

        opacity_changed_handler = partial(self._on_opacity_changed, record, row)
        self.opacity_changed_handler_by_record[record] = opacity_changed_handler
        record.opacity_changed.connect(opacity_changed_handler)

    def _on_record_removed(self, record: ImageLayerView, row: int):
        visibility_changed_handler = self.visibility_changed_handler_by_record.pop(record)
        record.visibility_changed.disconnect(visibility_changed_handler)

        opacity_changed_handler = self.opacity_changed_handler_by_record.pop(record)
        record.opacity_changed.disconnect(opacity_changed_handler)

    def _on_visibility_changed(self, record: ImageLayerView, row: int, visible: bool):
        visibility_model_index = self.index(row, self.column_number(VisibilityTableColumn))
        self.dataChanged.emit(visibility_model_index, visibility_model_index)

    def _on_opacity_changed(self, record: ImageLayerView, row: int, opacity: float):
        visibility_model_index = self.index(row, self.column_number(VisibilityTableColumn))
        self.dataChanged.emit(visibility_model_index, visibility_model_index)


class LayersTableView(QTableView):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

    def setModel(self, model: QAbstractItemModel):
        if self.model() is not None:
            self.model().modelReset.disconnect(self._open_persistent_editors)
            self.model().modelAboutToBeReset.disconnect(self._close_persistent_editors)

            self._close_persistent_editors()

        super().setModel(model)

        if self.model() is not None:
            self._open_persistent_editors()

            self.model().modelAboutToBeReset.connect(self._close_persistent_editors)
            self.model().modelReset.connect(self._open_persistent_editors)

    def _open_persistent_editors(self):
        self._open_persistent_editors_for_rows(range(self.model().rowCount()))

    def _close_persistent_editors(self):
        self._close_persistent_editors_for_rows(range(self.model().rowCount()))

    def rowsInserted(self, parent: QModelIndex, start: int, end: int):
        self._open_persistent_editors_for_rows(range(start, end + 1))

        super().rowsInserted(parent, start, end)

    def rowsAboutToBeRemoved(self, parent: QModelIndex, start: int, end: int):
        self._close_persistent_editors_for_rows(range(start, end + 1))

        super().rowsAboutToBeRemoved(parent, start, end)

    def _open_persistent_editors_for_rows(self, rows: typing.Iterable):
        visibility_column_number = self.model().column_number(VisibilityTableColumn)
        for row in rows:
            self.openPersistentEditor(self.model().index(row, visibility_column_number))

    def _close_persistent_editors_for_rows(self, rows: typing.Iterable):
        visibility_column_number = self.model().column_number(VisibilityTableColumn)
        for row in rows:
            self.closePersistentEditor(self.model().index(row, visibility_column_number))
