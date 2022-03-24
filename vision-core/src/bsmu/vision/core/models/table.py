from __future__ import annotations

from abc import abstractmethod
from enum import IntEnum
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QAbstractTableModel, QModelIndex

from bsmu.vision.core.abc import QABCMeta

if TYPE_CHECKING:
    from typing import Type, List, Tuple, Any, Sequence


class TableColumn:
    TITLE = ''


class TableItemDataRole(IntEnum):
    RECORD_REF = Qt.UserRole


class RecordTableModel(QAbstractTableModel, metaclass=QABCMeta):
    def __init__(
            self,
            record_storage: QObject,
            record_type: Type[QObject],
            columns: Sequence[Type[TableColumn]] = (),
            parent: QObject = None,
    ):
        super().__init__(parent)

        self._record_type = record_type
        self._columns = columns
        self._number_by_column = {column: number for number, column in enumerate(self._columns)}

        # Store record signal and handler pairs to disconnect record property changed signals.
        # We can store QMetaObject.Connection objects instead, but QObject.disconnect(connection) leads to memory leaks,
        # when handler is created using functools.partial. Tested using Python 3.9.7, PySide 6.2.3, Windows 10.
        self._property_changed_connections_by_record = {}

        self._record_storage = None
        self.record_storage = record_storage

    def clean_up(self):
        self.record_storage = None

    def record_row(self, record: QObject) -> int:
        """
        # This variant leads to memory leaks. May be the |record| is cached somewhere?
        # Some other variants are listed here:
        # https://wiki.qt.io/Technical_FAQ#How_can_a_QModelIndex_be_retrived_from_the_model_for_an_internal_data_item.3F
        matched_indexes = self.match(
            self.index(0, self.record_column_number),
            TableItemDataRole.RECORD_REF,
            record,
            hits=1,
            flags=Qt.MatchExactly
        )
        return matched_indexes[0].row()
        """

        return self.storage_records.index(record)

    @property
    def record_column_number(self) -> int:
        return 0  # Use zero column to store record reference

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
            for record in self.storage_records:
                self._on_record_removing(record, self.record_row(record))

        self._record_storage = value

        if self._record_storage is not None:
            for record in self.storage_records:
                self._on_record_added(record, self.record_row(record))
            self._on_record_storage_changed()

        self.endResetModel()

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._number_by_column[column]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or self.record_storage is None else len(self.storage_records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or self.record_storage is None else len(self._columns)

    def row_record(self, row: int) -> QObject:
        record_model_index = self.index(row, self.record_column_number)
        return self.data(record_model_index, TableItemDataRole.RECORD_REF)

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

    """
    # Uncomment this method to add index internal pointers to record
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        internal_ptr = self.storage_records[row] if column == self.record_column_number else None
        return self.createIndex(row, column, internal_ptr)
    """

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return

        if index.row() >= len(self.storage_records) or index.row() < 0:
            return

        record = self.storage_records[index.row()]
        if role == TableItemDataRole.RECORD_REF:
            if index.column() == self.record_column_number:
                return record

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

    def _on_storage_record_adding(self, record: QObject):
        # Append one row
        new_record_row = self.rowCount()
        self.beginInsertRows(QModelIndex(), new_record_row, new_record_row)

    def _on_storage_record_added(self, record: QObject):
        self.endInsertRows()
        new_record_row = self.rowCount() - 1
        self._on_record_added(record, new_record_row)

    def _on_storage_record_removing(self, record: QObject):
        record_row = self.record_row(record)
        self._on_record_removing(record, record_row)
        self.beginRemoveRows(QModelIndex(), record_row, record_row)

    def _on_storage_record_removed(self, record: QObject):
        self.endRemoveRows()

    def _create_record_connections(self, record, signal_slot_pairs):
        record_property_changed_connections = set()
        for signal, slot in signal_slot_pairs:
            record_property_changed_connections.add(self._create_record_connection(record, signal, slot))
        self._property_changed_connections_by_record[record] = record_property_changed_connections

    def _create_record_connection(self, record, signal, slot) -> tuple:
        handler = partial(slot, record)
        signal.connect(handler)
        return signal, handler

    def _remove_record_connections(self, record):
        record_property_changed_connections = self._property_changed_connections_by_record.pop(record)
        for signal, handler in record_property_changed_connections:
            signal.disconnect(handler)

    @property
    @abstractmethod
    def storage_records(self) -> List[QObject]:
        pass

    @abstractmethod
    def _record_data(self, record: QObject, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        pass

    def _set_record_data(self, record: QObject, index: QModelIndex, value: Any) -> bool | Tuple[bool, bool]:
        pass

    def _on_record_storage_changing(self):
        pass

    def _on_record_storage_changed(self):
        pass

    def _on_record_added(self, record: QObject, row: int):
        pass

    def _on_record_removing(self, record: QObject, row: int):
        pass
