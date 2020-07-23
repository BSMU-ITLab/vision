from __future__ import annotations

from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import List, Type
from typing import TYPE_CHECKING

import numpy as np
import skimage.transform
from PySide2.QtCore import QObject, Qt, QSysInfo, Signal
from PySide2.QtWidgets import QTableWidget, QTableWidgetItem, QGridLayout, QAbstractItemView, QHeaderView, QMenu, \
    QActionGroup

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.bone_age.predictor import Predictor
from bsmu.vision.widgets.gender import GenderWidget
from bsmu.vision.widgets.layer_visibility import LayerVisibilityWidget
from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision_core.converters import color as color_converter
from bsmu.vision_core.converters import image as image_converter
from bsmu.vision_core.data import Data
from bsmu.vision_core.image.base import FlatImage
from bsmu.vision_core.image.layered import LayeredImage
from bsmu.vision_core.transfer_functions.color import ColorTransferFunction

if TYPE_CHECKING:
    from bsmu.vision.app import App


class TableVisualizerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager
        mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi
        self.table_visualizer = TableVisualizer(self.data_visualization_manager, mdi)

    def _enable(self):
        self.data_visualization_manager.data_visualized.connect(self.table_visualizer.visualize_bone_age_data)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.table_visualizer.visualize_bone_age_data)


class PatientBoneAgeRecord(QObject):
    male_changed = Signal(bool)
    bone_age_changed = Signal(float)

    def __init__(self, image: FlatImage, male: bool, age: float, bone_age: float):
        super().__init__()

        self.image = image
        self._male = male
        self.age = age
        self._bone_age = bone_age  # in months

    @property
    def male(self) -> bool:
        return self._male

    @male.setter
    def male(self, value: bool):
        if self._male != value:
            self._male = value
            self.male_changed.emit(self._male)

    @property
    def bone_age(self) -> float:
        return self._bone_age

    @bone_age.setter
    def bone_age(self, value: float):
        if self._bone_age != value:
            self._bone_age = value
            self.bone_age_changed.emit(self._bone_age)


class PatientBoneAgeJournal(Data):
    record_added = Signal(PatientBoneAgeRecord)

    def __init__(self):
        super().__init__()

        self.records = []

    def add_record(self, record: PatientBoneAgeRecord):
        self.records.append(record)
        self.record_added.emit(record)


class PatientBoneAgeJournalTableRecord(QObject):
    def __init__(self, record: PatientBoneAgeRecord):
        super().__init__()

        self.record = record


class BoneAgeFormat(ABC):
    NAME = ''
    ABBR = ''

    bone_age_decimals = 2

    @classmethod
    @abstractmethod
    def format(cls, bone_age: float) -> str:
        pass


class MonthsBoneAgeFormat(BoneAgeFormat):
    NAME = 'Months'
    ABBR = 'M'

    @classmethod
    def format(cls, bone_age: float) -> str:
        return f'{bone_age:.{cls.bone_age_decimals}f}'


class YearsMonthsBoneAgeFormat(BoneAgeFormat):
    NAME = 'Years / Months'
    ABBR = 'Y / M'

    @classmethod
    def format(cls, bone_age: float) -> str:
        years, months = divmod(bone_age, 12)
        return f'{int(years)} / {months:.{cls.bone_age_decimals}f}'


class TableColumn:
    TITLE = ''


class TableNameColumn(TableColumn):
    TITLE = 'Name'


class TableGenderColumn(TableColumn):
    TITLE = 'Gender'


class TableAgeColumn(TableColumn):
    TITLE = 'Age'


class TableBoneAgeColumn(TableColumn):
    TITLE = 'Bone Age'


class TableDenseNetBoneAgeColumn(TableBoneAgeColumn):
    TITLE = 'DenseNet\nBone Age'


class TableActivationMapColumn(TableColumn):
    TITLE = 'Activation Map Visibility'


class PatientBoneAgeJournalTable(QTableWidget):
    record_selected = Signal(PatientBoneAgeRecord)

    RECORD_REF_ROLE = Qt.UserRole

    def __init__(self, data: PatientBoneAgeJournal = None):
        super().__init__()

        self.data = data

        self._records_rows = {}  # {PatientBoneAgeRecord: row}

        self._bone_age_formats = [MonthsBoneAgeFormat, YearsMonthsBoneAgeFormat]
        self._bone_age_format = YearsMonthsBoneAgeFormat

        self._columns = [TableNameColumn, TableGenderColumn, TableAgeColumn, TableDenseNetBoneAgeColumn,
                         TableActivationMapColumn]
        self._columns_numbers = {column: number for number, column in enumerate(self._columns)}
        self._bone_age_columns = {column for column in self._columns if issubclass(column, TableBoneAgeColumn)}
        self._bone_age_column_numbers = {self._columns_numbers[column] for column in self._bone_age_columns}

        self.setColumnCount(len(self._columns))
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        horizontal_header_labels = [self._create_column_title(column) for column in self._columns]
        self.setHorizontalHeaderLabels(horizontal_header_labels)
        # self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        if QSysInfo.windowsVersion() == QSysInfo.WV_WINDOWS10:
            # Add border under the header
            self.setStyleSheet(
                'QHeaderView::section { '
                'border-top: 0px solid #D8D8D8; '
                'border-left: 0px solid #D8D8D8; '
                'border-right: 1px solid #D8D8D8; '
                'border-bottom: 1px solid #D8D8D8; '
                '}'
                'QTableCornerButton::section { '
                'border-top: 0px solid #D8D8D8; '
                'border-left: 0px solid #D8D8D8; '
                'border-right: 1px solid #D8D8D8; '
                'border-bottom: 1px solid #D8D8D8; '
                '}')
            self.verticalHeader().setStyleSheet('QHeaderView::section { padding-left: 4px; }')

        self.itemSelectionChanged.connect(self._on_item_selection_changed)

        for record in self.data.records:
            self._add_record_view(record)

        self.data.record_added.connect(self._add_record_view)

        # Configure a custom context menu for the horizontal header
        self.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self._display_header_context_menu)

    def column_number(self, column: Type[TableColumn]) -> int:
        return self._columns_numbers[column]

    @property
    def bone_age_format(self) -> Type[BoneAgeFormat]:
        return self._bone_age_format

    @bone_age_format.setter
    def bone_age_format(self, value: Type[BoneAgeFormat]):
        if self._bone_age_format != value:
            self._bone_age_format = value
            self._update_bone_age_column_headers()
            self._update_bone_age_column_contents()

    def add_record_activation_map_visibility_widget(
            self, record: PatientBoneAgeRecord, layer_visibility_widget: LayerVisibilityWidget):
        row = self._records_rows[record]
        self.setCellWidget(row, self.column_number(TableActivationMapColumn), layer_visibility_widget)

    def _row_record(self, row: int) -> PatientBoneAgeRecord:
        return self.item(row, self.column_number(TableNameColumn)).data(self.RECORD_REF_ROLE)

    def _create_column_title(self, column: Type[TableColumn]) -> str:
        column_title = column.TITLE
        if issubclass(column, TableBoneAgeColumn):
            column_title += f' ({self._bone_age_format.ABBR})'
        return column_title

    def _add_record_view(self, record: PatientBoneAgeRecord):
        row = self.rowCount()
        self.insertRow(row)
        self._records_rows[record] = row

        name = '' if record.image is None else record.image.path.stem
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setTextAlignment(Qt.AlignCenter)
        # Add the |record| reference to the |name_item|
        name_item.setData(self.RECORD_REF_ROLE, record)
        self.setItem(row, self.column_number(TableNameColumn), name_item)

        gender_widget = GenderWidget(embedded=True)
        gender_widget.man = record.male
        gender_widget.gender_changed.connect(partial(self._on_gender_changed, record))
        record.male_changed.connect(partial(self._on_record_male_changed, gender_widget))
        self.setCellWidget(row, self.column_number(TableGenderColumn), gender_widget)

        age_item = QTableWidgetItem(str(record.age))
        age_item.setFlags(age_item.flags() & ~Qt.ItemIsEditable)
        age_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, self.column_number(TableAgeColumn), age_item)

        bone_age_item = QTableWidgetItem()
        bone_age_item.setFlags(bone_age_item.flags() & ~Qt.ItemIsEditable)
        bone_age_item.setTextAlignment(Qt.AlignCenter)
        self._set_bone_age_to_table_item(bone_age_item, record.bone_age)
        record.bone_age_changed.connect(partial(self._set_bone_age_to_table_item, bone_age_item))
        self.setItem(row, self.column_number(TableDenseNetBoneAgeColumn), bone_age_item)

    def _on_item_selection_changed(self):
        selected_ranges = self.selectedRanges()
        if selected_ranges:
            bottom_selected_row = selected_ranges[-1].bottomRow()
            selected_record = self._row_record(bottom_selected_row)
            self.record_selected.emit(selected_record)

    def _on_gender_changed(self, record: PatientBoneAgeRecord, man: bool):
        record.male = man

    def _on_record_male_changed(self, gender_widget: GenderWidget, male: bool):
        gender_widget.man = male

    def _set_bone_age_to_table_item(self, bone_age_table_item: QTableWidgetItem, bone_age: float):
        bone_age_table_item.setText(self._bone_age_format.format(bone_age))

    def _display_header_context_menu(self, point: QPoint):
        column_number = self.horizontalHeader().logicalIndexAt(point)
        if column_number in self._bone_age_column_numbers:
            self._display_bone_age_column_context_menu(point)

    def _display_bone_age_column_context_menu(self, point: QPoint):
        menu = QMenu(self)
        format_menu = menu.addMenu('Format')
        format_action_group = QActionGroup(self)
        for bone_age_format in self._bone_age_formats:
            format_action = format_menu.addAction(bone_age_format.NAME)
            format_action.bone_age_format = bone_age_format
            format_action.setCheckable(True)

            if self._bone_age_format == bone_age_format:
                format_action.setChecked(True)

            format_action_group.addAction(format_action)

        triggered_action = menu.exec_(self.horizontalHeader().viewport().mapToGlobal(point))
        if triggered_action:
            self.bone_age_format = triggered_action.bone_age_format

    def _update_bone_age_column_headers(self):
        for bone_age_column in self._bone_age_columns:
            header_label = self._create_column_title(bone_age_column)
            bone_age_column_number = self._columns_numbers[bone_age_column]
            self.horizontalHeaderItem(bone_age_column_number).setText(header_label)

    def _update_bone_age_column_contents(self):
        for row in range(self.rowCount()):
            record = self._row_record(row)
            bone_age = record.bone_age
            for bone_age_column_number in self._bone_age_column_numbers:
                self._set_bone_age_to_table_item(self.item(row, bone_age_column_number), bone_age)


class PatientBoneAgeJournalViewer(DataViewer):
    record_selected = Signal(PatientBoneAgeRecord)

    def __init__(self, data: PatientBoneAgeJournal = None):
        super().__init__(data)

        self.table = PatientBoneAgeJournalTable(self.data)
        self.table.record_selected.connect(self.record_selected)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.table)
        self.setLayout(grid_layout)

    def add_record_activation_map_visibility_widget(
            self, record: PatientBoneAgeRecord, layer_visibility_widget: LayerVisibilityWidget):
        self.table.add_record_activation_map_visibility_widget(record, layer_visibility_widget)


class TableVisualizer(QObject):
    ACTIVATION_MAP_LAYER_NAME = 'Activation Map'

    def __init__(self, visualization_manager: DataVisualizationManager, mdi: Mdi):
        super().__init__()

        self.predictor = Predictor(Path(r'D:\Temp\TempBoneAgeModels\DenseNet_withInputShape___weighted.pb'))
        # self.predictor.predict()

        self.visualization_manager = visualization_manager
        self.mdi = mdi

        self.journal = PatientBoneAgeJournal()
        self.journal_viewer = PatientBoneAgeJournalViewer(self.journal)
        self.journal_viewer.record_selected.connect(self._on_journal_record_selected)

        self.records_image_sub_windows = {}

        sub_window = DataViewerSubWindow(self.journal_viewer)
        sub_window.layout_anchors = np.array([[0, 0], [0.5, 1]])
        self.mdi.addSubWindow(sub_window)

    def visualize_bone_age_data(self, data: Data, data_viewer_sub_windows: List[DataViewerSubWindow]):
        print('visualize_bone_age_data', type(data))

        if isinstance(data, LayeredImage):
            first_layer = data.layers[0]

            default_gender_is_male = True
            image = first_layer.image
            predicted_bone_age, activation_map = self.predictor.predict(image, default_gender_is_male)
            record = PatientBoneAgeRecord(image, default_gender_is_male, 120, predicted_bone_age)
            record.male_changed.connect(partial(self._on_record_male_changed, record))
            self.journal.add_record(record)

            self.records_image_sub_windows[record] = data_viewer_sub_windows

            for sub_window in data_viewer_sub_windows:
                sub_window.layout_anchors = np.array([[0.5, 0], [1, 1]])
                sub_window.lay_out_to_anchors()

            # Add a layer with the activation map
            activation_map = skimage.transform.resize(activation_map, image.array.shape[:2], order=3)
            activation_map = image_converter.normalized_uint8(activation_map)

            activation_map_color_transfer_function = ColorTransferFunction.default_jet()
            activation_map_color_transfer_function.points[0].color_array = np.array([0, 0, 255, 0])
            activation_map_palette = color_converter.color_transfer_function_to_palette(
                activation_map_color_transfer_function)

            activation_map_layer = data.add_layer_from_image(
                FlatImage(array=activation_map, palette=activation_map_palette), name=self.ACTIVATION_MAP_LAYER_NAME)

            activation_map_layer_views = []
            for sub_window in data_viewer_sub_windows:
                activation_map_layer_view = sub_window.viewer.layer_view_by_model(activation_map_layer)
                activation_map_layer_view.opacity = 0.5
                activation_map_layer_views.append(activation_map_layer_view)
            activation_map_visibility_widget = LayerVisibilityWidget(activation_map_layer_views, embedded=True)
            # activation_map_visibility_widget.slider_bar_color = QColor(240, 206, 164)
            # activation_map_visibility_widget.toggle_button_checked_color = QColor(240, 206, 164)
            self.journal_viewer.add_record_activation_map_visibility_widget(
                record, activation_map_visibility_widget)

    def _on_record_male_changed(self, record: PatientBoneAgeRecord, male: bool):
        self._update_record_bone_age(record)

    def _update_record_bone_age(self, record: PatientBoneAgeRecord):
        record.bone_age, _ = self.predictor.predict(record.image, record.male, calculate_activation_map=False)

    def _on_journal_record_selected(self, record: PatientBoneAgeRecord):
        image_sub_windows = self.records_image_sub_windows.get(record, [])
        for image_sub_window in image_sub_windows:
            image_sub_window.raise_()
