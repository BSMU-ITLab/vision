from __future__ import annotations

from abc import abstractmethod
from enum import IntEnum, auto
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QAbstractTableModel, QModelIndex

from bsmu.vision.core.abc import QABCMeta
from bsmu.vision.core.models import ObjectParameter, ObjectRecord

if TYPE_CHECKING:
    from typing import Type, List, Tuple, Any, Sequence


class TableColumn:
    TITLE = ''
    OBJECT_PARAMETER_TYPE: Type[ObjectParameter] = None
    EDITABLE = False
    TEXT_ALIGNMENT = Qt.AlignCenter


class TableItemDataRole(IntEnum):
    RECORD_REF = Qt.UserRole
    PARAMETER = auto()


class RecordTableModel(QAbstractTableModel, metaclass=QABCMeta):
    def __init__(
            self,
            record_storage: QObject,
            record_type: Type[ObjectRecord],
            columns: Sequence[Type[TableColumn]] = (),
            parent: QObject = None,
    ):
        super().__init__(parent)

        self._record_type = record_type

        # Store record signal and handler pairs to disconnect record property changed signals.
        # We can store QMetaObject.Connection objects instead, but QObject.disconnect(connection) leads to memory leaks,
        # when handler is created using functools.partial. Tested using Python 3.9.7, PySide 6.2.3, Windows 10.
        self._property_changed_connections_by_record = {}

        self._record_storage = None
        self.record_storage = record_storage

        self._columns = []
        self._number_by_column = {}
        self._column_by_parameter_type = {}
        for column in columns:
            self.add_column(column)

    def add_column(self, column: Type[TableColumn]) -> int:
        assert column not in self._number_by_column, 'Such column already exists'
        number = len(self._columns)

        self.beginInsertColumns(QModelIndex(), number, number)

        self._columns.append(column)
        self._number_by_column[column] = number
        self._column_by_parameter_type[column.OBJECT_PARAMETER_TYPE] = column

        self.endInsertColumns()
        return number

    def clean_up(self):
        self.record_storage = None

    def record_row(self, record: ObjectRecord) -> int:
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
    def columns(self) -> Sequence[Type[TableColumn]]:
        return self._columns

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
                record_row = self.record_row(record)
                self._on_record_removing(record, record_row)
                self._on_record_removed(record, record_row)

        self._record_storage = value

        if self._record_storage is not None:
            for record in self.storage_records:
                record_row = self.record_row(record)
                self._on_record_adding(record, record_row)
                self._on_record_added(record, record_row)
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
        if self._columns[index.column()].EDITABLE:
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

        if role == Qt.DisplayRole:
            column_type = self._columns[index.column()]
            if column_type.OBJECT_PARAMETER_TYPE is not None:
                return record.parameter_value_str_by_type(column_type.OBJECT_PARAMETER_TYPE)

        if role == TableItemDataRole.PARAMETER:
            column_type = self._columns[index.column()]
            if column_type.OBJECT_PARAMETER_TYPE is not None:
                return record.parameter_by_type(column_type.OBJECT_PARAMETER_TYPE)

        if role == Qt.TextAlignmentRole:
            column_type = self._columns[index.column()]
            return column_type.TEXT_ALIGNMENT

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

    def _on_storage_record_adding(self, record: ObjectRecord, index: int):
        self._on_record_adding(record, index)
        self.beginInsertRows(QModelIndex(), index, index)

    def _on_storage_record_added(self, record: ObjectRecord, index: int):
        self.endInsertRows()
        self._on_record_added(record, index)

    def _on_storage_record_removing(self, record: ObjectRecord, index: int):
        self._on_record_removing(record, index)
        self.beginRemoveRows(QModelIndex(), index, index)

    def _on_storage_record_removed(self, record: ObjectRecord, index: int):
        self.endRemoveRows()
        self._on_record_removed(record, index)

    def _create_record_connections(self, record, signal_slot_pairs):
        record_property_changed_connections = \
            self._property_changed_connections_by_record.setdefault(record, set())
        for signal, slot in signal_slot_pairs:
            record_property_changed_connections.add(self._create_record_connection(record, signal, slot))

    def _create_record_connection(self, record, signal, slot) -> tuple:
        handler = partial(slot, record)
        signal.connect(handler)
        return signal, handler

    def _remove_record_connections(self, record):
        record_property_changed_connections = self._property_changed_connections_by_record.pop(record, set())
        for signal, handler in record_property_changed_connections:
            signal.disconnect(handler)

    @property
    @abstractmethod
    def storage_records(self) -> List[ObjectRecord]:
        pass

    @abstractmethod
    def _record_data(self, record: ObjectRecord, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        pass

    def _set_record_data(self, record: ObjectRecord, index: QModelIndex, value: Any) -> bool | Tuple[bool, bool]:
        pass

    def _on_record_storage_changing(self):
        pass

    def _on_record_storage_changed(self):
        pass

    def _on_record_parameter_value_changed(self, record: ObjectRecord, parameter: ObjectParameter):
        if (parameter_column := self._column_by_parameter_type.get(type(parameter))) is None:
            return
        record_parameter_model_index = self.index(self.record_row(record), self.column_number(parameter_column))
        self.dataChanged.emit(record_parameter_model_index, record_parameter_model_index)

    def _on_record_adding(self, record: ObjectRecord, row: int):
        pass

    def _on_record_added(self, record: ObjectRecord, row: int):
        self._create_record_connections(
            record,
            ((record.parameter_added, self._on_record_parameter_value_changed),
             (record.parameter_value_changed, self._on_record_parameter_value_changed),
             ))

    def _on_record_removing(self, record: ObjectRecord, row: int):
        self._remove_record_connections(record)

    def _on_record_removed(self, record: ObjectRecord, row: int):
        pass
