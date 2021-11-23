from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from PySide2.QtCore import QObject, Qt, Signal, QAbstractTableModel, QModelIndex, QSize
from PySide2.QtGui import QImage
from PySide2.QtWidgets import QGridLayout, QTableView, QHeaderView, QStyledItemDelegate

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.core.data import Data
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter, ModelParams as DnnModelParams
from bsmu.vision.plugins.windows.main import WindowsMenu
from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
from bsmu.vision.widgets.viewers.base import DataViewer

if TYPE_CHECKING:
    from typing import List, Any, Type

    from PySide2.QtCore import QAbstractItemModel
    from PySide2.QtWidgets import QWidget, QStyleOptionViewItem

    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager


class RetinalFundusTableVisualizerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'data_visualization_manager_plugin': 'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
            mdi_plugin: MdiPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._mdi = self._mdi_plugin.mdi

        segmenter_model_name = self.config.value('segmenter-model-name')
        segmenter_model_path = self.data_path(self._DNN_MODELS_DIR_NAME, segmenter_model_name)
        self.table_visualizer = RetinalFundusTableVisualizer(
            self._data_visualization_manager, self._mdi, segmenter_model_path)

        self._data_visualization_manager.data_visualized.connect(self.table_visualizer.visualize_retinal_fundus_data)

        self._main_window.add_menu_action(WindowsMenu, 'Table', self._disable, #% self.table_visualizer.raise_journal_sub_window,
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
    def __init__(self, data: PatientRetinalFundusJournal, preview_height: int | None = None, parent: QObject = None):
        super().__init__(parent)

        self._data = data
        self._data.record_adding.connect(self._on_data_record_adding)
        self._data.record_added.connect(self.endInsertRows)

        self._preview_height = preview_height

        self._columns = [PreviewTableColumn, NameTableColumn]
        self._number_by_column = {column: number for number, column in enumerate(self._columns)}

        # Store numpy array's data for preview images, because QImage uses it without copying,
        # and QImage will crash if it's data buffer will be deleted
        self._preview_data_buffer_by_row = {}

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
            if index.column() == self.column_number(NameTableColumn):
                return record.image.path_name
        elif role == TableItemDataRole.RECORD_REF:
            if index.column() == self.column_number(PreviewTableColumn):
                return record
        elif role == Qt.DecorationRole:
            if index.column() == self.column_number(PreviewTableColumn):
                preview_rgba_pixels = image_converter.converted_to_rgba(record.image.array)
                # Keep reference to numpy data, otherwise QImage will crash
                self._preview_data_buffer_by_row[index.row()] = preview_rgba_pixels.data

                qimage_format = QImage.Format_RGBA8888_Premultiplied if preview_rgba_pixels.itemsize == 1 \
                    else QImage.Format_RGBA64_Premultiplied
                preview_qimage = image_converter.numpy_rgba_image_to_qimage(preview_rgba_pixels, qimage_format)
                if self._preview_height is not None:
                    preview_qimage = preview_qimage.scaledToHeight(self._preview_height, Qt.SmoothTransformation)
                return preview_qimage

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


class ImageCenterAlignmentDelegate(QStyledItemDelegate):
    def __init__(self, table_view: QTableView, parent: QObject = None):
        super().__init__(parent)

        self._table_view = table_view

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)

        option.decorationSize = QSize(self._table_view.columnWidth(index.column()),
                                      self._table_view.verticalHeader().defaultSectionSize())
        # option.decorationAlignment = Qt.AlignCenter


class PatientRetinalFundusJournalTableView(QTableView):
    record_selected = Signal(PatientRetinalFundusRecord)

    def __init__(self, row_height: int | None = None, parent: QWidget = None):
        super().__init__(parent)

        if row_height is not None:
            vertical_header = self.verticalHeader()
            vertical_header.setSectionResizeMode(QHeaderView.Fixed)
            vertical_header.setDefaultSectionSize(row_height)

    def setModel(self, model: QAbstractItemModel):
        super().setModel(model)

        if model is None:
            return

        self.setItemDelegateForColumn(self.model().column_number(PreviewTableColumn),
                                      ImageCenterAlignmentDelegate(self))

        self.selectionModel().currentRowChanged.connect(self._on_current_row_changed)

    def _on_current_row_changed(self, current: QModelIndex, previous: QModelIndex):
        self.record_selected.emit(self.model().row_record(current.row()))


class PatientRetinalFundusJournalViewer(DataViewer):
    record_selected = Signal(PatientRetinalFundusRecord)

    def __init__(self, data: PatientRetinalFundusJournal = None):
        super().__init__(data)

        row_height = 64
        self._table_model = PatientRetinalFundusJournalTableModel(data, preview_height=row_height - 4)
        self._table_view = PatientRetinalFundusJournalTableView(row_height=row_height)
        self._table_view.setModel(self._table_model)
        self._table_view.record_selected.connect(self.record_selected)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self._table_view)
        self.setLayout(grid_layout)


class RetinalFundusTableVisualizer(QObject):
    def __init__(self, visualization_manager: DataVisualizationManager, mdi: Mdi, segmenter_model_path: Path):
        super().__init__()

        self._visualization_manager = visualization_manager
        self._mdi = mdi

        self._segmenter = DnnSegmenter(DnnModelParams(segmenter_model_path, input_image_size=(256, 256)))

        self._journal = PatientRetinalFundusJournal()
        self._journal.add_record(PatientRetinalFundusRecord(FlatImage(
            array=np.random.randint(low=0, high=256, size=(50, 50), dtype=np.uint8),
            path=Path(r'D:\Temp\Void-1.png'))))
        self._journal.add_record(PatientRetinalFundusRecord(FlatImage(
            array=np.random.randint(low=0, high=256, size=(50, 50), dtype=np.uint8),
            path=Path(r'D:\Temp\Void-2.png'))))
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
            mask = self._segmenter.segment(image.array)

            mask = np.squeeze(mask)
            print('ssss', image.array.shape[:2])
            mask = cv2.resize(mask, (image.array.shape[1], image.array.shape[0]), interpolation=cv2.INTER_LINEAR)

            mask = mask.astype(np.uint8)
            print('MASK', mask.shape, mask.dtype, mask.min(), mask.max(), '\n', mask)
            #      - [0, 0, 0, 0, 0]
            #      - [1, 255, 0, 0, 255]
            mask_pallete = Palette.from_sparse_index_list([[0, 0, 0, 0, 0],
                                                           [1, 255, 255, 255, 255]])

            # image_small = cv2.resize(image.array, (256, 256), interpolation=cv2.INTER_AREA)
            # data.add_layer_from_image(FlatImage(array=image_small,
            #                                     ), name='Image Small')

            data.add_layer_from_image(FlatImage(array=mask,
                                                palette=mask_pallete
                                                ), name='Mask')
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
