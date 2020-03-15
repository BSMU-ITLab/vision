from __future__ import annotations

from enum import Enum

import cv2
import numpy as np
import skimage
from PySide2.QtCore import QEvent
from PySide2.QtCore import Qt

from bsmu.vision.plugins.tools.viewer.base import ViewerToolPlugin, LayeredImageViewerTool
from bsmu.vision_core.palette import Palette


class SmartBrushImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(self, app: App):
        super().__init__(app, SmartBrushImageViewerTool, 'Smart Brush', Qt.CTRL + Qt.Key_B)


class Mode(Enum):
    SHOW = 1
    DRAW = 2
    ERASE = 3


DEFAULT_RADIUS = 22
MIN_RADIUS = 2


class SmartBrushImageViewerTool(LayeredImageViewerTool):
    def __init__(self, viewer: LayeredImageViewer, config: UnitedConfig):
        super().__init__(viewer, config)

        self.mode = Mode.SHOW

        self.radius = DEFAULT_RADIUS

        self.paint_central_pixel_cluster = True
        self.paint_dark_cluster = False

        self.paint_connected_component = True

        layers_properties = self.config.value('layers')
        self.mask_palette = Palette.from_names_rows_dict(layers_properties['mask']['palette'])
        self.mask_background_class = self.mask_palette.row_index_by_name('background')
        self.mask_foreground_class = self.mask_palette.row_index_by_name('foreground')

        self.tool_mask_palette = Palette.from_names_rows_dict(layers_properties['tool_mask']['palette'])
        self.tool_background_class = self.tool_mask_palette.row_index_by_name('background')
        self.tool_foreground_class = self.tool_mask_palette.row_index_by_name('foreground')
        self.tool_eraser_class = self.tool_mask_palette.row_index_by_name('eraser')
        self.tool_unconnected_component_class = self.tool_mask_palette.row_index_by_name('unconnected_component')

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
            self.mode = Mode.DRAW
        elif event.buttons() == Qt.RightButton:
            self.mode = Mode.ERASE
        else:
            self.mode = Mode.SHOW

    def draw_brush_event(self, event: QEvent):
        # if not self.viewer.has_image():
        #     return

        self.update_mode(event)
        pixel_coords = self.pos_to_image_pixel_coords(event.pos())
        self.draw_brush(pixel_coords[0], pixel_coords[1])

    def draw_brush(self, row, col):
        # Erase old tool mask
        self.tool_mask.array.fill(0)

        rr, cc = skimage.draw.circle(row, col, self.radius, self.tool_mask.array.shape)

        if self.mode == Mode.ERASE:
            self.erase_region(rr, cc)
            return

        mask_circle_pixels = self.mask.array[rr, cc]
        background_or_mask_class_indexes = \
            (mask_circle_pixels == self.mask_background_class) | (mask_circle_pixels == self.mask_foreground_class)
        # Do not use pixels, which already painted to another mask class
        rr = rr[background_or_mask_class_indexes]
        cc = cc[background_or_mask_class_indexes]

        samples = self.image.array[rr, cc][:, 0]  # use only first channel
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
        tool_mask_circle_pixels[label != painted_cluster_label] = self.tool_background_class
        self.tool_mask.array[rr, cc] = tool_mask_circle_pixels

        if self.paint_central_pixel_cluster and self.paint_connected_component:
            labeled_tool_mask = skimage.measure.label(self.tool_mask.array, background=self.tool_background_class)
            label_under_mouse = labeled_tool_mask[row, col]
            self.tool_mask.array[(self.tool_mask.array == self.tool_foreground_class) &
                                 (labeled_tool_mask != label_under_mouse)] = self.tool_unconnected_component_class

        if self.mode == Mode.DRAW:
            self.mask.array[self.tool_mask.array == self.tool_foreground_class] = self.mask_foreground_class
            self.mask.emit_pixels_modified()

        self.tool_mask.emit_pixels_modified()

    def erase_region(self, rr, cc):
        self.tool_mask.array[rr, cc] = self.tool_eraser_class
        self.mask.array[rr, cc] = self.mask_background_class

        self.tool_mask.emit_pixels_modified()
        self.mask.emit_pixels_modified()
