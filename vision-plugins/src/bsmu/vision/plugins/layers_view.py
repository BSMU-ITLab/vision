from __future__ import annotations

from abc import abstractmethod
from functools import partial
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt, QAbstractTableModel, QModelIndex
from PySide2.QtWidgets import QTableView, QDockWidget, QAbstractItemView

from bsmu.vision.core.abc import QABCMeta
from bsmu.vision.core.image.layered import ImageLayer
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

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._layers_table_view = LayersTableView()
        self._layers_table_view_dock_widget = QDockWidget('Layers View', self._main_window)
        self._layers_table_view_dock_widget.setWidget(self._layers_table_view)

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
        if not isinstance(sub_window, LayeredImageViewerSubWindow):
            return

        layers_table_model = LayersTableModel(sub_window.viewer)
        self._layers_table_view.setModel(layers_table_model)
        visibility_column_number = layers_table_model.column_number(VisibilityTableColumn)
        self._layers_table_view.setItemDelegateForColumn(visibility_column_number, VisibilityDelegate())


class TableColumn:
    TITLE = ''


class NameTableColumn(TableColumn):
    TITLE = 'Name'


class VisibilityTableColumn(TableColumn):
    TITLE = 'Visibility'


class DataTableModel(QAbstractTableModel, metaclass=QABCMeta):
    def __init__(
            self,
            data: QObject,
            record_type: Type[QObject],
            columns: List[Type[TableColumn]] | Tuple[Type[TableColumn]] = (),
            parent: QObject = None,
    ):
        super().__init__(parent)

        self._data = data
        self._record_type = record_type
        self._columns = columns
        self._number_by_column = {column: number for number, column in enumerate(self._columns)}

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._number_by_column[column]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.data_records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

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

        if index.row() >= len(self.data_records) or index.row() < 0:
            return

        record = self.data_records[index.row()]
        return self._record_data(record, index, role)

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        """
        Need this method only to insert some rows into our |self._data| using this model.
        E.g. some view can use this method to insert rows.
        At other times it's more convenient to use |self._data.add_record| method
        """
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        for i in range(count):
            self.data_records.insert(row, self._record_type())

        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        del self.data_records[row: row + count]

        self.endRemoveRows()
        return True

    def _on_data_record_adding(self):
        # Append one row
        row_count = self.rowCount()
        self.beginInsertRows(QModelIndex(), row_count, row_count)

    def _on_data_record_added(self):
        self.endInsertRows()
        row = self.rowCount() - 1
        self._on_record_added(self.data_records[row], row)

    @abstractmethod
    def _record_data(self, record, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        pass

    @property
    @abstractmethod
    def data_records(self) -> List[QObject]:
        pass

    @abstractmethod
    def _on_record_added(self, record: QObject, row: int):
        pass


class LayersTableModel(DataTableModel):
    def __init__(self, data: LayeredImageViewer, parent: QObject = None):
        super().__init__(data, ImageLayerView, (NameTableColumn, VisibilityTableColumn), parent)

        self._data.layer_view_adding.connect(self._on_data_record_adding)
        self._data.layer_view_added.connect(self._on_data_record_added)

    def _record_data(self, record: ImageLayer, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(NameTableColumn):
                return record.name
            elif index.column() == self.column_number(VisibilityTableColumn):
                return Visibility(record.visible, record.opacity)

    @property
    def data_records(self) -> List[QObject]:
        return self._data.layer_views

    def _on_record_added(self, record: ImageLayerView, row: int):
        print('_on_record_added', record.name)
        record.visibility_changed.connect(partial(self._on_row_visibility_changed, row))

    def _on_row_visibility_changed(self, row, visible: bool):
        visibility_model_index = self.index(row, self.column_number(VisibilityTableColumn))
        self.dataChanged.emit(visibility_model_index, visibility_model_index)


class LayersTableView(QTableView):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setEditTriggers(
            QAbstractItemView.CurrentChanged | QAbstractItemView.SelectedClicked | QAbstractItemView.DoubleClicked)
