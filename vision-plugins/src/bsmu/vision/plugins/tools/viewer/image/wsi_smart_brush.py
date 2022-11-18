from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

import cv2
import numpy as np
import skimage.draw
import skimage.measure
from PySide6.QtCore import QEvent, Qt

from bsmu.vision.core.bbox import BBox
from bsmu.vision.core.palette import Palette
from bsmu.vision.plugins.tools.viewer.base import ViewerToolPlugin, LayeredImageViewerTool

if TYPE_CHECKING:
    from typing import Sequence

    from PySide6.QtCore import QObject

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.plugins.windows.main import MainWindowPlugin
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


class WsiSmartBrushImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(self, main_window_plugin: MainWindowPlugin, mdi_plugin: MdiPlugin):
        super().__init__(main_window_plugin, mdi_plugin, WsiSmartBrushImageViewerTool, 'Smart Brush (WSI)', Qt.CTRL + Qt.Key_B)


class Mode(Enum):
    SHOW = 1
    DRAW = 2
    ERASE = 3


DEFAULT_RADIUS = 22
MIN_RADIUS = 2


class WsiSmartBrushImageViewerTool(LayeredImageViewerTool):
    def __init__(self, viewer: LayeredImageViewer, config: UnitedConfig):
        super().__init__(viewer, config)

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
        image_pixel_indexes = self.pos_f_to_image_pixel_indexes(event.position(), self.tool_mask)
        self.draw_brush(*image_pixel_indexes)

    def draw_brush(self, row_f: float, col_f: float):
        # Erase old tool mask
        if self._brush_bbox is not None:
            self.tool_mask.bboxed_pixels(self._brush_bbox).fill(self.tool_background_class)
            self.tool_mask.emit_pixels_modified(self._brush_bbox)

        row_spatial_radius, col_spatial_radius = \
            self.tool_mask.spatial_size_to_indexed(np.array([self.radius, self.radius]))
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
        downscale_factor = 1 / math.sqrt(self.radius)
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
            np.full(shape=downscaled_brush_shape, fill_value=self.tool_background_class)

        if self.mode == Mode.ERASE:
            downscaled_tool_mask_in_brush_bbox[rr, cc] = self.tool_eraser_class
            tool_mask_in_brush_bbox, temp_tool_eraser_class = self.resize_indexed_binary_image(
                downscaled_tool_mask_in_brush_bbox,
                self._brush_bbox.size,
                self.tool_background_class,
                self.tool_eraser_class)
            erased_pixels = tool_mask_in_brush_bbox == temp_tool_eraser_class

            self.tool_mask.bboxed_pixels(self._brush_bbox)[erased_pixels] = self.tool_eraser_class
            self.mask.bboxed_pixels(self._brush_bbox)[erased_pixels] = self.mask_background_class

            self.tool_mask.emit_pixels_modified(self._brush_bbox)
            self.mask.emit_pixels_modified(self._brush_bbox)

            return

        image_in_brush_bbox = self.image.bboxed_pixels(self._brush_bbox)
        downscaled_image_in_brush_bbox = cv2.resize(
            image_in_brush_bbox, tuple(reversed(downscaled_brush_shape)), interpolation=cv2.INTER_AREA)

        samples = downscaled_image_in_brush_bbox[rr, cc]
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
            center_pixel_indexes = np.where((rr == downscaled_brush_center[0]) & (cc == downscaled_brush_center[1]))[0]
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

        tool_mask_circle_pixels = downscaled_tool_mask_in_brush_bbox[rr, cc]
        tool_mask_circle_pixels[label == painted_cluster_label] = self.tool_foreground_class
        downscaled_tool_mask_in_brush_bbox[rr, cc] = tool_mask_circle_pixels

        if self.paint_central_pixel_cluster and self.paint_connected_component:
            labeled_tool_mask_in_brush_bbox = skimage.measure.label(
                downscaled_tool_mask_in_brush_bbox, background=self.tool_background_class)
            label_under_mouse = labeled_tool_mask_in_brush_bbox[downscaled_brush_center[0], downscaled_brush_center[1]]
            downscaled_tool_mask_in_brush_bbox[
                (downscaled_tool_mask_in_brush_bbox == self.tool_foreground_class) &
                (labeled_tool_mask_in_brush_bbox != label_under_mouse)] = self.tool_unconnected_component_class

        tool_mask_in_brush_bbox = cv2.resize(
            downscaled_tool_mask_in_brush_bbox,
            self._brush_bbox.size,
            # cv2.INTER_LINEAR_EXACT cannot be used for indexed image with more then two indexes
            interpolation=cv2.INTER_NEAREST)
        self.tool_mask.bboxed_pixels(self._brush_bbox)[...] = tool_mask_in_brush_bbox

        if self.mode == Mode.DRAW:
            # We can use cv2.INTER_LINEAR_EXACT interpolation for draw mode
            # For that we have to remove all values from tool mask, except background and foreground
            downscaled_tool_mask_in_brush_bbox[downscaled_tool_mask_in_brush_bbox != self.tool_foreground_class] = \
                self.tool_background_class
            tool_mask_in_brush_bbox, temp_tool_foreground_class = self.resize_indexed_binary_image(
                downscaled_tool_mask_in_brush_bbox,
                self._brush_bbox.size,
                self.tool_background_class,
                self.tool_foreground_class)
            drawn_pixels = tool_mask_in_brush_bbox == temp_tool_foreground_class

            mask_in_brush_bbox = self.mask.bboxed_pixels(self._brush_bbox)
            mask_in_brush_bbox[drawn_pixels] = self.mask_foreground_class

            self.mask.emit_pixels_modified(self._brush_bbox)

        self.tool_mask.emit_pixels_modified(self._brush_bbox)
        return

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
