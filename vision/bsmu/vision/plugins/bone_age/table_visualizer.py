from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Qt, QSysInfo, Signal, QSize
from PySide2.QtGui import QPalette, QPixmap, QIcon, QColor
from PySide2.QtWidgets import QTableWidget, QTableWidgetItem, QGridLayout, QAbstractItemView, QCheckBox, QWidget, \
    QHBoxLayout, QHeaderView, QLabel, QFrame, QSizePolicy, QGraphicsColorizeEffect, QPushButton, QToolButton, QVBoxLayout, QSpinBox, QSlider, QLayout

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.combo_slider import ComboSlider, SliderBar
from bsmu.vision_core.data import Data
from bsmu.vision_core.image.layered import LayeredImage

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
        self.data_visualization_manager.data_visualized.connect(self.table_visualizer.visualize_bone_age_table)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.table_visualizer.visualize_bone_age_table)


class PatientBoneAgeRecord(QObject):
    def __init__(self, image: FlatImage, male, age: float, bone_age: float):
        super().__init__()

        self.image = image
        self.male = male
        self.age = age
        self.bone_age = bone_age


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


class PatientBoneAgeJournalTable(QTableWidget):
    def __init__(self, data: PatientBoneAgeJournal = None):
        super().__init__()

        self.data = data

        self.setColumnCount(5)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setHorizontalHeaderLabels(['Name', 'Male', 'Age', 'Bone Age', 'Activation Map Visibility'])
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

        for record in self.data.records:
            self._add_record_view(record)

        self.data.record_added.connect(self._add_record_view)

    def _add_record_view(self, record: PatientBoneAgeRecord):
        print('_add_record_view')
        row = self.rowCount()
        self.insertRow(row)

        name = '' if record.image is None else record.image.path.stem
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 0, name_item)

        male_cell_widget = QWidget()
        male_check_box = QCheckBox()
        male_check_box.setChecked(record.male)
        male_cell_widget_layout = QHBoxLayout(male_cell_widget)
        male_cell_widget_layout.addWidget(male_check_box)
        male_cell_widget_layout.setAlignment(Qt.AlignCenter)
        male_cell_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.setCellWidget(row, 1, male_cell_widget)

        age_item = QTableWidgetItem(str(record.age))
        age_item.setFlags(age_item.flags() & ~Qt.ItemIsEditable)
        age_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 2, age_item)

        bone_age_item = QTableWidgetItem(str(record.bone_age))
        bone_age_item.setFlags(bone_age_item.flags() & ~Qt.ItemIsEditable)
        bone_age_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 3, bone_age_item)


        activation_map_cell_widget = QWidget()
        # Set minimum width, else widget will go beyond the cell width (if column width is small)
        activation_map_cell_widget.setMinimumWidth(1)
        # activation_map_cell_widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        # self.icon_label_2 = QLabel()
        # self.icon_label_2.setMaximumSize(QSize(24, 32))
        # self.icon_label_2.setScaledContents(True)
        self.icon_pixmap = QPixmap(r'D:\Projects\vision\vision\bsmu\vision\plugins\bone_age\no-eye.svg')  # './../eye.svg')
        # self.icon_label_2.setPixmap(self.icon_pixmap)

        self.button = QPushButton(QIcon(self.icon_pixmap), '')
        row_height = self.rowHeight(row) - self.rowSpan(row, 5)
        self.button.setIconSize(QSize(row_height, row_height))
        self.button.setStyleSheet(
            'QPushButton { '
            'border: 0px solid transparent; '
            '}'
            'QPushButton:checked { '
            'background-color: rgb(204, 228, 247); '
            '}')
        # self.button.setStyleSheet(
        #     'QPushButton:pressed { '
        #     'background-color: transparent; '
        #     '}'
        #     'QPushButton:checked { '
        #     'border: 0px solid transparent; '
        #     '}')
        self.button.setFlat(True)
        self.button.setCheckable(True)
        self.button.toggled.connect(self.change_button_icon)

        activation_map_cell_widget_layout = QHBoxLayout(activation_map_cell_widget)
        activation_map_cell_widget_layout.setContentsMargins(0, 0, 0, 0)
        activation_map_cell_widget_layout.setSpacing(0)
        # activation_map_cell_widget_layout.addWidget(self.icon_label_2)


        combo_slider = ComboSlider('Opacity', 50)
        combo_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # combo_slider.setMinimumWidth(1)
        combo_slider.setFixedHeight(row_height)
        combo_slider.setFrameStyle(QFrame.NoFrame)
        # combo_slider.setStyleSheet('ComboSlider { border: 0px solid rgb(128, 128, 128); } ')
        # combo_slider.setStyleSheet('ComboSlider { border: 0px solid rgb(128, 128, 128); border-left: 1px solid rgb(216, 216, 216); }')
        combo_slider.setStyleSheet(
            'ComboSlider { border: 0px solid rgb(128, 128, 128); border-left: 1px solid gainsboro; }')
        # combo_slider.frame_color = QColor(Qt.red)
        combo_slider.bar_color = QColor(204, 228, 247)


        activation_map_cell_widget_layout.addWidget(self.button, 0, Qt.AlignRight)

        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)

        # activation_map_cell_widget_layout.addWidget(line)
        activation_map_cell_widget_layout.addWidget(combo_slider)


        self.setCellWidget(row, 4, activation_map_cell_widget)


        # test_w = QWidget()
        # test_h_l = QHBoxLayout(test_w)
        # test_h_l.setContentsMargins(0, 0, 0, 0)
        # test_h_l.setSpacing(0)
        # test_h_l.addWidget(QSpinBox())
        # test_h_l.addWidget(QSpinBox())
        # self.setCellWidget(row, 5, test_w)

        # test_item = QTableWidgetItem('TEST')
        # self.setItem(row, 5, test_item)


    def change_button_icon(self, checked: bool):
        if checked:
            pixmap = QPixmap(r'D:\Projects\vision\vision\bsmu\vision\plugins\bone_age\eye.svg')  # './../eye.svg')
        else:
            pixmap = QPixmap(r'D:\Projects\vision\vision\bsmu\vision\plugins\bone_age\no-eye.svg')  # './../eye.svg')
        self.button.setIcon(QIcon(pixmap))


class PatientBoneAgeJournalViewer(DataViewer):
    def __init__(self, data: PatientBoneAgeJournal = None):
        super().__init__(data)

        self.table = PatientBoneAgeJournalTable(self.data)
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.table)
        self.setLayout(grid_layout)


class TestSpin(QSpinBox):
    def __init__(self):
        super().__init__()

    def focusInEvent(self, event: QFocusEvent):
        print("FFFFFFFFFFFFFFFFFFFFFFFFFFFOOOOCUS")
        super().focusInEvent(event)


class TableVisualizer(QObject):
    def __init__(self, visualization_manager: DataVisualizationManager, mdi: Mdi):
        super().__init__()

        self.visualization_manager = visualization_manager
        self.mdi = mdi

        self.journal = PatientBoneAgeJournal()
        self.journal.add_record(PatientBoneAgeRecord(None, True, 120, 125))
        self.journal.add_record(PatientBoneAgeRecord(None, False, 100, 110))
        self.journal.add_record(PatientBoneAgeRecord(None, False, 50, 51))

        self.viewer = PatientBoneAgeJournalViewer(self.journal)

        sub_window = DataViewerSubWindow(self.viewer)
        self.mdi.addSubWindow(sub_window)
        sub_window.setGeometry(0, 0, 600, 500)   #######
        sub_window.show()

        # self.icon_label = QLabel()
        # self.icon_label.setAlignment(Qt.AlignCenter)
        # self.icon_label.setFrameShape(QFrame.Box)
        # self.icon_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.icon_label.setBackgroundRole(QPalette.Base)
        # self.icon_label.setAutoFillBackground(True)
        # self.icon_label.setMinimumSize(132, 132)
        # self.icon_pixmap = QPixmap(r'D:\Projects\vision\vision\bsmu\vision\plugins\bone_age\eye.svg') #'./../eye.svg')
        # self.icon_label.setPixmap(self.icon_pixmap)
        # self.icon_label.show()
        #
        # self.icon_label_2 = QLabel()
        # self.icon_label_2.setPixmap(self.icon_pixmap)
        # self.icon_label_2.show()

        self.test_widget = QWidget()
        l = QVBoxLayout(self.test_widget)

        test_w = QFrame()
        test_w.setFrameStyle(QFrame.Box)
        test_h_box = QHBoxLayout(test_w)
        test_h_box.addWidget(QLabel('TEST'))
        # test_h_box.addWidget(QPushButton('PUSH'))
        test_h_box.addWidget(TestSpin())

        spin = QSpinBox()
        # spin.setFocusPolicy(Qt.TabFocus)

        self.combo_slider = ComboSlider('Opacity', 50)

        l.addWidget(test_w)
        l.addWidget(self.combo_slider)
        l.addWidget(spin)
        l.addWidget(QSlider(Qt.Horizontal))

        self.test_widget.show()
        print('HHH', spin.height(), self.combo_slider.height())

        # self.combo_slider.show()
        # self.slider_bar = SliderBar()
        # self.slider_bar.show()

    def visualize_bone_age_table(self, data: Data, data_viewer_sub_windows: DataViewerSubWindow):
        print('visualize_bone_age_table', type(data))

        if isinstance(data, LayeredImage):
            first_layer = data.layers[0]

            self.journal.add_record(PatientBoneAgeRecord(first_layer.image, True, 120, 125))
