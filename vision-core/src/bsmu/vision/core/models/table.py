from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt, QAbstractTableModel, QModelIndex

from bsmu.vision.core.abc import QABCMeta

if TYPE_CHECKING:
    from typing import Type, List, Tuple, Any


class TableColumn:
    TITLE = ''


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
            set_record_data_result = self._set_record_data(record, index, value)
            if isinstance(set_record_data_result, tuple):
                successfully_set, emit_data_changed_signal = set_record_data_result
            else:
                successfully_set = set_record_data_result
                # dataChanged signal may be emitted in the model after a record property changed signal.
                # In such cases we do not emit dataChanged signal here
                emit_data_changed_signal = False
            if successfully_set and emit_data_changed_signal:
                self.dataChanged.emit(index, index)
        return successfully_set

    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        """
        Need this method only to insert some records into our |self.record_storage| using this model.
        E.g. some view can use this method to insert records.
        At other times it's more convenient to use |self.storage_records| directly to add records
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

    @property
    @abstractmethod
    def storage_records(self) -> List[QObject]:
        pass

    @abstractmethod
    def _record_data(self, record: QObject, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        pass

    @abstractmethod
    def _set_record_data(self, record: QObject, index: QModelIndex, value: Any) -> bool | Tuple[bool, bool]:
        pass

    @abstractmethod
    def _on_record_storage_changing(self):
        pass

    @abstractmethod
    def _on_record_storage_changed(self):
        pass

    @abstractmethod
    def _on_record_added(self, record: QObject, row: int):
        pass

    @abstractmethod
    def _on_record_removed(self, record: QObject, row: int):
        pass
