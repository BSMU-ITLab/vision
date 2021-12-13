from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt, QAbstractTableModel, QModelIndex, Signal
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


class TableModelDataWrapper(QObject, metaclass=QABCMeta):
    record_adding = Signal(QObject)
    record_added = Signal(QObject)

    def __init__(self, data: QObject, record_type: Type[QObject]):
        super().__init__()

        self._data = data
        self._record_type = record_type

    @property
    @abstractmethod
    def records(self) -> List:
        pass

    @property
    def record_type(self) -> Type[QObject]:
        return self._record_type

    def add_record(self, record: QObject):
        self.record_adding.emit(record)
        self.records.append(record)
        self.record_added.emit(record)


class DataTableModel(QAbstractTableModel, metaclass=QABCMeta):
    def __init__(
            self,
            data: TableModelDataWrapper,
            columns: List[Type[TableColumn]] | Tuple[Type[TableColumn]] = (),
            parent: QObject = None
    ):
        super().__init__(parent)

        self._data = data
        self._data.record_adding.connect(self._on_data_record_adding)
        self._data.record_added.connect(self.endInsertRows)

        self._columns = columns
        self._number_by_column = {column: number for number, column in enumerate(self._columns)}

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._number_by_column[column]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data.records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

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

        if index.row() >= len(self._data.records) or index.row() < 0:
            return

        record = self._data.records[index.row()]
        return self._record_data(record, index, role)

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        """
        Need this method only to insert some rows into our |self._data| using this model.
        E.g. some view can use this method to insert rows.
        At other times it's more convenient to use |self._data.add_record| method
        """
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        for i in range(count):
            self._data.records.insert(row, self._data.record_type())

        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        del self._data.records[row: row + count]

        self.endRemoveRows()
        return True

    def _on_data_record_adding(self):
        # Append one row
        row_count = self.rowCount()
        self.beginInsertRows(QModelIndex(), row_count, row_count)

    @abstractmethod
    def _record_data(self, record, index: QModelIndex, role: int = Qt.DisplayRole):
        pass


class LayersTableModelDataWrapper(TableModelDataWrapper):
    def __init__(self, data: LayeredImageViewer):
        super().__init__(data, ImageLayerView)

        self._data.layer_view_adding.connect(self.record_adding)
        self._data.layer_view_added.connect(self.record_added)

    @property
    def records(self) -> List[ImageLayerView]:
        return self._data.layer_views


class LayersTableModel(DataTableModel):
    def __init__(self, data: LayeredImageViewer, parent: QObject = None):
        super().__init__(LayersTableModelDataWrapper(data), (NameTableColumn, VisibilityTableColumn), parent)

    def _record_data(self, record: ImageLayer, index: QModelIndex, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(NameTableColumn):
                return record.name
            elif index.column() == self.column_number(VisibilityTableColumn):
                #% return str(record.opacity)
                return Visibility(record.visible, record.opacity)


class LayersTableView(QTableView):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setEditTriggers(
            QAbstractItemView.CurrentChanged | QAbstractItemView.SelectedClicked | QAbstractItemView.DoubleClicked)
