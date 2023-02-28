from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import cv2
import numpy as np
import skimage.draw
import skimage.measure
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFormLayout, QSpinBox

from bsmu.vision.core.bbox import BBox
from bsmu.vision.plugins.tools.viewer.base import ViewerToolPlugin, LayeredImageViewerTool, \
    LayeredImageViewerToolSettings, ViewerToolSettingsWidget

if TYPE_CHECKING:
    from typing import Sequence, Type

    from PySide6.QtCore import QObject, QPoint
    from PySide6.QtWidgets import QWidget

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.tools.viewer.base import ViewerTool, ViewerToolSettings
    from bsmu.vision.plugins.windows.main import MainWindowPlugin
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


class Mode(Enum):
    SHOW = 1
    DRAW = 2
    ERASE = 3


DEFAULT_RADIUS = 600
DEFAULT_MIN_RADIUS = 2
DEFAULT_MAX_RADIUS = 2200
DEFAULT_MAX_RADIUS_WITHOUT_DOWNSCALE = 100


class WsiSmartBrushImageViewerToolSettings(LayeredImageViewerToolSettings):
    radius_changed = Signal(float)
    smart_mode_enabled_changed = Signal(bool)
    mask_foreground_class_changed = Signal(int)

    def __init__(
            self,
            layers_props: dict,
            radius: float,
            min_radius: float,
            max_radius: float,
            radius_zoom_factor: float,
            max_radius_without_downscale: float,
            smart_mode_enabled: bool,
            number_of_clusters: int,
            paint_central_pixel_cluster: bool,
            paint_dark_cluster: bool,
            paint_connected_component: bool,
            draw_on_mouse_move: bool,
    ):
        super().__init__(layers_props)

        self._radius = radius
        self._min_radius = min_radius
        self._max_radius = max_radius
        self._radius_zoom_factor = radius_zoom_factor
        self._max_radius_without_downscale = max_radius_without_downscale
        self._smart_mode_enabled = smart_mode_enabled
        self._number_of_clusters = number_of_clusters
        self._paint_central_pixel_cluster = paint_central_pixel_cluster
        self._paint_dark_cluster = paint_dark_cluster
        self._paint_connected_component = paint_connected_component
        self._draw_on_mouse_move = draw_on_mouse_move

        self._mask_background_class = self._mask_palette.row_index_by_name('background')
        self._mask_foreground_class = self._mask_palette.row_index_by_name('foreground')

        self._tool_background_class = self._tool_mask_palette.row_index_by_name('background')
        self._tool_foreground_class = self._tool_mask_palette.row_index_by_name('foreground')
        self._tool_eraser_class = self._tool_mask_palette.row_index_by_name('eraser')
        self._tool_unconnected_component_class = self._tool_mask_palette.row_index_by_name('unconnected_component')

    @property
    def radius(self) -> float:
        return self._radius

    @radius.setter
    def radius(self, value: float):
        if self._radius != value:
            self._radius = value
            self.radius_changed.emit(self._radius)

    @property
    def min_radius(self) -> float:
        return self._min_radius

    @property
    def max_radius(self) -> float:
        return self._max_radius

    @property
    def radius_zoom_factor(self) -> float:
        return self._radius_zoom_factor

    @property
    def max_radius_without_downscale(self) -> float:
        return self._max_radius_without_downscale

    @property
    def smart_mode_enabled(self) -> bool:
        return self._smart_mode_enabled

    @smart_mode_enabled.setter
    def smart_mode_enabled(self, value: bool):
        if self._smart_mode_enabled != value:
            self._smart_mode_enabled = value
            self.smart_mode_enabled_changed.emit(self._smart_mode_enabled)

    @property
    def number_of_clusters(self) -> int:
        return self._number_of_clusters

    @property
    def paint_central_pixel_cluster(self) -> bool:
        return self._paint_central_pixel_cluster

    @property
    def paint_dark_cluster(self) -> bool:
        return self._paint_dark_cluster

    @property
    def paint_connected_component(self) -> bool:
        return self._paint_connected_component

    @property
    def draw_on_mouse_move(self) -> bool:
        return self._draw_on_mouse_move

    @property
    def mask_background_class(self) -> int:
        return self._mask_background_class

    @property
    def mask_foreground_class(self) -> int:
        return self._mask_foreground_class

    @mask_foreground_class.setter
    def mask_foreground_class(self, value: int):
        if self._mask_foreground_class != value:
            self._mask_foreground_class = value
            self.mask_foreground_class_changed.emit(self._mask_foreground_class)

    @property
    def tool_background_class(self) -> int:
        return self._tool_background_class

    @property
    def tool_foreground_class(self) -> int:
        return self._tool_foreground_class

    @property
    def tool_eraser_class(self) -> int:
        return self._tool_eraser_class

    @property
    def tool_unconnected_component_class(self) -> int:
        return self._tool_unconnected_component_class

    @classmethod
    def from_config(cls, config: UnitedConfig) -> WsiSmartBrushImageViewerToolSettings:
        return cls(
            cls.layers_props_from_config(config),
            config.value('radius', DEFAULT_RADIUS),
            config.value('min_radius', DEFAULT_MIN_RADIUS),
            config.value('max_radius', DEFAULT_MAX_RADIUS),
            config.value('radius_zoom_factor', 1),
            config.value('max_radius_without_downscale', DEFAULT_MAX_RADIUS_WITHOUT_DOWNSCALE),
            config.value('smart_mode_enabled', True),
            config.value('number_of_clusters', 2),
            config.value('paint_central_pixel_cluster', True),
            config.value('paint_dark_cluster', False),
            config.value('paint_connected_component', True),
            config.value('draw_on_mouse_move', True),
        )


class WsiSmartBrushImageViewerToolSettingsWidget(ViewerToolSettingsWidget):
    def __init__(self, tool_settings: WsiSmartBrushImageViewerToolSettings, parent: QWidget = None):
        super().__init__(tool_settings, parent)

        layout = QFormLayout()

        self._mask_foreground_class_spin_box = QSpinBox()
        self._mask_foreground_class_spin_box.setValue(tool_settings.mask_foreground_class)
        self._mask_foreground_class_spin_box.valueChanged.connect(self._on_mask_foreground_class_spin_box_value_changed)
        tool_settings.mask_foreground_class_changed.connect(self._on_tool_settings_mask_foreground_class_changed)
        layout.addRow('&Mask Foreground:', self._mask_foreground_class_spin_box)

        self.setLayout(layout)

    def _on_mask_foreground_class_spin_box_value_changed(self, value: int):
        self.tool_settings.mask_foreground_class = value

    def _on_tool_settings_mask_foreground_class_changed(self, value: int):
        self._mask_foreground_class_spin_box.setValue(value)


class WsiSmartBrushImageViewerTool(LayeredImageViewerTool):
    def __init__(self, viewer: LayeredImageViewer, settings: WsiSmartBrushImageViewerToolSettings):
        super().__init__(viewer, settings)

        self._mode = Mode.SHOW

        self._brush_bbox = None

    def activate(self):
        super().activate()

        self.viewer.viewport.setMouseTracking(True)

        mouse_pos_in_viewport = self.viewer.viewport.mapFromGlobal(QCursor.pos())
        self._draw_brush_in_pos(mouse_pos_in_viewport)

    def deactivate(self):
        self.viewer.viewport.setMouseTracking(False)

        super().deactivate()

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonPress or event.type() == QEvent.MouseButtonRelease:
            self.draw_brush_event(event)
            return True
        elif event.type() == QEvent.MouseMove:
            self.draw_brush_event(event)
            return False
        elif event.type() == QEvent.Wheel:
            angle_in_degrees = event.angleDelta().y() / 8
            zoom_factor = 1 + angle_in_degrees / 65 * self.settings.radius_zoom_factor
            self.settings.radius = \
                min(max(self.settings.min_radius, self.settings.radius * zoom_factor), self.settings.max_radius)
            self.draw_brush_event(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def update_mode(self, event: QEvent):
        if event.buttons() == Qt.LeftButton and (self.settings.draw_on_mouse_move or event.type() != QEvent.MouseMove):
            if event.type() != QEvent.Wheel:  # This condition is used only to fix strange bug
                # after a mouse click on the app title bar, try to change brush radius (using Ctrl + mouse wheel)
                # event.buttons() shows, that LeftButton is pressed (but it is not pressed)
                # that leads to draw mode, but we want only change brush radius (in show mode)
                self._mode = Mode.DRAW
        elif event.buttons() == Qt.RightButton:
            self._mode = Mode.ERASE
        elif event.type() == QEvent.MouseButtonPress and event.buttons() == Qt.MiddleButton:
            self.settings.smart_mode_enabled = not self.settings.smart_mode_enabled
        else:
            self._mode = Mode.SHOW

    def draw_brush_event(self, event: QEvent):
        # if not self.viewer.has_image():
        #     return

        self.update_mode(event)
        self._draw_brush_in_pos(event.position().toPoint())

    def _draw_brush_in_pos(self, pos: QPoint):
        image_pixel_indexes = self.pos_to_image_pixel_indexes(pos, self.tool_mask)
        self.draw_brush(*image_pixel_indexes)

    def draw_brush(self, row_f: float, col_f: float):
        # Erase old tool mask
        if self._brush_bbox is not None:
            self.tool_mask.bboxed_pixels(self._brush_bbox).fill(self.settings.tool_background_class)
            self.tool_mask.emit_pixels_modified(self._brush_bbox)

        row_spatial_radius, col_spatial_radius = \
            self.tool_mask.spatial_size_to_indexed(np.array([self.settings.radius, self.settings.radius]))
        not_clipped_brush_bbox = BBox(
            int(round(col_f - col_spatial_radius)), int(round(col_f + col_spatial_radius)) + 1,
            int(round(row_f - row_spatial_radius)), int(round(row_f + row_spatial_radius)) + 1)
        self._brush_bbox = not_clipped_brush_bbox.clipped_to_shape(self.tool_mask.shape)
        brush_clip_bbox = self._brush_bbox.calculate_clip_bbox(not_clipped_brush_bbox)
        if self._brush_bbox.empty:
            return

        # Downscale the image in brush region if radius is large.
        # Smaller analyzed region will improve performance of algorithms
        # (skimage.draw.ellipse, cv2.kmeans, skimage.measure.label) at the expense of accuracy.
        downscale_factor = min(1, self.settings.max_radius_without_downscale / self.settings.radius)
        downscaled_brush_shape_f = \
            (self._brush_bbox.height * downscale_factor, self._brush_bbox.width * downscale_factor)
        downscaled_brush_shape = np.rint(downscaled_brush_shape_f).astype(int) + 1
        if (downscaled_brush_shape == 0).any():
            return

        not_clipped_brush_bbox_center = (np.array(not_clipped_brush_bbox.shape) - 1) / 2
        brush_center = np.array(brush_clip_bbox.map_rc_point(not_clipped_brush_bbox_center))
        downscaled_brush_center_f = brush_center * downscale_factor
        downscaled_brush_center = np.rint(downscaled_brush_center_f).astype(int)

        row_downscaled_radius, col_downscaled_radius = \
            row_spatial_radius * downscale_factor, col_spatial_radius * downscale_factor

        rr, cc = skimage.draw.ellipse(  # we can use rounded row, col and radii,
            # but float values give more precise resulting ellipse indexes
            *downscaled_brush_center_f, row_downscaled_radius, col_downscaled_radius,
            shape=downscaled_brush_shape)  # try with downscaled_brush_shape_f

        downscaled_tool_mask_in_brush_bbox = \
            np.full(shape=downscaled_brush_shape, fill_value=self.settings.tool_background_class)

        if not self.settings.smart_mode_enabled or self._mode == Mode.ERASE:
            tool_class, mask_class = (self.settings.tool_eraser_class, self.settings.mask_background_class) \
                if self._mode == Mode.ERASE \
                else (self.settings.tool_foreground_class, self.settings.mask_foreground_class)

            downscaled_tool_mask_in_brush_bbox[rr, cc] = tool_class
            tool_mask_in_brush_bbox, temp_tool_class = self.resize_indexed_binary_image(
                downscaled_tool_mask_in_brush_bbox,
                self._brush_bbox.size,
                self.settings.tool_background_class,
                tool_class)
            modified_pixels = tool_mask_in_brush_bbox == temp_tool_class

            self.tool_mask.bboxed_pixels(self._brush_bbox)[modified_pixels] = tool_class
            self.tool_mask.emit_pixels_modified(self._brush_bbox)

            if self._mode in [Mode.ERASE, Mode.DRAW]:
                self.mask.bboxed_pixels(self._brush_bbox)[modified_pixels] = mask_class
                self.mask.emit_pixels_modified(self._brush_bbox)

            return

        image_in_brush_bbox = self.image.bboxed_pixels(self._brush_bbox)
        downscaled_image_in_brush_bbox = cv2.resize(
            image_in_brush_bbox, tuple(reversed(downscaled_brush_shape)), interpolation=cv2.INTER_AREA)

        downscaled_image_in_brush_bbox = self._preprocess_downscaled_image_in_brush_bbox(downscaled_image_in_brush_bbox)
        samples = downscaled_image_in_brush_bbox[rr, cc]
        if len(samples.shape) == 2:  # if there is an axis with channels (multichannel image)
            samples = samples[:, 0]  # use only the first channel
        samples = samples.astype(np.float32)
        if self.settings.number_of_clusters > samples.size:
            return

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        ret, label, centers = cv2.kmeans(
            samples, self.settings.number_of_clusters, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
        label = label.ravel()  # 2D array (one column) to 1D array without copy
        centers = centers.ravel()

        if self.settings.paint_central_pixel_cluster:
            center_pixel_indexes = np.where((rr == downscaled_brush_center[0]) & (cc == downscaled_brush_center[1]))[0]
            if center_pixel_indexes.size != 1:  # there are situations, when the center pixel is out of image
                return
            center_pixel_index = center_pixel_indexes[0]
            painted_cluster_label = label[center_pixel_index]
        else:
            # Label of light cluster
            painted_cluster_label = 0 if centers[0] > centers[1] else 1
            if self.settings.paint_dark_cluster:
                # Swapping 1 with 0 and 0 with 1
                painted_cluster_label = 1 - painted_cluster_label

        tool_mask_circle_pixels = downscaled_tool_mask_in_brush_bbox[rr, cc]
        tool_mask_circle_pixels[label == painted_cluster_label] = self.settings.tool_foreground_class
        downscaled_tool_mask_in_brush_bbox[rr, cc] = tool_mask_circle_pixels

        if self.settings.paint_connected_component:
            if 0 <= downscaled_brush_center[0] < downscaled_tool_mask_in_brush_bbox.shape[0] and \
                    0 <= downscaled_brush_center[1] < downscaled_tool_mask_in_brush_bbox.shape[1]:

                labeled_tool_mask_in_brush_bbox = skimage.measure.label(
                    downscaled_tool_mask_in_brush_bbox, background=self.settings.tool_background_class)
                label_under_mouse = labeled_tool_mask_in_brush_bbox[
                    downscaled_brush_center[0], downscaled_brush_center[1]]
                downscaled_tool_mask_in_brush_bbox[
                    (downscaled_tool_mask_in_brush_bbox == self.settings.tool_foreground_class) &
                    (labeled_tool_mask_in_brush_bbox != label_under_mouse)] = \
                    self.settings.tool_unconnected_component_class
            else:
                downscaled_tool_mask_in_brush_bbox[
                    downscaled_tool_mask_in_brush_bbox == self.settings.tool_foreground_class] = \
                    self.settings.tool_unconnected_component_class

        tool_mask_in_brush_bbox = cv2.resize(
            downscaled_tool_mask_in_brush_bbox,
            self._brush_bbox.size,
            # cv2.INTER_LINEAR_EXACT cannot be used for indexed image with more then two indexes
            interpolation=cv2.INTER_NEAREST)
        self.tool_mask.bboxed_pixels(self._brush_bbox)[...] = tool_mask_in_brush_bbox

        if self._mode == Mode.DRAW:
            # We can use cv2.INTER_LINEAR_EXACT interpolation for draw mode
            # For that we have to remove all values from tool mask, except background and foreground
            downscaled_tool_mask_in_brush_bbox[
                downscaled_tool_mask_in_brush_bbox != self.settings.tool_foreground_class] = \
                self.settings.tool_background_class
            tool_mask_in_brush_bbox, temp_tool_foreground_class = self.resize_indexed_binary_image(
                downscaled_tool_mask_in_brush_bbox,
                self._brush_bbox.size,
                self.settings.tool_background_class,
                self.settings.tool_foreground_class)
            drawn_pixels = tool_mask_in_brush_bbox == temp_tool_foreground_class

            mask_in_brush_bbox = self.mask.bboxed_pixels(self._brush_bbox)
            mask_in_brush_bbox[drawn_pixels] = self.settings.mask_foreground_class

            self.mask.emit_pixels_modified(self._brush_bbox)

        self.tool_mask.emit_pixels_modified(self._brush_bbox)
        return

    def _preprocess_downscaled_image_in_brush_bbox(self, image: np.ndarray):
        return image

    @staticmethod
    def resize_indexed_binary_image(
            image: np.ndarray, size: Sequence[int], background_index, foreground_index) -> tuple[np.ndarray, int]:
        """Resize indexed image, which has only two indexes: background and foreground.
        Foreground indexes of resized image can be replaced by |temp_foreground_index|
        :param image: image can be modified (foreground indexes can be replaced by |temp_foreground_index|)
        :param size: output image size
        :param background_index:
        :param foreground_index:
        :return: tuples[resized image, temp foreground index]
        """
        # Background and foreground indexes have to be nearest integers (e.g. 0 and 1, or 5 and 6)
        # to use cv2.INTER_LINEAR_EXACT interpolation for resize.
        if abs(foreground_index - background_index) != 1:
            # Index has to be in uint8 range (0 <= index <= 255)
            temp_foreground_index = background_index - 1 \
                if background_index == 255 \
                else background_index + 1

            image[image == foreground_index] = temp_foreground_index
        else:
            temp_foreground_index = foreground_index

        resized_image = cv2.resize(image, size, interpolation=cv2.INTER_LINEAR_EXACT)
        return resized_image, temp_foreground_index


class WsiSmartBrushImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            tool_cls: Type[ViewerTool] = WsiSmartBrushImageViewerTool,
            tool_settings_cls: Type[ViewerToolSettings] = WsiSmartBrushImageViewerToolSettings,
            tool_settings_widget_cls: Type[ViewerToolSettingsWidget] = WsiSmartBrushImageViewerToolSettingsWidget,
            action_name: str = 'Smart Brush (WSI)',
            action_shortcut: Qt.Key = Qt.Key_2,
    ):
        super().__init__(
            main_window_plugin,
            mdi_plugin,
            tool_cls,
            tool_settings_cls,
            tool_settings_widget_cls,
            action_name,
            action_shortcut,
        )
