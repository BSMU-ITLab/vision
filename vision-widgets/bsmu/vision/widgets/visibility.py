from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QPixmap, QIcon, QColor
from PySide2.QtWidgets import QWidget, QPushButton, QHBoxLayout, QSizePolicy, QFrame

from bsmu.vision.widgets.combo_slider import ComboSlider


class VisibilityToggleButton(QPushButton):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

##        row_height = self.rowHeight(row) - self.rowSpan(row, 5)
##        self.button.setIconSize(QSize(row_height, row_height))
        self.setStyleSheet(
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
        self.setFlat(True)
        self.setCheckable(True)
        self.toggled.connect(self._on_button_toggled)

        self._update_icon()

    def _on_button_toggled(self, checked):
        self._update_icon()

    def _update_icon(self):
        if self.isChecked():
            pixmap = QPixmap(r'D:\Projects\vision\vision\bsmu\vision\plugins\bone_age\eye.svg')  # './../eye.svg')
        else:
            pixmap = QPixmap(r'D:\Projects\vision\vision\bsmu\vision\plugins\bone_age\no-eye.svg')  # './../eye.svg')
        self.setIcon(QIcon(pixmap))


class VisibilityWidget(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        # Set minimum width, else widget will go beyond the cell width (if column width is small)
        self.setMinimumWidth(1)
        # activation_map_cell_widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        # self.icon_label_2 = QLabel()
        # self.icon_label_2.setMaximumSize(QSize(24, 32))
        # self.icon_label_2.setScaledContents(True)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        # h_layout.addWidget(self.icon_label_2)

        combo_slider = ComboSlider('Opacity', 50)
        combo_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # combo_slider.setMinimumWidth(1)
##        combo_slider.setFixedHeight(row_height)
        combo_slider.setFrameStyle(QFrame.NoFrame)
        # combo_slider.setStyleSheet('ComboSlider { border: 0px solid rgb(128, 128, 128); } ')
        # combo_slider.setStyleSheet('ComboSlider { border: 0px solid rgb(128, 128, 128); border-left: 1px solid rgb(216, 216, 216); }')
        combo_slider.setStyleSheet(
            'ComboSlider { border: 0px solid rgb(128, 128, 128); border-left: 1px solid gainsboro; }')
        # combo_slider.frame_color = QColor(Qt.red)
        combo_slider.bar_color = QColor(204, 228, 247)

        h_layout.addWidget(VisibilityToggleButton(), 0, Qt.AlignRight)

        # line = QFrame()
        # line.setFrameShape(QFrame.VLine)
        # line.setFrameShadow(QFrame.Sunken)

        # h_layout.addWidget(line)
        h_layout.addWidget(combo_slider)
