from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import List, Any, Type
from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject, Qt, Signal, QAbstractTableModel, QModelIndex
from PySide2.QtWidgets import QGridLayout, QTableView

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import WindowsMenu
from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision_core.data import Data
from bsmu.vision_core.image.base import FlatImage
from bsmu.vision_core.image.layered import LayeredImage

if TYPE_CHECKING:
    from PySide2.QtCore import QAbstractItemModel
    from PySide2.QtWidgets import QWidget

    from bsmu.vision.app import App
    from bsmu.vision.plugins.doc_interfaces.mdi import Mdi
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManager


class RetinalFundusTableVisualizerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager
        mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi
        self.table_visualizer = RetinalFundusTableVisualizer(self.data_visualization_manager, mdi)

    def _enable(self):
        self.data_visualization_manager.data_visualized.connect(self.table_visualizer.visualize_retinal_fundus_data)

        self.main_window.add_menu_action(WindowsMenu, 'Table', self.table_visualizer.raise_journal_sub_window,
                                         Qt.CTRL + Qt.Key_1)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.table_visualizer.visualize_retinal_fundus_data)


class PatientRetinalFundusRecord(QObject):
    def __init__(self, image: FlatImage):
        super().__init__()

        self._image = image

    @property
    def image(self) -> FlatImage:
        return self._image


class PatientRetinalFundusJournal(Data):
    record_adding = Signal(PatientRetinalFundusRecord)
    record_added = Signal(PatientRetinalFundusRecord)

    def __init__(self):
        super().__init__()

        self._records = []

    @property
    def records(self) -> List[PatientRetinalFundusRecord]:
        return self._records

    def add_record(self, record: PatientRetinalFundusRecord):
        self.record_adding.emit(record)
        self.records.append(record)
        self.record_added.emit(record)


class TableColumn:
    TITLE = ''


class PreviewTableColumn(TableColumn):
    TITLE = 'Preview'


class NameTableColumn(TableColumn):
    TITLE = 'Name'


class TableItemDataRole(IntEnum):
    RECORD_REF = Qt.UserRole


class PatientRetinalFundusJournalTableModel(QAbstractTableModel):
    def __init__(self, data: PatientRetinalFundusJournal, parent: QObject = None):
        super().__init__(parent)

        self._data = data
        self._data.record_adding.connect(self._on_data_record_adding)
        self._data.record_added.connect(self.endInsertRows)

        self._columns = [PreviewTableColumn, NameTableColumn]
        self._number_by_column = {column: number for number, column in enumerate(self._columns)}

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._number_by_column[column]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data.records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return

        if index.row() >= len(self._data.records) or index.row() < 0:
            return

        record = self._data.records[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(PreviewTableColumn):
                return record.image.path_name
            elif index.column() == self.column_number(NameTableColumn):
                return record.image.path_name
        elif role == TableItemDataRole.RECORD_REF:
            if index.column() == self.column_number(PreviewTableColumn):
                return record

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return

        if orientation == Qt.Horizontal:
            return self._columns[section].TITLE
        elif orientation == Qt.Vertical:
            return section + 1

    # Need this function only to insert some rows into our |self._data| using this model
    # E.g. some view can use this function to insert rows
    # At other times it's more convenient to use |self._data.add_record| method
    def insertRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        for i in range(count):
            self._data.records.insert(row, PatientRetinalFundusRecord(FlatImage()))

        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        del self._data.records[row: row + count]

        self.endRemoveRows()
        return True

    def row_record(self, row: int) -> PatientRetinalFundusRecord:
        preview_model_index = self.index(row, self.column_number(PreviewTableColumn))
        return self.data(preview_model_index, TableItemDataRole.RECORD_REF)

    def _on_data_record_adding(self):
        # Append one row
        row_count = self.rowCount()
        self.beginInsertRows(QModelIndex(), row_count, row_count)


class PatientRetinalFundusJournalTableView(QTableView):
    record_selected = Signal(PatientRetinalFundusRecord)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

    def setModel(self, model: QAbstractItemModel):
        super().setModel(model)

        self.selectionModel().currentRowChanged.connect(self._on_current_row_changed)

    def _on_current_row_changed(self, current: QModelIndex, previous: QModelIndex):
        self.record_selected.emit(self.model().row_record(current.row()))


class PatientRetinalFundusJournalViewer(DataViewer):
    record_selected = Signal(PatientRetinalFundusRecord)

    def __init__(self, data: PatientRetinalFundusJournal = None):
        super().__init__(data)

        self._table_model = PatientRetinalFundusJournalTableModel(data)
        self._table_view = PatientRetinalFundusJournalTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.record_selected.connect(self.record_selected)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self._table_view)
        self.setLayout(grid_layout)


class RetinalFundusTableVisualizer(QObject):
    def __init__(self, visualization_manager: DataVisualizationManager, mdi: Mdi):
        super().__init__()

        self._visualization_manager = visualization_manager
        self._mdi = mdi

        self._journal = PatientRetinalFundusJournal()
        self._journal.add_record(
            PatientRetinalFundusRecord(FlatImage(array=np.random.rand(50, 50), path=Path(r'D:\Temp\Void-1.png'))))
        self._journal.add_record(
            PatientRetinalFundusRecord(FlatImage(array=np.random.rand(50, 50), path=Path(r'D:\Temp\Void-2.png'))))
        self._journal_viewer = PatientRetinalFundusJournalViewer(self.journal)
        self._journal_viewer.record_selected.connect(self._on_journal_record_selected)

        self._image_sub_windows_by_record = {}

        self._journal_sub_window = DataViewerSubWindow(self.journal_viewer)
        self._journal_sub_window.layout_anchors = np.array([[0, 0], [0.6, 1]])
        self._mdi.addSubWindow(self._journal_sub_window)

    @property
    def journal(self) -> PatientRetinalFundusJournal:
        return self._journal

    @property
    def journal_viewer(self) -> PatientRetinalFundusJournalViewer:
        return self._journal_viewer

    def visualize_retinal_fundus_data(self, data: Data, data_viewer_sub_windows: List[DataViewerSubWindow]):
        print('visualize_retinal_fundus_data', type(data))

        if isinstance(data, LayeredImage):
            first_layer = data.layers[0]

            image = first_layer.image
            record = PatientRetinalFundusRecord(image)
            self.journal.add_record(record)

            self._image_sub_windows_by_record[record] = data_viewer_sub_windows

            for sub_window in data_viewer_sub_windows:
                sub_window.layout_anchors = np.array([[0.6, 0], [1, 1]])
                sub_window.lay_out_to_anchors()

    def raise_journal_sub_window(self):
        self._journal_sub_window.show_normal()

        self._mdi.setActiveSubWindow(self._journal_sub_window)

        # self.journal_sub_window.raise_()

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        image_sub_windows = self._image_sub_windows_by_record.get(record, [])
        for image_sub_window in image_sub_windows:
            image_sub_window.show_normal()

            image_sub_window.raise_()
