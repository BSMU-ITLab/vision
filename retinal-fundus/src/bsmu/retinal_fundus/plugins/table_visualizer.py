from __future__ import annotations

import re
from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal, QModelIndex, QSize, QMargins
from PySide6.QtGui import QImage, QPainter, QFont, QPalette, QColor, QKeySequence
from PySide6.QtWidgets import QWidget, QGridLayout, QTableView, QHeaderView, QStyledItemDelegate, QSplitter, \
    QAbstractItemView, QStyle, QFrame, QMessageBox

import bsmu.vision.core.converters.image as image_converter
from bsmu.retinal_fundus.plugins.main_window import TableMenu
from bsmu.vision.core.bbox import BBox
from bsmu.vision.core.data import Data
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.models.base import ObjectRecord, positive_list_insert_index, positive_list_remove_index
from bsmu.vision.core.models.table import RecordTableModel, TableColumn, TableItemDataRole
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter
from bsmu.vision.plugins.windows.main import WindowsMenu
from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer

if TYPE_CHECKING:
    from typing import List, Any, Type, Sequence

    from PySide6.QtCore import QAbstractItemModel
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.core.models.base import ObjectParameter
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.viewers.image.settings import ImageViewerSettingsPlugin
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.post_load_converters.manager import PostLoadConversionManagerPlugin, \
        PostLoadConversionManager
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, ImageLayerView, ImageViewerSettings


class RetinalFundusTableVisualizerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'data_visualization_manager_plugin': 'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
        'post_load_conversion_manager_plugin':
            'bsmu.vision.plugins.post_load_converters.manager.PostLoadConversionManagerPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'image_viewer_settings_plugin': 'bsmu.vision.plugins.viewers.image.settings.ImageViewerSettingsPlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
            post_load_conversion_manager_plugin: PostLoadConversionManagerPlugin,
            mdi_plugin: MdiPlugin,
            image_viewer_settings_plugin: ImageViewerSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager | None = None

        self._post_load_conversion_manager_plugin = post_load_conversion_manager_plugin
        self._post_load_conversion_manager: PostLoadConversionManager | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._image_viewer_settings_plugin = image_viewer_settings_plugin
        self._image_viewer_settings: ImageViewerSettings | None = None

        self._table_visualizer: RetinalFundusTableVisualizer | None = None

    @property
    def table_visualizer(self) -> RetinalFundusTableVisualizer | None:
        return self._table_visualizer

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._post_load_conversion_manager = self._post_load_conversion_manager_plugin.post_load_conversion_manager
        self._mdi = self._mdi_plugin.mdi
        self._image_viewer_settings = self._image_viewer_settings_plugin.settings

        disk_segmenter_model_params = DnnModelParams.from_config(
            self.config.value('disk-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        cup_segmenter_model_params = DnnModelParams.from_config(
            self.config.value('cup-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        vessels_segmenter_model_params = DnnModelParams.from_config(
            self.config.value('vessels-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        self._table_visualizer = RetinalFundusTableVisualizer(
            self._data_visualization_manager, self._mdi, self._image_viewer_settings,
            disk_segmenter_model_params, cup_segmenter_model_params, vessels_segmenter_model_params)

        self._post_load_conversion_manager.data_converted.connect(self._table_visualizer.visualize_retinal_fundus_data)

        self._main_window.add_menu_action(TableMenu, 'Clear', self._confirm_and_clear_journal)
        self._main_window.add_menu_action(
            TableMenu, 'Delete Selected Records', self._table_visualizer.remove_selected_records, QKeySequence.Delete)

        self._main_window.add_menu_action(
            WindowsMenu, 'Table', self._table_visualizer.maximize_journal_viewer, Qt.CTRL | Qt.Key_1)
        self._main_window.add_menu_action(
            WindowsMenu, 'Table/Image', self._table_visualizer.show_journal_and_image_viewers, Qt.CTRL | Qt.Key_2)
        self._main_window.add_menu_action(
            WindowsMenu, 'Image', self._table_visualizer.maximize_layered_image_viewer, Qt.CTRL | Qt.Key_3)

    def _disable(self):
        self._post_load_conversion_manager.data_converted.disconnect(
            self._table_visualizer.visualize_retinal_fundus_data)

    def _confirm_and_clear_journal(self):
        if QMessageBox.question(
                self._main_window,
                'Clear Table?',
                'Are you sure you want to delete all records from the table?') == QMessageBox.Yes:
            self._table_visualizer.clear_journal()


class Patient:
    def __init__(self, name: str, records: Sequence[PatientRetinalFundusRecord] = None):
        self._name = name
        self._records = list(records) if records else []

    def add_record(self, record: PatientRetinalFundusRecord):
        self._records.append(record)

    def remove_record(self, record: PatientRetinalFundusRecord):
        self._records.remove(record)

    @property
    def name(self) -> str:
        return self._name

    @property
    def records(self) -> list[PatientRetinalFundusRecord]:
        return self._records


class PatientRetinalFundusRecord(ObjectRecord):
    IMAGE_LAYER_NAME = 'image'
    DISK_REGION_MASK_LAYER_NAME = 'disk-region-mask'
    DISK_MASK_LAYER_NAME = 'disk-mask'
    CUP_MASK_LAYER_NAME = 'cup-mask'
    VESSELS_MASK_LAYER_NAME = 'vessels-mask'

    disk_bbox_changed = Signal(BBox)

    disk_area_changed = Signal(float)
    cup_area_changed = Signal(float)
    cup_to_disk_area_ratio_changed = Signal(float)

    def __init__(self, patient: Patient, layered_image: LayeredImage):
        super().__init__()

        self._patient = patient

        self._layered_image = layered_image

        self._disk_bbox: BBox | None = None

        self._disk_area: float | None = None
        self._cup_area: float | None = None
        self._cup_to_disk_area_ratio: float | None = None

        self._patient.add_record(self)

    @classmethod
    def from_flat_image(cls, image: FlatImage) -> PatientRetinalFundusRecord:
        layered_image = LayeredImage()
        layered_image.add_layer_from_image(image, cls.IMAGE_LAYER_NAME)
        return cls(layered_image)

    @property
    def patient(self) -> Patient:
        return self._patient

    @property
    def layered_image(self) -> LayeredImage:
        return self._layered_image

    @property
    def image(self) -> FlatImage:
        return self._layered_image.layers[0].image

    @property
    def disk_mask(self) -> FlatImage | None:
        return self.image_by_layer_name(self.DISK_MASK_LAYER_NAME)

    @property
    def disk_bbox(self) -> BBox | None:
        return self._disk_bbox

    @disk_bbox.setter
    def disk_bbox(self, value: BBox | None):
        if self._disk_bbox != value:
            self._disk_bbox = value
            self.disk_bbox_changed.emit(self._disk_bbox)

    @property
    def cup_mask(self) -> FlatImage | None:
        return self.image_by_layer_name(self.CUP_MASK_LAYER_NAME)

    @property
    def vessels_mask(self) -> FlatImage | None:
        return self.image_by_layer_name(self.VESSELS_MASK_LAYER_NAME)

    @property
    def disk_area(self) -> float | None:
        return self._disk_area

    @disk_area.setter
    def disk_area(self, value: float):
        if self._disk_area != value:
            self._disk_area = value
            self.disk_area_changed.emit(self._disk_area)

    @property
    def disk_area_str(self) -> str:
        return self._value_str(self.disk_area)

    @property
    def cup_area(self) -> float | None:
        return self._cup_area

    @cup_area.setter
    def cup_area(self, value: float):
        if self._cup_area != value:
            self._cup_area = value
            self.cup_area_changed.emit(self._cup_area)

    @property
    def cup_area_str(self) -> str:
        return self._value_str(self.cup_area)

    @property
    def cup_to_disk_area_ratio(self) -> float | None:
        return self._cup_to_disk_area_ratio

    @cup_to_disk_area_ratio.setter
    def cup_to_disk_area_ratio(self, value: float):
        if self._cup_to_disk_area_ratio != value:
            self._cup_to_disk_area_ratio = value
            self.cup_to_disk_area_ratio_changed.emit(self._cup_to_disk_area_ratio)

    @property
    def cup_to_disk_area_ratio_str(self) -> str:
        return self._value_str(self.cup_to_disk_area_ratio)

    def image_by_layer_name(self, layer_name: str) -> FlatImage | None:
        layer = self._layered_image.layer_by_name(layer_name)
        return None if layer is None else layer.image

    def calculate_params(self):
        self._calculate_disk_area()
        self._calculate_cup_area()
        self._calculate_cup_to_disk_area_ratio()

    def _calculate_disk_area(self) -> float:
        if self._disk_area is None:
            self.disk_area = self._count_nonzero_layer_pixels(self.DISK_MASK_LAYER_NAME)
        return self._disk_area

    def _calculate_cup_area(self) -> float:
        if self._cup_area is None:
            self.cup_area = self._count_nonzero_layer_pixels(self.CUP_MASK_LAYER_NAME)
        return self._cup_area

    def _calculate_cup_to_disk_area_ratio(self):
        if self._cup_to_disk_area_ratio is None:
            self._calculate_disk_area()
            self.cup_to_disk_area_ratio = self._calculate_cup_area() / self.disk_area if self.disk_area != 0 else None
        return self._cup_to_disk_area_ratio

    def _count_nonzero_layer_pixels(self, layer_name: str) -> int:
        layer = self._layered_image.layer_by_name(layer_name)
        return np.count_nonzero(layer.image_pixels)


class PatientRetinalFundusJournal(Data):
    record_adding = Signal(PatientRetinalFundusRecord, int)
    record_added = Signal(PatientRetinalFundusRecord, int)
    record_removing = Signal(PatientRetinalFundusRecord, int)
    record_removed = Signal(PatientRetinalFundusRecord, int)

    def __init__(self):
        super().__init__()

        self._patients = []

        self._records = []

    @property
    def records(self) -> list[PatientRetinalFundusRecord]:
        return self._records

    @property
    def patients(self) -> list[Patient]:
        return self._patients

    """
    If |index| is None then add record to the end
    """
    def add_record(self, record: PatientRetinalFundusRecord, index: int = None):
        index = positive_list_insert_index(self._records, index)
        self.record_adding.emit(record, index)
        self.records.insert(index, record)

        if record.patient not in self._patients:
            if index == 0:
                self._patients.insert(0, record.patient)
            else:
                prev_record = self._records[index - 1]
                prev_patient_index = self._patients.index(prev_record.patient)
                self._patients.insert(prev_patient_index + 1, record.patient)

        self.record_added.emit(record, index)

    """
    If |index| is None then remove last record
    """
    def remove_record_by_index(self, index: int = None):
        index = positive_list_remove_index(self._records, index)
        record = self._records[index]
        self._remove_record(record, index)

    def remove_record(self, record: PatientRetinalFundusRecord):
        self._remove_record(record, self._records.index(record))

    def _remove_record(self, record: PatientRetinalFundusRecord, index: int):
        self.record_removing.emit(record, index)

        record.patient.remove_record(record)
        if not record.patient.records:
            self._patients.remove(record.patient)

        del self._records[index]
        self.record_removed.emit(record, index)

    def clear(self):
        # Remove records from the end
        for i in range(len(self._records) - 1, -1, -1):
            self.remove_record_by_index(i)


class PreviewTableColumn(TableColumn):
    TITLE = 'Preview'


class NameTableColumn(TableColumn):
    TITLE = 'Name'


class DiskAreaTableColumn(TableColumn):
    TITLE = 'Disk\nArea'


class CupAreaTableColumn(TableColumn):
    TITLE = 'Cup\nArea'


class CupToDiskAreaRatioTableColumn(TableColumn):
    TITLE = 'Cup/Disk\nArea'


class PatientRetinalFundusJournalTableModel(RecordTableModel):
    def __init__(
            self,
            record_storage: PatientRetinalFundusJournal = None,
            parent: QObject = None
    ):
        super().__init__(
            record_storage,
            PatientRetinalFundusRecord,
            (PreviewTableColumn, NameTableColumn, DiskAreaTableColumn, CupAreaTableColumn,
             CupToDiskAreaRatioTableColumn),
            parent,
        )

        # Store numpy array's data for preview images, because QImage uses it without copying,
        # and QImage will crash if it's data buffer will be deleted
        self._preview_data_buffer_by_record = {}
        # Cache QImage preview for better performance
        self._preview_qimage_by_record = {}

    @property
    def storage_records(self) -> List[PatientRetinalFundusRecord]:
        return self.record_storage.records

    def _record_data(self, record: PatientRetinalFundusRecord, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(NameTableColumn):
                return record.image.path_name
            elif index.column() == self.column_number(DiskAreaTableColumn):
                return record.disk_area_str
            elif index.column() == self.column_number(CupAreaTableColumn):
                return record.cup_area_str
            elif index.column() == self.column_number(CupToDiskAreaRatioTableColumn):
                return record.cup_to_disk_area_ratio_str
        elif role == Qt.DecorationRole:
            if index.column() == self.column_number(PreviewTableColumn):
                return self._preview_qimage_by_record[record]

    def _on_record_storage_changing(self):
        self.record_storage.record_adding.disconnect(self._on_storage_record_adding)
        self.record_storage.record_added.disconnect(self._on_storage_record_added)
        self.record_storage.record_removing.disconnect(self._on_storage_record_removing)
        self.record_storage.record_removed.disconnect(self._on_storage_record_removed)

    def _on_record_storage_changed(self):
        self.record_storage.record_adding.connect(self._on_storage_record_adding)
        self.record_storage.record_added.connect(self._on_storage_record_added)
        self.record_storage.record_removing.connect(self._on_storage_record_removing)
        self.record_storage.record_removed.connect(self._on_storage_record_removed)

    def _generate_record_preview(self, record: PatientRetinalFundusRecord):
        preview_rgba_pixels = image_converter.converted_to_rgba(record.image.array)
        # Keep reference to numpy data, otherwise QImage will crash
        self._preview_data_buffer_by_record[record] = preview_rgba_pixels.data

        qimage_format = QImage.Format_RGBA8888_Premultiplied if preview_rgba_pixels.itemsize == 1 \
            else QImage.Format_RGBA64_Premultiplied
        preview_qimage = image_converter.numpy_array_to_qimage(preview_rgba_pixels, qimage_format)

        self._preview_qimage_by_record[record] = preview_qimage

    def _delete_record_preview(self, record: PatientRetinalFundusRecord):
        del self._preview_data_buffer_by_record[record]
        del self._preview_qimage_by_record[record]

    def _on_record_adding(self, record: PatientRetinalFundusRecord, row: int):
        super()._on_record_adding(record, row)

        self._generate_record_preview(record)

    def _on_record_added(self, record: PatientRetinalFundusRecord, row: int):
        super()._on_record_added(record, row)

        self._create_record_connections(
            record,
            ((record.disk_area_changed, self._on_disk_area_changed),
             (record.cup_area_changed, self._on_cup_area_changed),
             (record.cup_to_disk_area_ratio_changed, self._on_cup_to_disk_area_ratio_changed),
             ))

    def _on_record_removed(self, record: ObjectRecord, row: int):
        super()._on_record_removed(record, row)

        self._delete_record_preview(record)

    def _on_disk_area_changed(self, record: PatientRetinalFundusRecord, disk_area: float):
        disk_area_model_index = self.index(self.record_row(record), self.column_number(DiskAreaTableColumn))
        self.dataChanged.emit(disk_area_model_index, disk_area_model_index)

    def _on_cup_area_changed(self, record: PatientRetinalFundusRecord, cur_area: float):
        cup_area_model_index = self.index(self.record_row(record), self.column_number(CupAreaTableColumn))
        self.dataChanged.emit(cup_area_model_index, cup_area_model_index)

    def _on_cup_to_disk_area_ratio_changed(self, record: PatientRetinalFundusRecord, cup_to_disk_area_ratio: float):
        cup_to_disk_area_ratio_model_index = \
            self.index(self.record_row(record), self.column_number(CupToDiskAreaRatioTableColumn))
        self.dataChanged.emit(cup_to_disk_area_ratio_model_index, cup_to_disk_area_ratio_model_index)


class StyledItemDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        painter.save()
        self._paint(painter, option, index)
        painter.restore()

    def _paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        pass

    @staticmethod
    def _item_parameter(index: QModelIndex) -> ObjectParameter:
        return index.data(TableItemDataRole.PARAMETER)


class ImageCenterAlignmentDelegate(StyledItemDelegate):
    def __init__(self, size_hint: QSize, border: int = 4, parent: QObject = None):
        super().__init__(parent)

        self._size_hint = size_hint
        self._border = border

    def _paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        image = index.data(Qt.DecorationRole)
        scaled_image_rect = option.rect
        scaled_image_rect = scaled_image_rect.marginsRemoved(
            QMargins(self._border, self._border, self._border, self._border))
        image = image.scaled(scaled_image_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        point_to_draw_image = option.rect.center() - image.rect().center()
        painter.drawImage(point_to_draw_image, image)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return self._size_hint


class PatientRetinalFundusJournalTableView(QTableView):
    record_selected = Signal(PatientRetinalFundusRecord)

    def __init__(self, row_height: int | None = None, parent: QWidget = None):
        super().__init__(parent)

        self._row_height = row_height
        if row_height is not None:
            vertical_header = self.verticalHeader()
            vertical_header.setSectionResizeMode(QHeaderView.Fixed)
            vertical_header.setDefaultSectionSize(row_height)

        self._selected_record: PatientRetinalFundusRecord | None = None

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)

        palette = self.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(0, 0, 0, 16))
        palette.setColor(QPalette.Highlight, QColor(204, 228, 247))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

    @property
    def selected_record(self) -> PatientRetinalFundusRecord | None:
        return self._selected_record

    @property
    def selected_records(self) -> list[PatientRetinalFundusRecord]:
        return [self.model().row_record(model_index.row()) for model_index in self.selectionModel().selectedRows()]

    def setModel(self, model: QAbstractItemModel):
        super().setModel(model)

        if model is None:
            return

        self.setItemDelegateForColumn(
            self.model().column_number(PreviewTableColumn),
            ImageCenterAlignmentDelegate(QSize(int(1.25 * self._row_height), self._row_height), parent=self))

        self.selectionModel().currentRowChanged.connect(self._on_current_row_changed)

    def paintEvent(self, event):
        # Draw 'DROP IMAGES HERE' text
        painter = QPainter(self.viewport())
        painter.save()

        painter.setPen(self.palette().placeholderText().color())
        font = QFont('Monospace', 16, QFont.Bold)
        font.setStretch(QFont.SemiExpanded)
        painter.setFont(font)

        last_row = self.model().rowCount() - 1
        all_rows_height = self.rowViewportPosition(last_row) + self.rowHeight(last_row)

        free_rect_to_draw_text = self.viewport().rect()
        free_rect_to_draw_text.setY(all_rows_height)

        text_flags = Qt.AlignCenter
        text = 'DROP\n\nIMAGES\n\nHERE'
        text_bounding_rect = painter.boundingRect(free_rect_to_draw_text, text_flags, text)

        if free_rect_to_draw_text.contains(text_bounding_rect):
            painter.drawText(free_rect_to_draw_text, text_flags, text)

        painter.restore()
        super().paintEvent(event)

    def sizeHintForColumn(self, column: int) -> int:
        if self.model() is None:
            return -1

        if column == self.model().column_number(NameTableColumn):
            return self.fontMetrics().horizontalAdvance('Ivanov Ivan Ivanovich')

        return super().sizeHintForColumn(column)

    def _on_current_row_changed(self, current: QModelIndex, previous: QModelIndex):
        self._selected_record = self.model().row_record(current.row())
        self.record_selected.emit(self._selected_record)


class PatientRetinalFundusJournalViewer(DataViewer):
    record_selected = Signal(PatientRetinalFundusRecord)

    def __init__(self, data: PatientRetinalFundusJournal = None):
        super().__init__(data)

        self._table_model = PatientRetinalFundusJournalTableModel(data)
        self._table_view = PatientRetinalFundusJournalTableView(row_height=64)
        self._table_view.setModel(self._table_model)
        self._table_view.record_selected.connect(self.record_selected)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self._table_view)
        self.setLayout(grid_layout)

    @property
    def selected_record(self) -> PatientRetinalFundusRecord | None:
        return self._table_view.selected_record

    @property
    def selected_records(self) -> list[PatientRetinalFundusRecord]:
        return self._table_view.selected_records

    @property
    def columns(self) -> Sequence[Type[TableColumn]]:
        return self._table_model.columns

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._table_model.column_number(column)

    def record_row(self, record: ObjectRecord) -> int:
        return self._table_model.record_row(record)

    def select_record(self, record: PatientRetinalFundusRecord):
        row = self._table_model.record_row(record)
        self._table_view.selectRow(row)

    def resize_columns_to_contents(self):
        self._table_view.resizeColumnsToContents()

    def add_column(self, column: Type[TableColumn], column_delegate: QStyledItemDelegate):
        column_number = self._table_model.add_column(column)
        if column_delegate is not None:
            self._table_view.setItemDelegateForColumn(column_number, column_delegate)
        self._table_view.resizeColumnToContents(column_number)

    def set_span(self, row: int, column: int, rowSpanCount: int, columnSpanCount: int):
        self._table_view.setSpan(row, column, rowSpanCount, columnSpanCount)


class RecordDetailedInfoViewer(QFrame):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Box)
        self.setFrameShape(QFrame.StyledPanel)

        self._splitter = QSplitter(Qt.Vertical)

        self._layout = QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._splitter)
        self.setLayout(self._layout)

    def add_widget(self, widget: QWidget):
        self._splitter.addWidget(widget)
        self._update_visibility()

    def remove_widget(self, widget: QWidget):
        widget.setParent(None)
        self._update_visibility()

    def _update_visibility(self):
        self.setVisible(self._splitter.count() > 0)


class PatientRetinalFundusIllustratedJournalViewer(DataViewer):
    _DEFAULT_LAYER_VISIBILITY_BY_NAME = {
        PatientRetinalFundusRecord.DISK_REGION_MASK_LAYER_NAME: Visibility(False, 0.2),
        PatientRetinalFundusRecord.DISK_MASK_LAYER_NAME: Visibility(True, 0.5),
        PatientRetinalFundusRecord.CUP_MASK_LAYER_NAME: Visibility(True, 0.5),
        PatientRetinalFundusRecord.VESSELS_MASK_LAYER_NAME: Visibility(True, 0.5),
    }

    def __init__(
            self,
            image_viewer_settings: ImageViewerSettings,
            data: PatientRetinalFundusJournal = None,
            parent: QWidget = None
    ):
        self._journal_viewer = PatientRetinalFundusJournalViewer(data)
        self._journal_viewer.record_selected.connect(self._on_journal_record_selected)

        super().__init__(parent)

        self._detailed_info_viewer = RecordDetailedInfoViewer()
        self._detailed_info_viewer.hide()
        self._journal_with_detailed_info_splitter = QSplitter(Qt.Vertical)
        self._journal_with_detailed_info_splitter.addWidget(self._journal_viewer)
        self._journal_with_detailed_info_splitter.addWidget(self._detailed_info_viewer)

        self._layered_image_viewer = LayeredFlatImageViewer(settings=image_viewer_settings)
        self._layer_visibility_by_name = {}
        self._layered_image_viewer.layer_view_removing.connect(self._save_layer_visibility)
        self._layered_image_viewer.layer_view_added.connect(self._restore_layer_visibility)

        self._splitter = QSplitter()
        self._splitter.addWidget(self._journal_with_detailed_info_splitter)
        self._splitter.addWidget(self._layered_image_viewer)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)
        self.show_journal_and_image_viewers_with_equal_sizes()
        self._splitter_state = self._splitter.saveState()

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self._splitter)
        self.setLayout(grid_layout)

    @property
    def journal_viewer(self) -> PatientRetinalFundusJournalViewer:
        return self._journal_viewer

    @property
    def detailed_info_viewer(self) -> RecordDetailedInfoViewer:
        return self._detailed_info_viewer

    @property
    def layered_image_viewer(self) -> LayeredFlatImageViewer:
        return self._layered_image_viewer

    @property
    def data(self) -> Data:
        return self._journal_viewer.data

    @data.setter
    def data(self, value: Data):
        self._journal_viewer.data = value

    @property
    def data_path_name(self):
        return self._journal_viewer.data_path_name

    def maximize_journal_viewer(self):
        self._maximize_splitter_widget(self._journal_with_detailed_info_splitter)

    def maximize_layered_image_viewer(self):
        self._maximize_splitter_widget(self._layered_image_viewer)

    def show_journal_and_image_viewers_with_equal_sizes(self):
        # Divide the width equally between the two widgets
        splitter_widget_size = max(
            self._journal_viewer.minimumSizeHint().width(), self._layered_image_viewer.minimumSizeHint().width())
        self._splitter.setSizes([splitter_widget_size, splitter_widget_size])

    def show_journal_and_image_viewers(self):
        self._splitter.restoreState(self._splitter_state)
        # If some widget is maximized
        if 0 in self._splitter.sizes():
            self.show_journal_and_image_viewers_with_equal_sizes()

    def add_column(self, column: Type[TableColumn], column_delegate: QStyledItemDelegate):
        self.journal_viewer.add_column(column, column_delegate)

    def _maximize_splitter_widget(self, widget: QWidget):
        sizes = [0] * self._splitter.count()
        widget_index = self._splitter.indexOf(widget)
        sizes[widget_index] = 1
        self._splitter.setSizes(sizes)

    def _on_splitter_moved(self, pos: int, index: int):
        # TODO: do not save the splitter state multiple times here.
        #  We need to save it just one time, when splitter moving finished.
        self._splitter_state = self._splitter.saveState()

    def _save_layer_visibility(self, layer_view: ImageLayerView):
        layer_view_visibility = Visibility(layer_view.visible, layer_view.opacity)
        self._layer_visibility_by_name[layer_view.name] = layer_view_visibility

    def _restore_layer_visibility(self, layer_view: ImageLayerView):
        """
        Restore previous visibility of the layer or use default one.
        (If the layer with such name was added for the first time, then set it's default visibility;
        otherwise visibility customized by a user will remain unchanged)
        """
        layer_visibility_to_restore = self._layer_visibility_by_name.get(layer_view.name)
        if layer_visibility_to_restore is None:
            layer_visibility_to_restore = self._DEFAULT_LAYER_VISIBILITY_BY_NAME.get(layer_view.name)
        if layer_visibility_to_restore is not None:
            layer_view.visible = layer_visibility_to_restore.visible
            layer_view.opacity = layer_visibility_to_restore.opacity

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        self._layered_image_viewer.data = record and record.layered_image
        self.layered_image_viewer.fit_image_in()


class IllustratedJournalSubWindow(DataViewerSubWindow):
    def __init__(self, viewer: DataViewer):
        super().__init__(viewer)

    @property
    def layered_image_viewer(self) -> LayeredImageViewer:
        return self.viewer.layered_image_viewer


class RetinalFundusTableVisualizer(QObject):
    def __init__(
            self,
            visualization_manager: DataVisualizationManager,  #% Temp
            mdi: Mdi,
            image_viewer_settings: ImageViewerSettings,
            disk_segmenter_model_params: DnnModelParams,
            cup_segmenter_model_params: DnnModelParams,
            vessels_segmenter_model_params: DnnModelParams,
    ):
        super().__init__()

        self._visualization_manager = visualization_manager
        self._mdi = mdi
        self._image_viewer_settings = image_viewer_settings

        self._disk_segmenter = DnnSegmenter(disk_segmenter_model_params)
        self._cup_segmenter = DnnSegmenter(cup_segmenter_model_params)
        self._vessels_segmenter = DnnSegmenter(vessels_segmenter_model_params)

        self._columns_resized_to_contents_once = False

        self._disk_mask_palette = Palette.default_binary(255, [102, 255, 128])
        self._cup_mask_palette = Palette.default_binary(255, [189, 103, 255])
        self._vessels_mask_palette = Palette.default_soft([102, 183, 255])

        self._journal = PatientRetinalFundusJournal()

        """
        # Add test images
        self._journal.add_record(PatientRetinalFundusRecord.from_flat_image(FlatImage(
            array=np.random.randint(low=0, high=256, size=(50, 50), dtype=np.uint8),
            path=Path('Void-1.png'))))
        self._journal.add_record(PatientRetinalFundusRecord.from_flat_image(FlatImage(
            array=np.random.randint(low=0, high=256, size=(50, 50), dtype=np.uint8),
            path=Path('Void-2.png'))))
        """

        self._illustrated_journal_viewer = PatientRetinalFundusIllustratedJournalViewer(
            self._image_viewer_settings, self._journal)
        self.journal_viewer.resize_columns_to_contents()

        self._journal_sub_window = IllustratedJournalSubWindow(self._illustrated_journal_viewer)
        self._journal_sub_window.setWindowFlag(Qt.FramelessWindowHint)

        self._mdi.addSubWindow(self._journal_sub_window)
        self._journal_sub_window.showMaximized()

    @property
    def journal(self) -> PatientRetinalFundusJournal:
        return self._journal

    @property
    def illustrated_journal_viewer(self) -> PatientRetinalFundusIllustratedJournalViewer:
        return self._illustrated_journal_viewer

    @property
    def journal_viewer(self) -> PatientRetinalFundusJournalViewer:
        return self._illustrated_journal_viewer.journal_viewer

    @property
    def detailed_info_viewer(self) -> RecordDetailedInfoViewer:
        return self._illustrated_journal_viewer.detailed_info_viewer

    @property
    def layered_image_viewer(self) -> LayeredFlatImageViewer:
        return self._illustrated_journal_viewer.layered_image_viewer

    @property
    def selected_record(self) -> PatientRetinalFundusRecord | None:
        return self.journal_viewer.selected_record

    @property
    def disk_mask_palette(self) -> Palette:
        return self._disk_mask_palette

    @property
    def cup_mask_palette(self) -> Palette:
        return self._cup_mask_palette

    @property
    def vessels_mask_palette(self) -> Palette:
        return self._vessels_mask_palette

    def maximize_journal_viewer(self):
        self._illustrated_journal_viewer.maximize_journal_viewer()

    def maximize_layered_image_viewer(self):
        self._illustrated_journal_viewer.maximize_layered_image_viewer()

    def show_journal_and_image_viewers(self):
        self._illustrated_journal_viewer.show_journal_and_image_viewers()

    def add_column(self, column: Type[TableColumn], column_delegate: QStyledItemDelegate = None):
        self.illustrated_journal_viewer.add_column(column, column_delegate)

    def clear_journal(self):
        self._journal.clear()

    def remove_selected_records(self):
        for record in self.journal_viewer.selected_records:
            self._journal.remove_record(record)

    def _add_cup_mask_layer_to_record(
            self,
            record: PatientRetinalFundusRecord,
            cup_mask_pixels: np.ndarray,
    ) -> ImageLayer:
        return record.layered_image.add_layer_from_image(
            FlatImage(array=cup_mask_pixels, palette=self._cup_mask_palette),
            PatientRetinalFundusRecord.CUP_MASK_LAYER_NAME)

    def _on_disk_segmented(
            self,
            record: PatientRetinalFundusRecord,
            image: FlatImage,
            disk_mask_pixels: np.ndarray,
            disk_bbox: BBox,
    ):
        disk_mask_pixels = image_converter.normalized_uint8(disk_mask_pixels)
        disk_mask_layer = record.layered_image.add_layer_from_image(
            FlatImage(array=disk_mask_pixels, palette=self._disk_mask_palette),
            PatientRetinalFundusRecord.DISK_MASK_LAYER_NAME)

        record.disk_bbox = disk_bbox

        if disk_bbox is None:
            cup_mask_pixels = np.zeros_like(disk_mask_pixels)
            cup_mask_layer = self._add_cup_mask_layer_to_record(record, cup_mask_pixels)

            # Vessels segmentation
            self._segment_vessels(record, image)
            return

        disk_region_bbox = disk_bbox.margins_added(round((disk_bbox.width + disk_bbox.height) / 2))
        disk_region_bbox.clip_to_shape(image.array.shape)

        disk_region_image_pixels = image.bboxed_pixels(disk_region_bbox)
        # data.add_layer_from_image(FlatImage(disk_region_image_pixels), name='disk-region')

        disk_region_mask_pixels = np.zeros_like(disk_mask_pixels)
        disk_region_mask_pixels[disk_region_bbox.top:disk_region_bbox.bottom, disk_region_bbox.left:disk_region_bbox.right, ...] = 255
        disk_region_mask_layer = record.layered_image.add_layer_from_image(
            FlatImage(disk_region_mask_pixels, self._disk_mask_palette),
            PatientRetinalFundusRecord.DISK_REGION_MASK_LAYER_NAME)

        # Optic cup segmentation
        self._cup_segmenter.segment_largest_connected_component_and_return_mask_with_bbox_async(
            disk_region_image_pixels,
            callback=partial(self._on_cup_segmented, record, image, disk_mask_pixels, disk_region_bbox))

    def _on_cup_segmented(
            self,
            record: PatientRetinalFundusRecord,
            image: FlatImage,
            disk_mask_pixels: np.ndarray,
            disk_bbox: BBox,
            cup_mask_pixels_on_disk_region: np.ndarray,
            cup_bbox: BBox,
    ):
        cup_mask_pixels_on_disk_region = image_converter.normalized_uint8(cup_mask_pixels_on_disk_region)
        cup_mask_pixels = np.zeros_like(disk_mask_pixels)
        cup_mask_pixels[disk_bbox.top:disk_bbox.bottom, disk_bbox.left:disk_bbox.right, ...] = \
            cup_mask_pixels_on_disk_region
        cup_mask_layer = self._add_cup_mask_layer_to_record(record, cup_mask_pixels)

        # Vessels segmentation
        self._segment_vessels(record, image)

    def _segment_vessels(self, record: PatientRetinalFundusRecord, image: FlatImage):
        self._vessels_segmenter.segment_on_splitted_into_tiles_async(
            image.array,
            callback=partial(self._on_vessels_segmented, record))

    def _on_vessels_segmented(
            self,
            record: PatientRetinalFundusRecord,
            vessels_mask_pixels: np.ndarray,
    ):
        vessels_mask_pixels = image_converter.normalized_uint8(vessels_mask_pixels)
        vessels_mask_layer = record.layered_image.add_layer_from_image(
            FlatImage(array=vessels_mask_pixels, palette=self._vessels_mask_palette),
            PatientRetinalFundusRecord.VESSELS_MASK_LAYER_NAME)

        record.calculate_params()
        if not self._columns_resized_to_contents_once:
            self.journal_viewer.resize_columns_to_contents()
            self._columns_resized_to_contents_once = True

    def visualize_retinal_fundus_data(self, data: Data):
        if not isinstance(data, LayeredImage):
            return

        first_layer = data.layers[0]
        image = first_layer.image

        # Use image name part up to the first digit as patient name
        digit_match = re.search(r'\d', image.path_name)
        if digit_match:
            patient_name = image.path_name[:digit_match.start()]
        else:
            patient_name = image.path.stem

        # Use patient of last journal record if it's patient name is the same
        patient = None
        curr_patients = self.journal.patients
        if curr_patients:
            last_patient = curr_patients[-1]
            if last_patient.name == patient_name:
                patient = last_patient
        if patient is None:
            patient = Patient(patient_name)

        record = PatientRetinalFundusRecord(patient, data)
        self.journal.add_record(record)

        self.journal_viewer.select_record(record)

        # Optic disk segmentation
        self._disk_segmenter.segment_largest_connected_component_and_return_mask_with_bbox_async(
            image.array,
            callback=partial(self._on_disk_segmented, record, image))

    def raise_journal_sub_window(self):
        self._journal_sub_window.show_normal()

        self._mdi.setActiveSubWindow(self._journal_sub_window)

        # self.journal_sub_window.raise_()
