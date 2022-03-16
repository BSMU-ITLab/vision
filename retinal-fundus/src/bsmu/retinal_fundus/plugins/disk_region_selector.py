from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, QMarginsF, QTimer
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import QWidget, QGridLayout, QFrame, QGraphicsItem, QStyle

from bsmu.retinal_fundus.plugins.table_visualizer import PatientRetinalFundusRecord
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer

if TYPE_CHECKING:
    from typing import Tuple, Sequence

    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    from bsmu.vision.core.image.layered import ImageLayer
    from bsmu.vision.widgets.viewers.image.layered.flat import ImageLayerView
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        RetinalFundusTableVisualizer
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class RetinalFundusDiskRegionSelectorPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._table_visualizer_plugin = retinal_fundus_table_visualizer_plugin
        self._table_visualizer: RetinalFundusTableVisualizer | None = None

        self._disk_region_selector: RetinalFundusDiskRegionSelector | None = None

    @property
    def disk_region_selector(self) -> RetinalFundusDiskRegionSelector | None:
        return self._disk_region_selector

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._table_visualizer = self._table_visualizer_plugin.table_visualizer

        self._disk_region_selector = RetinalFundusDiskRegionSelector(self._table_visualizer)
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


class RetinalFundusDiskRegionSelector(QWidget):
    DISK_LAYER_NAME = 'disk'
    SELECTED_SECTORS_LAYER_NAME = 'selected-sectors'

    def __init__(self, table_visualizer: RetinalFundusTableVisualizer):
        super().__init__()

        self._table_visualizer = table_visualizer

        self._disk_viewer = LayeredFlatImageViewer(LayeredImage())
        self._disk_viewer.graphics_view.setRenderHint(QPainter.Antialiasing)
        self._disk_viewer.graphics_view.setFrameShape(QFrame.NoFrame)

        self._table_visualizer.journal_viewer.record_selected.connect(self._on_journal_record_selected)

        self._disk_region_image_pixels: np.ndarray | None = None
        self._disk_mask_region_image_pixels: np.ndarray | None = None

        self._selected_sectors_mask_layer: ImageLayer | None = None
        self._selected_sectors_layer_view: ImageLayerView | None = None
        self._selected_sectors_mask_palette = Palette.default_binary(255, [102, 183, 255])
        self._selected_sectors_opacity_timer = QTimer()
        self._selected_sectors_max_opacity = 0.75

        self._disk_center: QPointF | None = None

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._disk_viewer)
        self.setLayout(layout)

    def _on_journal_record_selected(self, record: PatientRetinalFundusRecord):
        disk_layer = self._disk_viewer.layer_by_name(self.DISK_LAYER_NAME)
        print('dl:', disk_layer)
        if record.disk_bbox is None:
            print('disk_bbox is None')
            return

        disk_region = record.disk_bbox.scaled(1.2, 1.2)
        disk_region.clip_to_shape(record.image.shape)

        self._disk_region_image_pixels = record.image.bboxed_pixels(disk_region)
        self._disk_viewer.data.add_layer_or_modify_pixels(
            self.DISK_LAYER_NAME, self._disk_region_image_pixels, FlatImage)

        self._disk_mask_region_image_pixels = record.disk_mask.bboxed_pixels(disk_region)

        selected_sectors_mask_pixels = np.copy(self._disk_mask_region_image_pixels)
        self._selected_sectors_mask_layer = self._disk_viewer.data.add_layer_or_modify_pixels(
            self.SELECTED_SECTORS_LAYER_NAME,
            selected_sectors_mask_pixels,
            FlatImage,
            self._selected_sectors_mask_palette)
        self._selected_sectors_layer_view = self._disk_viewer.layer_view_by_model(self._selected_sectors_mask_layer)

        self._disk_viewer.fit_image_in()

        self._disk_center = QPointF(disk_region.width, disk_region.height) / 2
        disk_region_rect = QRectF(0, 0, disk_region.width, disk_region.height)

        angle_count = 12 #4
        angle = 360 / angle_count
        rotate = 0 #45
        for i in range(angle_count):
            start_angle = i * angle + rotate
            end_angle = start_angle + angle
            sector_item = GraphicsSectorItem(self._disk_center, start_angle, end_angle, disk_region_rect)
            self._disk_viewer.add_graphics_item(sector_item)

        self._disk_viewer.graphics_scene.selectionChanged.connect(self._on_scene_selection_changed)

        self._selected_sectors_opacity_timer.timeout.connect(self._change_selected_sectors_opacity)
        self._selected_sectors_opacity_timer.start(20)

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
            self._selected_sectors_mask_layer.image.array = np.copy(self._disk_mask_region_image_pixels)
        self._selected_sectors_mask_layer.image.emit_pixels_modified()

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

        self._pen_max_width = 3
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
