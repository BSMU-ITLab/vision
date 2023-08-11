from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QObject, Signal, QMetaObject, QRectF, QPointF, QLineF, QMarginsF, QTimer
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import QWidget, QGridLayout, QFrame, QGraphicsItem, QStyle, QGroupBox, QFormLayout, QComboBox, \
    QSpinBox, QHBoxLayout

from bsmu.retinal_fundus.plugins.table_visualizer import PatientRetinalFundusRecord
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer

if TYPE_CHECKING:
    from typing import Tuple, Sequence

    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.widgets.viewers.image.layered.flat import ImageLayerView, ImageViewerSettings
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer
    from bsmu.vision.plugins.viewers.image.settings import ImageViewerSettingsPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class RetinalFundusDiskRegionSelectorPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
        'image_viewer_settings_plugin': 'bsmu.vision.plugins.viewers.image.settings.ImageViewerSettingsPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
            image_viewer_settings_plugin: ImageViewerSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._image_viewer_settings_plugin = image_viewer_settings_plugin
        self._image_viewer_settings: ImageViewerSettings | None = None

        self._disk_region_selector: RetinalFundusDiskRegionSelector | None = None

    @property
    def disk_region_selector(self) -> RetinalFundusDiskRegionSelector | None:
        return self._disk_region_selector

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._table_visualizer = self._table_visualizer_plugin.table_visualizer
        self._image_viewer_settings = self._image_viewer_settings_plugin.settings

        self._disk_region_selector = RetinalFundusDiskRegionSelector(
            self._table_visualizer, self._image_viewer_settings)
        self._table_visualizer.detailed_info_viewer.add_widget(self._disk_region_selector)

        # histograms_menu = self._main_window.menu(HistogramsMenu)
        # neuroretinal_rim_menu = histograms_menu.addMenu('Neuroretinal Rim')
        # rgb_neuroretinal_rim_histogram_action = neuroretinal_rim_menu.addAction('RGB', None, Qt.CTRL + Qt.Key_R)
        # hsv_neuroretinal_rim_histogram_action = neuroretinal_rim_menu.addAction('HSV', None, Qt.CTRL + Qt.Key_H)
        #
        # rgb_neuroretinal_rim_histogram_action.setCheckable(True)
        # hsv_neuroretinal_rim_histogram_action.setCheckable(True)
        #
        # rgb_neuroretinal_rim_histogram_action.triggered.connect(
        #     self._rgb_histogram_visualizer.on_visualize_neuroretinal_rim_histogram_toggled)
        # hsv_neuroretinal_rim_histogram_action.triggered.connect(
        #     self._hsv_histogram_visualizer.on_visualize_neuroretinal_rim_histogram_toggled)

    def _disable(self):
        self._disk_region_selector = None

        self._table_visualizer = None
        self._main_window = None

        raise NotImplementedError


@dataclass
class Sector:
    start_angle: float
    end_angle: float
    name: str = ''


@dataclass
class SectorsPreset:
    name: str = ''
    quantity: int = 4
    rotation: int = 0
    sector_names: Sequence[str] = None

    def sectors(self) -> list[Sector]:
        assert self.sector_names is None or len(self.sector_names) == self.quantity, 'Incorrect number of sector names'

        sectors = []
        angle = 360 / self.quantity
        for i in range(self.quantity):
            start_angle = i * angle + self.rotation
            end_angle = start_angle + angle
            name = '' if self.sector_names is None else self.sector_names[i]
            sector = Sector(start_angle, end_angle, name)
            sectors.append(sector)
        return sectors


class RetinalFundusDiskRegionSelector(QWidget):
    DISK_LAYER_NAME = 'disk'
    SELECTED_SECTORS_LAYER_NAME = 'selected-sectors'

    ISNT_SECTORS_PRESET = SectorsPreset('ISNT', 4, 45, ('Nasal', 'Inferior', 'Temporal', 'Superior'))
    CLOCK_SECTORS_PRESET = SectorsPreset('Clock', 12)

    selected_regions_changed = Signal()

    def __init__(self, table_visualizer: RetinalFundusTableVisualizer, image_viewer_settings: ImageViewerSettings,):
        super().__init__()

        self._table_visualizer = table_visualizer

        self._disk_viewer = LayeredFlatImageViewer(LayeredImage(), image_viewer_settings)
        self._disk_viewer.graphics_view.setRenderHint(QPainter.Antialiasing)
        self._disk_viewer.graphics_view.setFrameShape(QFrame.NoFrame)

        self._record_disk_bbox_changed_connection = QMetaObject.Connection()
        self._record_image_layer_added_connection = QMetaObject.Connection()

        self._scene_selection_changed_connection = QMetaObject.Connection()
        self._selected_sectors_opacity_timer_timeout_connection = QMetaObject.Connection()

        self._processed_record: PatientRetinalFundusRecord | None = None
        self._is_visualization_started: bool
        self.is_visualization_started = False
        self._table_visualizer.journal_viewer.record_selected.connect(self._on_journal_record_selected)

        self._disk_region_image_layer: ImageLayer | None = None
        self._disk_region_image_pixels: np.ndarray | None = None
        self._disk_mask_region_image_pixels: np.ndarray | None = None

        self._selected_sectors_mask_layer: ImageLayer | None = None
        self._selected_sectors_layer_view: ImageLayerView | None = None
        self._selected_sectors_mask_palette = Palette.default_binary(255, [102, 183, 255])
        self._selected_sectors_opacity_timer = QTimer()
        self._selected_sectors_opacity_timer.setInterval(20)
        self._selected_sectors_max_opacity = 0.75

        self._disk_region: BBox | None = None
        self._disk_center: QPointF | None = None
        self._disk_region_rect: QRectF | None = None

        self._sectors_recreation_enabled: bool = True
        self._curr_sectors_config: SectorsPreset | None = None
        self._sector_items = []

        self._sectors_preset_combo_box: QComboBox | None = None
        self._sectors_quantity_spin_box: QSpinBox | None = None
        self._sectors_rotation_spin_box: QSpinBox | None = None

        settings_ui_grid_layout = QGridLayout()
        settings_ui_grid_layout.addWidget(self._create_settings_ui())
        settings_ui_grid_layout.setContentsMargins(
            self.style().pixelMetric(QStyle.PM_LayoutLeftMargin),
            self.style().pixelMetric(QStyle.PM_LayoutTopMargin),
            self.style().pixelMetric(QStyle.PM_LayoutRightMargin),
            self.style().pixelMetric(QStyle.PM_LayoutBottomMargin))

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._disk_viewer)
        layout.addLayout(settings_ui_grid_layout)
        self.setLayout(layout)

    @property
    def processed_record(self) -> PatientRetinalFundusRecord | None:
        return self._processed_record

    @processed_record.setter
    def processed_record(self, value: PatientRetinalFundusRecord | None):
        if self._processed_record != value:
            self._stop_record_processing()
            self._processed_record = value
            self._start_record_processing()

    @property
    def is_visualization_started(self) -> bool:
        return self._is_visualization_started

    @is_visualization_started.setter
    def is_visualization_started(self, value: bool):
        self._is_visualization_started = value
        self.setEnabled(self._is_visualization_started)

    @property
    def disk_region(self) -> BBox | None:
        return self._disk_region

    @property
    def selected_sectors_mask(self) -> np.ndarray | None:
        return self._selected_sectors_mask_layer.image_pixels

    def _start_record_processing(self):
        if self.processed_record is None:
            return

        self._record_disk_bbox_changed_connection = \
            self.processed_record.disk_bbox_changed.connect(self._on_record_disk_bbox_changed)
        self._record_image_layer_added_connection = \
            self._processed_record.layered_image.layer_added.connect(self._on_record_image_layer_added)

        self._start_visualization()

    def _stop_record_processing(self):
        if self.processed_record is None:
            return

        self._stop_visualization()

        QObject.disconnect(self._record_disk_bbox_changed_connection)
        QObject.disconnect(self._record_image_layer_added_connection)

    def _on_record_disk_bbox_changed(self, disk_bbox: BBox):
        self._restart_visualization()

    def _on_record_image_layer_added(self, image_layer: ImageLayer):
        self._start_visualization()

    def _create_settings_ui(self) -> QWidget:
        self._sectors_quantity_spin_box = QSpinBox()
        self._sectors_quantity_spin_box.setRange(2, 36)
        self._sectors_quantity_spin_box.valueChanged.connect(self._on_sectors_quantity_changed)

        self._sectors_rotation_spin_box = QSpinBox()
        self._sectors_rotation_spin_box.setRange(0, 360)
        self._sectors_rotation_spin_box.valueChanged.connect(self._on_sectors_rotation_changed)

        self._sectors_preset_combo_box = QComboBox()
        self._sectors_preset_combo_box.currentIndexChanged.connect(self._on_sectors_preset_changed)
        self._sectors_preset_combo_box.addItem(self.ISNT_SECTORS_PRESET.name, self.ISNT_SECTORS_PRESET)
        self._sectors_preset_combo_box.addItem(self.CLOCK_SECTORS_PRESET.name,  self.CLOCK_SECTORS_PRESET)

        form_layout = QFormLayout()
        form_layout.addRow('Preset:', self._sectors_preset_combo_box)
        form_layout.addRow('Quantity:', self._sectors_quantity_spin_box)
        form_layout.addRow('Rotation:', self._sectors_rotation_spin_box)

        sectors_settings_group_box = QGroupBox('Sectors')
        sectors_settings_group_box.setLayout(form_layout)
        return sectors_settings_group_box

    def _on_sectors_preset_changed(self, index: int):
        self._sectors_recreation_enabled = False

        sectors_preset = self._sectors_preset_combo_box.currentData()
        self._sectors_quantity_spin_box.setValue(sectors_preset.quantity)
        self._sectors_rotation_spin_box.setValue(sectors_preset.rotation)

        self._sectors_recreation_enabled = True
        self._recreate_sector_items()

    def _on_sectors_quantity_changed(self, i: int):
        self._recreate_sector_items()

    def _on_sectors_rotation_changed(self, i: int):
        self._recreate_sector_items()

    def _ui_sectors_config(self) -> SectorsPreset:
        return SectorsPreset(
            quantity=self._sectors_quantity_spin_box.value(), rotation=self._sectors_rotation_spin_box.value())

    def _recreate_sector_items(self):
        if not self._sectors_recreation_enabled:
            return

        sectors_config = self._ui_sectors_config()
        if self._curr_sectors_config == sectors_config:
            return

        self._remove_sector_items()
        self._create_sector_items(sectors_config)

    def _remove_sector_items(self):
        for sector_item in self._sector_items:
            self._disk_viewer.remove_graphics_item(sector_item)

        self._sector_items.clear()

        self._curr_sectors_config = None

    def _create_sector_items(self, sectors_config: SectorsPreset):
        if self._disk_region_rect is None:
            return

        sectors = sectors_config.sectors()
        for sector in sectors:
            sector_item = GraphicsSectorItem(
                self._disk_center, sector.start_angle, sector.end_angle, self._disk_region_rect)
            self._disk_viewer.add_graphics_item(sector_item)

            self._sector_items.append(sector_item)

        self._curr_sectors_config = sectors_config

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        self.processed_record = record

    def _restart_visualization(self):
        if self._is_visualization_started:
            self._stop_visualization()
        self._start_visualization()

    def _start_visualization(self):
        if self._is_visualization_started:
            return

        if self.processed_record.disk_bbox is None or self.processed_record.disk_mask is None:
            return

        self._disk_region = self.processed_record.disk_bbox.scaled(1.2, 1.2)
        self._disk_region.clip_to_shape(self.processed_record.image.shape)

        self._disk_region_image_pixels = self.processed_record.image.bboxed_pixels(self._disk_region)
        self._disk_region_image_layer = self._disk_viewer.data.add_layer_or_modify_pixels(
            self.DISK_LAYER_NAME, self._disk_region_image_pixels, FlatImage)

        self._disk_mask_region_image_pixels = self.processed_record.disk_mask.bboxed_pixels(self._disk_region)

        selected_sectors_mask_pixels = np.copy(self._disk_mask_region_image_pixels)
        self._selected_sectors_mask_layer = self._disk_viewer.data.add_layer_or_modify_pixels(
            self.SELECTED_SECTORS_LAYER_NAME,
            selected_sectors_mask_pixels,
            FlatImage,
            self._selected_sectors_mask_palette)
        self._selected_sectors_layer_view = self._disk_viewer.layer_view_by_model(self._selected_sectors_mask_layer)

        self._disk_viewer.fit_image_in()

        self._disk_center = QPointF(self._disk_region.width, self._disk_region.height) / 2
        self._disk_region_rect = QRectF(0, 0, self._disk_region.width, self._disk_region.height)

        self._create_sector_items(self._ui_sectors_config())

        self._scene_selection_changed_connection = \
            self._disk_viewer.graphics_scene.selectionChanged.connect(self._on_scene_selection_changed)

        self._selected_sectors_opacity_timer_timeout_connection = \
            self._selected_sectors_opacity_timer.timeout.connect(self._change_selected_sectors_opacity)
        self._selected_sectors_opacity_timer.start()

        self.is_visualization_started = True

    def _stop_visualization(self):
        self._selected_sectors_opacity_timer.stop()
        QObject.disconnect(self._selected_sectors_opacity_timer_timeout_connection)
        QObject.disconnect(self._scene_selection_changed_connection)

        self._remove_sector_items()

        if self._disk_region_image_layer is not None:
            self._disk_region_image_layer.image = None
            self._disk_region_image_layer = None

        if self._selected_sectors_mask_layer is not None:
            self._selected_sectors_mask_layer.image = None
            self._selected_sectors_mask_layer = None

        self._disk_region_image_pixels = None
        self._disk_mask_region_image_pixels = None
        self._selected_sectors_layer_view = None

        self._disk_region = None
        self._disk_center = None
        self._disk_region_rect = None

        self.is_visualization_started = False

    def _on_scene_selection_changed(self):
        self._selected_sectors_mask_layer.image_pixels.fill(0)

        at_least_one_sector_is_selected = False
        for sector in self._disk_viewer.graphics_scene.selectedItems():
            if not isinstance(sector, GraphicsSectorItem):
                continue

            at_least_one_sector_is_selected = True
            curr_sector_mask = sector_mask(
                self._disk_region_image_pixels.shape[:2],
                (round(self._disk_center.y()), round(self._disk_center.x())),
                (sector.start_angle, sector.end_angle))
            self._selected_sectors_mask_layer.image_pixels[curr_sector_mask] = 255
        if at_least_one_sector_is_selected:
            self._selected_sectors_mask_layer.image_pixels[self._disk_mask_region_image_pixels == 0] = 0
        else:
            self._selected_sectors_mask_layer.image.pixels = np.copy(self._disk_mask_region_image_pixels)
        self._selected_sectors_mask_layer.image.emit_pixels_modified()

        self.selected_regions_changed.emit()

    def _change_selected_sectors_opacity(self):
        # Generate periodic values in range [0; |self._selected_sectors_max_opacity|]
        self._selected_sectors_layer_view.opacity = \
            abs(math.sin(1.5 * time.time()) * self._selected_sectors_max_opacity)


class GraphicsSectorItem(QGraphicsItem):
    def __init__(
            self,
            center: QPointF,
            start_angle: float,
            end_angle: float,
            region_rect: QRectF,
            parent: QGraphicsItem = None,
    ):
        super().__init__(parent)

        self._center = center
        self._start_angle = start_angle
        self._end_angle = end_angle
        self._region_rect = region_rect

        self._bbox_lines = [
            QLineF(self._region_rect.topLeft(), self._region_rect.topRight()),
            QLineF(self._region_rect.topRight(), self._region_rect.bottomRight()),
            QLineF(self._region_rect.bottomRight(), self._region_rect.bottomLeft()),
            QLineF(self._region_rect.bottomLeft(), self._region_rect.topLeft()),
        ]

        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self._pen_max_width = 2
        self._selected_pen = QPen(QColor(67, 114, 142), self._pen_max_width, Qt.SolidLine, Qt.RoundCap)
        self._selected_brush = QBrush(QColor(67, 114, 142, 63))
        self._unselected_pen = QPen(QColor(67, 114, 142), 1, Qt.DotLine)

        self._region_rect_diagonal_len = \
            math.sqrt(pow(self._region_rect.width(), 2) + pow(self._region_rect.height(), 2))
        self._start_point, start_bbox_line = self._calculate_angle_point_on_bbox_line(self._start_angle)
        self._end_point, end_bbox_line = self._calculate_angle_point_on_bbox_line(self._end_angle)

        self._stroke_path = QPainterPath()
        self._stroke_path.moveTo(self._center)
        self._stroke_path.lineTo(self._start_point)
        self._stroke_path.moveTo(self._center)
        self._stroke_path.lineTo(self._end_point)

        self._fill_path = QPainterPath()
        self._fill_path.moveTo(self._center)
        self._fill_path.lineTo(self._start_point)
        start_bbox_line_index = self._bbox_lines.index(start_bbox_line)
        bbox_lines_len = len(self._bbox_lines)
        for i in range(bbox_lines_len):
            curr_bbox_line = self._bbox_lines[(start_bbox_line_index + i) % bbox_lines_len]
            if curr_bbox_line.p2() == end_bbox_line.p2():
                break
            self._fill_path.lineTo(curr_bbox_line.p2())
        self._fill_path.lineTo(self._end_point)
        self._fill_path.closeSubpath()

    @property
    def start_angle(self) -> float:
        return self._start_angle

    @property
    def end_angle(self) -> float:
        return self._end_angle

    def boundingRect(self) -> QRectF:
        return self._fill_path.boundingRect().marginsAdded(
            QMarginsF(self._pen_max_width, self._pen_max_width, self._pen_max_width, self._pen_max_width))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.save()

        if option.state & QStyle.State_Selected:
            painter.setPen(self._selected_pen)
            painter.setBrush(self._selected_brush)
            painter.drawPath(self._fill_path)
        else:
            painter.setPen(self._unselected_pen)
            painter.drawPath(self._stroke_path)

        painter.restore()

    def shape(self) -> QPainterPath:
        return self._fill_path

    def _calculate_angle_point_on_bbox_line(self, angle: float) -> Tuple[QPointF, QLineF]:
        x = self._region_rect_diagonal_len * math.sin(math.radians(angle))
        y = self._region_rect_diagonal_len * math.cos(math.radians(angle))
        # Use |-y| because Y-axis is pointing down
        return self._bbox_intersection_with_line(QLineF(self._center, self._center + QPointF(x, -y)))

    def _bbox_intersection_with_line(self, line: QLineF) -> Tuple[QPointF, QLineF]:
        for bbox_line in self._bbox_lines:
            intersection_type, intersection_point = bbox_line.intersects(line)
            if intersection_type == QLineF.BoundedIntersection:
                return intersection_point, bbox_line


def sector_mask(
        rect_shape: Sequence,
        center: Sequence,
        angle_range: Sequence,
        rotate: float = 270,
) -> np.ndarray:
    """
    See: https://stackoverflow.com/questions/18352973/mask-a-circular-sector-in-a-numpy-array
         https://stackoverflow.com/a/18354475/3605259
    Returns a boolean mask for a sector within a rectangle.
    The start/stop angles in the |angle_range| should be given in clockwise order in degrees.
    0-degree angle with the default |rotate| value will start at 12 o'clock.
    If |rotate| is equal to 0, then 0-degree angle value will start at 3 o'clock.
    """

    row, col = np.ogrid[:rect_shape[0], :rect_shape[1]]
    center_row, center_col = center
    min_angle, max_angle = np.deg2rad(np.array(angle_range) + rotate)

    # Ensure max angle > min angle
    if max_angle < min_angle:
        max_angle += 2 * np.pi

    # Convert cartesian to polar coordinates
    theta = np.arctan2(row - center_row, col - center_col) - min_angle
    # Wrap angles between 0 and 2 * pi
    theta %= 2 * np.pi

    return theta <= max_angle - min_angle
