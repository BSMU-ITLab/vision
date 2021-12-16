from __future__ import annotations

from abc import abstractmethod
from functools import partial
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt, QAbstractTableModel, QModelIndex
from PySide2.QtWidgets import QTableView, QDockWidget, QAbstractItemView

from bsmu.vision.core.abc import QABCMeta
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.base import ImageLayerView
from bsmu.vision.widgets.visibility_new import Visibility, VisibilityDelegate

if TYPE_CHECKING:
    from typing import Type, List, Tuple, Any

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
        self._layers_table_view_dock_widget = QDockWidget('Layers View', self._main_window)
        self._layers_table_view_dock_widget.setWidget(self._layers_table_view)

        self._layers_table_model = LayersTableModel()
        self._layers_table_view.setModel(self._layers_table_model)

        self._visibility_delegate = VisibilityDelegate()
        visibility_column_number = self._layers_table_model.column_number(VisibilityTableColumn)
        self._layers_table_view.setItemDelegateForColumn(visibility_column_number, self._visibility_delegate)

        self._mdi.subWindowActivated.connect(self._on_mdi_sub_window_activated)

        self._main_window.addDockWidget(Qt.RightDockWidgetArea, self._layers_table_view_dock_widget)

    def _disable(self):
        self._main_window.removeDockWidget(self._layers_table_view_dock_widget)

        self._mdi.subWindowActivated.disconnect(self._on_mdi_sub_window_activated)

        self._layers_table_view_dock_widget = None
        self._layers_table_view = None

        self._mdi = None
        self._main_window = None

        raise NotImplementedError

    def _on_mdi_sub_window_activated(self, sub_window: QMdiSubWindow):
        print('_on_mdi_sub_window_activated', sub_window)

        if isinstance(sub_window, LayeredImageViewerSubWindow):
            self._layers_table_model.record_storage = sub_window.viewer
        else:
            self._layers_table_model.record_storage = None


class TableColumn:
    TITLE = ''


class NameTableColumn(TableColumn):
    TITLE = 'Name'


class VisibilityTableColumn(TableColumn):
    TITLE = 'Visibility'


class RecordTableModel(QAbstractTableModel, metaclass=QABCMeta):
    def __init__(
            self,
            record_storage: QObject,
            record_type: Type[QObject],
            columns: List[Type[TableColumn]] | Tuple[Type[TableColumn]] = (),
            parent: QObject = None,
    ):
        super().__init__(parent)

        self._record_storage = None
        self.record_storage = record_storage

        self._record_type = record_type
        self._columns = columns
        self._number_by_column = {column: number for number, column in enumerate(self._columns)}

    def clean_up(self):
        self.record_storage = None

    @property
    def record_storage(self) -> QObject:
        return self._record_storage

    @record_storage.setter
    def record_storage(self, value: QObject):
        if self._record_storage == value:
            return

        self.beginResetModel()

        if self._record_storage is not None:
            self._on_record_storage_changing()
            for i, record in enumerate(self.storage_records):
                self._on_record_removed(record, i)

        self._record_storage = value

        if self._record_storage is not None:
            for i, record in enumerate(self.storage_records):
                self._on_record_added(record, i)
            self._on_record_storage_changed()

        self.endResetModel()

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._number_by_column[column]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or self.record_storage is None else len(self.storage_records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or self.record_storage is None else len(self._columns)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled

        flags = super().flags(index)
        flags |= Qt.ItemIsEditable
        return flags

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return

        if orientation == Qt.Horizontal:
            return self._columns[section].TITLE
        elif orientation == Qt.Vertical:
            return section + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return

        if index.row() >= len(self.storage_records) or index.row() < 0:
            return

        record = self.storage_records[index.row()]
        return self._record_data(record, index, role)

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        successfully_set = False
        if index.isValid() and role == Qt.EditRole:
            row = index.row()
            record = self.storage_records[row]
            successfully_set = self._set_record_data(record, index, value)
            if successfully_set:
                self.dataChanged.emit(index, index)
        return successfully_set

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        """
        Need this method only to insert some rows into our |self._data| using this model.
        E.g. some view can use this method to insert rows.
        At other times it's more convenient to use |self._data.add_record| method
        """
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        for i in range(count):
            self.storage_records.insert(row, self._record_type())

        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        del self.storage_records[row: row + count]

        self.endRemoveRows()
        return True

    def _on_storage_record_adding(self):
        # Append one row
        row_count = self.rowCount()
        self.beginInsertRows(QModelIndex(), row_count, row_count)

    def _on_storage_record_added(self):
        self.endInsertRows()
        row = self.rowCount() - 1
        self._on_record_added(self.storage_records[row], row)

    @abstractmethod
    def _record_data(self, record: QObject, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        pass

    @abstractmethod
    def _set_record_data(self, record: QObject, index: QModelIndex, value: Any) -> bool:
        pass

    @abstractmethod
    def _on_record_storage_changing(self):
        pass

    @abstractmethod
    def _on_record_storage_changed(self):
        pass

    @property
    @abstractmethod
    def storage_records(self) -> List[QObject]:
        pass

    @abstractmethod
    def _on_record_added(self, record: QObject, row: int):
        pass

    @abstractmethod
    def _on_record_removed(self, record: QObject, row: int):
        pass


class LayersTableModel(RecordTableModel):
    def __init__(self, record_storage: LayeredImageViewer = None, parent: QObject = None):
        self.visibility_changed_handler_by_record = {}

        super().__init__(record_storage, ImageLayerView, (NameTableColumn, VisibilityTableColumn), parent)

        self.columnsInserted.connect(self._on_columns_inserted)
        self.dataChanged.connect(self._on_data_changed)
        self.layoutChanged.connect(self._on_layout_changed)
        self.modelReset.connect(self._on_model_reset)

    def _record_data(self, record: ImageLayerView, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(NameTableColumn):
                return record.name
            elif index.column() == self.column_number(VisibilityTableColumn):
                return Visibility(record.visible, record.opacity)

    def _set_record_data(self, record: ImageLayerView, index: QModelIndex, value: Any) -> bool:
        if index.column() == self.column_number(NameTableColumn):
            record.name = value
        elif index.column() == self.column_number(VisibilityTableColumn):
            record.visible = value.visible
            record.opacity = value.opacity
        else:
            return False
        return True

    @property
    def storage_records(self) -> List[QObject]:
        return self.record_storage.layer_views

    @abstractmethod
    def _on_record_storage_changing(self):
        self.record_storage.layer_view_adding.disconnect(self._on_storage_record_adding)
        self.record_storage.layer_view_added.disconnect(self._on_storage_record_added)

    @abstractmethod
    def _on_record_storage_changed(self):
        self.record_storage.layer_view_adding.connect(self._on_storage_record_adding)
        self.record_storage.layer_view_added.connect(self._on_storage_record_added)

    def _on_record_added(self, record: ImageLayerView, row: int):
        visibility_changed_handler = partial(self._on_visibility_changed, record, row)
        self.visibility_changed_handler_by_record[record] = visibility_changed_handler
        record.visibility_changed.connect(visibility_changed_handler)

    def _on_record_removed(self, record: ImageLayerView, row: int):
        visibility_changed_handler = self.visibility_changed_handler_by_record.pop(record)
        record.visibility_changed.disconnect(visibility_changed_handler)

    def _on_visibility_changed(self, record: ImageLayerView, row: int, visible: bool):
        visibility_model_index = self.index(row, self.column_number(VisibilityTableColumn))
        self.setData(visibility_model_index, Visibility(record.visible, record.opacity))

    def _on_columns_inserted(self, parent: QModelIndex, first: int, last: int):
        print('_on_columns_inserted', first, last)

    def _on_data_changed(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles):
        print('_on_data_changed', topLeft.row(), topLeft.column(), '      ', bottomRight.row(), bottomRight.column())

    def _on_layout_changed(self, parents, hint):
        print('_on_layout_changed')

    def _on_model_reset(self):
        print('_on_model_reset')


class LayersTableView(QTableView):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setEditTriggers(
            QAbstractItemView.CurrentChanged | QAbstractItemView.SelectedClicked | QAbstractItemView.DoubleClicked)
