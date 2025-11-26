from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import cv2
import numpy as np
import skimage.draw
import skimage.measure
from PySide6.QtCore import QEvent, Qt

from bsmu.vision.core.bbox import BBox
from bsmu.vision.core.palette import Palette
from bsmu.vision.plugins.tools.viewer import ViewerToolPlugin, ViewerToolSettingsWidget
from bsmu.vision.plugins.tools.viewer.image.layered import LayeredImageViewerTool, LayeredImageViewerToolSettings

if TYPE_CHECKING:
    from PySide6.QtCore import QObject

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettings, PalettePackSettingsPlugin
    from bsmu.vision.plugins.tools.viewer import ViewerTool, ViewerToolSettings
    from bsmu.vision.plugins.undo import UndoManager, UndoPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin
    from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer


class Mode(Enum):
    SHOW = 1
    DRAW = 2
    ERASE = 3


DEFAULT_RADIUS = 22
MIN_RADIUS = 2


class SmartBrushImageViewerToolSettings(LayeredImageViewerToolSettings):
    def __init__(
            self,
            layers_props: dict,
            palette_pack_settings: PalettePackSettings,
            icon_file_name: str = ':/icons/brush.svg',
    ):
        super().__init__(layers_props, palette_pack_settings, icon_file_name)


class SmartBrushImageViewerTool(LayeredImageViewerTool):
    def __init__(self, viewer: LayeredImageViewer, undo_manager: UndoManager, config: UnitedConfig):
        super().__init__(viewer, undo_manager, config)

        self.mode = Mode.SHOW

        self.radius = DEFAULT_RADIUS

        self.paint_central_pixel_cluster = True
        self.paint_dark_cluster = False

        self.paint_connected_component = True

        layers_props = self.config.value('layers')
        self.mask_palette = Palette.from_config(layers_props['mask'].get('palette'))
        self.mask_background_class = self.mask_palette.row_index_by_name('background')
        self.mask_foreground_class = self.mask_palette.row_index_by_name('foreground')

        self.tool_mask_palette = Palette.from_config(layers_props['tool_mask'].get('palette'))
        self.tool_background_class = self.tool_mask_palette.row_index_by_name('background')
        self.tool_foreground_class = self.tool_mask_palette.row_index_by_name('foreground')
        self.tool_eraser_class = self.tool_mask_palette.row_index_by_name('eraser')
        self.tool_unconnected_component_class = self.tool_mask_palette.row_index_by_name('unconnected_component')

        self._brush_bbox = None

    def activate(self):
        super().activate()

        self.viewer.viewport.setMouseTracking(True)

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonPress or event.type() == QEvent.MouseButtonRelease:
            self.draw_brush_event(event)
            return True
        elif event.type() == QEvent.MouseMove:
            self.draw_brush_event(event)
            return False
        elif event.type() == QEvent.Wheel and event.modifiers() == Qt.ControlModifier:
            angle_delta_y = event.angleDelta().y()
            zoom_factor = 1 + np.sign(angle_delta_y) * 0.2 * abs(angle_delta_y) / 110
            self.radius *= zoom_factor
            self.radius = max(self.radius, MIN_RADIUS)
            self.draw_brush_event(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def update_mode(self, event: QEvent):
        if event.buttons() == Qt.LeftButton:
            if event.type() != QEvent.Wheel:  # This condition is used only to fix strange bug
                # after a mouse click on the app title bar, try to change brush radius (using Ctrl + mouse wheel)
                # event.buttons() shows, that LeftButton is pressed (but it is not pressed)
                # that leads to draw mode, but we want only change brush radius (in show mode)
                self.mode = Mode.DRAW
        elif event.buttons() == Qt.RightButton:
            self.mode = Mode.ERASE
        else:
            self.mode = Mode.SHOW

    def draw_brush_event(self, event: QEvent):
        # if not self.viewer.has_image():
        #     return

        self.update_mode(event)
        image_pixel_coords = self.map_viewport_to_pixel_coords(event.position(), self.tool_mask)
        self.draw_brush(*image_pixel_coords)

    def draw_brush(self, row_f: float, col_f: float):
        row = int(round(row_f))
        col = int(round(col_f))

        # Erase old tool mask
        if self._brush_bbox is not None:
            self.tool_mask.bboxed_pixels(self._brush_bbox).fill(self.tool_background_class)
            self.tool_mask.emit_pixels_modified(self._brush_bbox)

        row_spatial_radius, col_spatial_radius = \
            self.tool_mask.map_spatial_vector_to_pixel_vector(np.array([self.radius, self.radius]))
        rr, cc = skimage.draw.ellipse(  # we can use rounded row, col and radii,
            # but float values give more precise resulting ellipse indexes
            row_f, col_f, row_spatial_radius, col_spatial_radius, shape=self.tool_mask.shape)
        self._brush_bbox = BBox(
            int(round(col_f - col_spatial_radius)), int(round(col_f + col_spatial_radius)) + 1,
            int(round(row_f - row_spatial_radius)), int(round(row_f + row_spatial_radius)) + 1)
        self._brush_bbox.clip_to_shape(self.tool_mask.shape)
        if self._brush_bbox.empty:
            return

        if self.mode == Mode.ERASE:
            self.erase_region(rr, cc)
            return

        mask_circle_pixels = self.mask.array[rr, cc]
        background_or_mask_class_indexes = \
            (mask_circle_pixels == self.mask_background_class) | (mask_circle_pixels == self.mask_foreground_class)
        # Do not use pixels, which already painted to another mask class
        rr = rr[background_or_mask_class_indexes]
        cc = cc[background_or_mask_class_indexes]

        samples = self.image.array[rr, cc]
        if len(samples.shape) == 2:  # if there is an axis with channels (multichannel image)
            samples = samples[:, 0]  # use only the first channel
        samples = samples.astype(np.float32)
        number_of_clusters = 2
        if number_of_clusters > samples.size:
            return

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        ret, label, centers = cv2.kmeans(samples, number_of_clusters, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        label = label.ravel()  # 2D array (one column) to 1D array without copy
        centers = centers.ravel()

        if self.paint_central_pixel_cluster:
            center_pixel_indexes = np.where((rr == row) & (cc == col))[0]
            if center_pixel_indexes.size != 1:  # there are situations, when the center pixel is out of image
                return
            center_pixel_index = center_pixel_indexes[0]
            painted_cluster_label = label[center_pixel_index]
        else:
            # Label of light cluster
            painted_cluster_label = 0 if centers[0] > centers[1] else 1
            if self.paint_dark_cluster:
                # Swapping 1 with 0 and 0 with 1
                painted_cluster_label = 1 - painted_cluster_label

        tool_mask_circle_pixels = self.tool_mask.array[rr, cc]
        tool_mask_circle_pixels[label == painted_cluster_label] = self.tool_foreground_class
        self.tool_mask.array[rr, cc] = tool_mask_circle_pixels

        tool_mask_in_brush_bbox = self.tool_mask.bboxed_pixels(self._brush_bbox)
        if self.paint_central_pixel_cluster and self.paint_connected_component:
            labeled_tool_mask_in_brush_bbox = skimage.measure.label(
                tool_mask_in_brush_bbox, background=self.tool_background_class)
            row_col_mapped_to_brush_bbox = self._brush_bbox.map_rc_point((row, col))
            label_under_mouse = labeled_tool_mask_in_brush_bbox[row_col_mapped_to_brush_bbox]
            tool_mask_in_brush_bbox[
                (tool_mask_in_brush_bbox == self.tool_foreground_class) &
                (labeled_tool_mask_in_brush_bbox != label_under_mouse)] = self.tool_unconnected_component_class

        if self.mode == Mode.DRAW:
            mask_in_brush_bbox = self.mask.bboxed_pixels(self._brush_bbox)
            mask_in_brush_bbox[tool_mask_in_brush_bbox == self.tool_foreground_class] = self.mask_foreground_class
            self.mask.emit_pixels_modified(self._brush_bbox)

        self.tool_mask.emit_pixels_modified(self._brush_bbox)

    def erase_region(self, rr, cc):
        self.tool_mask.array[rr, cc] = self.tool_eraser_class
        self.mask.array[rr, cc] = self.mask_background_class

        self.tool_mask.emit_pixels_modified(self._brush_bbox)
        self.mask.emit_pixels_modified(self._brush_bbox)


class SmartBrushImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: type[ViewerTool] = SmartBrushImageViewerTool,
            tool_settings_cls: type[ViewerToolSettings] = SmartBrushImageViewerToolSettings,
            tool_settings_widget_cls: type[ViewerToolSettingsWidget] = None,
            action_name: str = 'Smart Brush',
            action_shortcut: Qt.Key = Qt.Key_2,
    ):
        super().__init__(
            main_window_plugin,
            mdi_plugin,
            undo_plugin,
            palette_pack_settings_plugin,
            tool_cls,
            tool_settings_cls,
            tool_settings_widget_cls,
            action_name,
            action_shortcut,
        )
