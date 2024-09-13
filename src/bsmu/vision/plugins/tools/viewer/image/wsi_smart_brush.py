from __future__ import annotations

import logging
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
from bsmu.vision.core.image import MASK_MAX
from bsmu.vision.core.rle import encode_rle, decode_rle
from bsmu.vision.plugins.tools.viewer import (
    LayeredImageViewerTool, LayeredImageViewerToolSettings, ViewerToolPlugin, ViewerToolSettingsWidget)
from bsmu.vision.plugins.undo import UndoCommand

if TYPE_CHECKING:
    from typing import Sequence

    from PySide6.QtCore import QObject, QPoint
    from PySide6.QtWidgets import QWidget

    from bsmu.vision.core.config.united import UnitedConfig
    from bsmu.vision.core.image import FlatImage
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettings, PalettePackSettingsPlugin
    from bsmu.vision.plugins.tools.viewer import ViewerTool, ViewerToolSettings
    from bsmu.vision.plugins.undo import UndoManager, UndoPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin
    from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer


class Mode(Enum):
    SHOW = 1
    HIDE = 2
    DRAW = 3
    ERASE = 4


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
            palette_pack_settings: PalettePackSettings,
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
            icon_file_name: str = ':/icons/brush.svg',
    ):
        super().__init__(layers_props, palette_pack_settings, icon_file_name)

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

        self._mask_background_class = self.mask_palette.row_index_by_name('background')
        self._mask_foreground_class = self.mask_palette.row_index_by_name('foreground')

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
    def from_config(
            cls,
            config: UnitedConfig,
            palette_pack_settings: PalettePackSettings
    ) -> WsiSmartBrushImageViewerToolSettings:
        return cls(
            cls.layers_props_from_config(config),
            palette_pack_settings,
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

        # self._mask_layer_combo_box = QComboBox()
        # layout.addRow('&Mask Layer:', self._mask_layer_combo_box)

        self._mask_foreground_class_spin_box = QSpinBox()
        self._mask_foreground_class_spin_box.setMaximum(MASK_MAX)
        self._mask_foreground_class_spin_box.setValue(tool_settings.mask_foreground_class)
        self._mask_foreground_class_spin_box.valueChanged.connect(self._on_mask_foreground_class_spin_box_value_changed)
        tool_settings.mask_foreground_class_changed.connect(self._on_tool_settings_mask_foreground_class_changed)
        layout.addRow('&Mask Foreground:', self._mask_foreground_class_spin_box)

        self.setLayout(layout)

    def _on_mask_foreground_class_spin_box_value_changed(self, value: int):
        self.tool_settings.mask_foreground_class = value

    def _on_tool_settings_mask_foreground_class_changed(self, value: int):
        self._mask_foreground_class_spin_box.setValue(value)


class ModifyMaskCommand(UndoCommand):
    def __init__(
            self,
            mask: FlatImage,
            modified_bbox: BBox,
            modified_bbox_pixels: np.ndarray,
            new_modified_bbox_pixels: int | np.ndarray,
            is_last_to_merge: bool = False,
            text: str = 'Modify Mask',
            parent: UndoCommand = None,
    ):
        """
        :param modified_bbox: bbox of modified pixels
        :param modified_bbox_pixels: boolean array with True on modified pixels
        :param new_modified_bbox_pixels: if has type int, then all modified pixels will have such value.
        Else it is flat (one-dimensional) array with values of new pixels, which were modified
        :param is_last_to_merge: the last command to be merged.
        We need it to compress command data only after full merge, because compression can be slow
        """

        super().__init__(text, parent)

        self._is_last_to_merge = is_last_to_merge
        if is_last_to_merge:
            # The last to merge command is a fake command and contains no useful data
            # It's just an indicator, that now previous command can be compressed
            return

        self._mask = mask
        self._modified_bbox = modified_bbox
        self._modified_bbox_pixels = modified_bbox_pixels
        self._compressed_modified_bbox_pixels = None
        if type(new_modified_bbox_pixels) != int:
            raise NotImplementedError()
        self._new_modified_bbox_pixels = new_modified_bbox_pixels
        self._rle_compressed_old_modified_bbox_pixels = None  # after command compression we get
        # flat (one-dimensional) array with old values of modified pixels. Then it's compressed using RLE into
        # tuple of (values, run_lengths) and stored into this property
        self._old_bbox_pixels = mask.bboxed_pixels(modified_bbox).copy()

        self._mergeable = True

    @property
    def _is_compressed(self) -> bool:
        return self._modified_bbox_pixels is None

    def _clean(self):
        self._is_last_to_merge = None
        self._mask = None
        self._modified_bbox = None
        self._modified_bbox_pixels = None
        self._compressed_modified_bbox_pixels = None
        self._new_modified_bbox_pixels = None
        self._rle_compressed_old_modified_bbox_pixels = None
        self._old_bbox_pixels = None
        self._mergeable = None

    def id(self) -> int:
        return self._id

    def redo(self):
        modified_bbox_pixels = self._uncompressed_modified_bbox_pixels() \
            if self._is_compressed \
            else self._modified_bbox_pixels
        self._mask.bboxed_pixels(self._modified_bbox)[modified_bbox_pixels] = self._new_modified_bbox_pixels
        self._mask.emit_pixels_modified(self._modified_bbox)

    def undo(self):
        if self._is_compressed:
            old_modified_bbox_pixels = decode_rle(*self._rle_compressed_old_modified_bbox_pixels)
            self._mask.bboxed_pixels(self._modified_bbox)[self._uncompressed_modified_bbox_pixels()] = \
                old_modified_bbox_pixels
        else:
            self._mask.modify_bboxed_pixels(self._modified_bbox, self._old_bbox_pixels)
        self._mask.emit_pixels_modified(self._modified_bbox)

    def mergeWith(self, other: ModifyMaskCommand) -> bool:
        """
        Method called after |other.redo| method
        :param other: is next command after |self|
        """
        if not self._mergeable:
            return False

        if other._is_last_to_merge:
            self._compress_data()
            return True

        if type(self._new_modified_bbox_pixels) == int \
                and self._new_modified_bbox_pixels != other._new_modified_bbox_pixels:
            logging.warning(f'You forgot to use {FinishModifyMaskCommand.__name__} to compress the command '
                            f'as early as possible')
            self._compress_data()
            return False

        if bbox_contains_other := self._modified_bbox.contains(other._modified_bbox):
            merged_modified_bbox = self._modified_bbox
        else:
            merged_modified_bbox = self._modified_bbox.united_with(other._modified_bbox)
            # Add some reserve pads for the bbox to reduce number of mask copying.
            # Else, e.g. during drawing by brush, we will have to copy bboxed mask every mouse move event,
            # when |bbox_contains_other| is False.
            # Reserve pads are proportional to the shift of |other._modified_bbox| relative to |self._modified_bbox|
            reserve_pads = self._modified_bbox.pads_to_include(other._modified_bbox)
            reserve_factor = 50
            reserve_pads.resize(reserve_factor, reserve_factor)
            merged_modified_bbox.add_bbox_pads(reserve_pads)
            merged_modified_bbox.clip_to_shape(self._mask.shape)

        other_modified_bbox_mapped_to_merged = other._modified_bbox.mapped_to_bbox(merged_modified_bbox)

        if bbox_contains_other:
            merged_modified_bbox_pixels = self._modified_bbox_pixels
        else:
            merged_modified_bbox_pixels = np.zeros(merged_modified_bbox.shape, dtype=self._modified_bbox_pixels.dtype)
            modified_bbox_mapped_to_merged = self._modified_bbox.mapped_to_bbox(merged_modified_bbox)
            modified_bbox_mapped_to_merged.pixels(merged_modified_bbox_pixels)[...] = self._modified_bbox_pixels

            merged_old_bbox_pixels = self._mask.bboxed_pixels(merged_modified_bbox).copy()
            other_modified_bbox_mapped_to_merged.pixels(merged_old_bbox_pixels)[...] = other._old_bbox_pixels
            modified_bbox_mapped_to_merged.pixels(merged_old_bbox_pixels)[...] = self._old_bbox_pixels
            self._old_bbox_pixels = merged_old_bbox_pixels

        # Use |= operator to keep True-values unchanged, else they could be replaced by False-values
        other_modified_bbox_mapped_to_merged.pixels(merged_modified_bbox_pixels)[...] |= other._modified_bbox_pixels

        self._modified_bbox = merged_modified_bbox
        self._modified_bbox_pixels = merged_modified_bbox_pixels

        # Weird behaviour: |other| command is not deleted (Python __dell__ is not called),
        # when |mergeWith| method returns True. Looks like there are references to it somewhere.
        # At the same time, underlying C++ object of |other| is deleted in the QUndoStack::push method.
        # We nullify all properties of |other| to minimize memory leaks.
        # But undeleted |other| command will leak very small amount of memory anyway.
        # TODO: create minimal test app with multiple merged commands and check if they are deleted.
        # TODO: fill a bug report if they are not deleted, when |mergeWith| returns True.
        other._clean()

        return True

    def _compress_data(self):
        # Use boolean array indexing to get a copy of flat (one-dimensional) array with old pixels
        # and compress them using RLE into tuple of (values, run_lengths)
        self._rle_compressed_old_modified_bbox_pixels = self._old_bbox_pixels[self._modified_bbox_pixels]
        self._rle_compressed_old_modified_bbox_pixels = encode_rle(self._rle_compressed_old_modified_bbox_pixels)
        self._old_bbox_pixels = None

        self._compressed_modified_bbox_pixels = np.packbits(self._modified_bbox_pixels)
        self._modified_bbox_pixels = None

        self._mergeable = False

    def _uncompressed_modified_bbox_pixels(self) -> np.ndarray:
        modified_bbox_pixels = np.unpackbits(
            self._compressed_modified_bbox_pixels, count=self._modified_bbox.element_count)
        modified_bbox_pixels = modified_bbox_pixels.reshape(self._modified_bbox.shape)
        # Change np.uint8 type to bool type using |view| method. It's much faster than |astype|
        modified_bbox_pixels = modified_bbox_pixels.view(bool)
        return modified_bbox_pixels


class FinishModifyMaskCommand(ModifyMaskCommand):
    """
    It is a fake command and contains no useful data
    It is used just as an indicator, that it is the last command to merge and now previous command can be compressed
    """
    def __init__(self, text: str = 'Finish Modify Mask', parent: UndoCommand = None):
        super().__init__(None, None, None, None, True, text, parent)

    def id(self) -> int:
        # We need to merge commands of such type with ModifyMaskCommand commands
        return ModifyMaskCommand.command_type_id()

    def redo(self):
        pass

    def undo(self):
        pass


class WsiSmartBrushImageViewerTool(LayeredImageViewerTool):
    # Store and increment stroke ID, when DRAW or ERASE mode is activated.
    # Use class attribute, because new instances of tool are created, when tool is activated/deactivated
    _STROKE_ID = 0

    def __init__(
            self,
            viewer: LayeredImageViewer,
            undo_manager: UndoManager,
            settings: WsiSmartBrushImageViewerToolSettings,
    ):
        super().__init__(viewer, undo_manager, settings)

        self._mode = None
        self._brush_bbox = None
        self._is_stroke_finished = True

    @property
    def mode(self) -> Mode:
        return self._mode

    @mode.setter
    def mode(self, value: Mode):
        if self._mode != value:
            self._mode = value
            if self._mode == Mode.DRAW or self._mode == Mode.ERASE:
                self._is_stroke_finished = False
                WsiSmartBrushImageViewerTool._STROKE_ID += 1
            else:
                self._finish_stroke()

    def activate(self):
        super().activate()

        self.viewer.viewport.setMouseTracking(True)

        if self.viewer.viewport.underMouse():
            self.mode = Mode.SHOW
            mouse_pos_in_viewport = self.viewer.viewport.mapFromGlobal(QCursor.pos())
            self._draw_brush_in_pos(mouse_pos_in_viewport)
        else:
            self.mode = Mode.HIDE

    def deactivate(self):
        self.mode = None

        self.viewer.viewport.setMouseTracking(False)

        super().deactivate()

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.Leave:
            self.draw_brush_event(event)
            return False
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
        if event.type() == QEvent.Leave:
            self.mode = Mode.HIDE
        elif event.buttons() == Qt.LeftButton and (self.settings.draw_on_mouse_move or event.type() != QEvent.MouseMove):
            if event.type() != QEvent.Wheel:  # This condition is used only to fix strange bug
                # after a mouse click on the app title bar, try to change brush radius (using Ctrl + mouse wheel)
                # event.buttons() shows, that LeftButton is pressed (but it is not pressed)
                # that leads to draw mode, but we want only change brush radius (in show mode)
                self.mode = Mode.DRAW
        elif event.buttons() == Qt.RightButton:
            self.mode = Mode.ERASE
        elif event.type() == QEvent.MouseButtonPress and event.buttons() == Qt.MiddleButton:
            self.settings.smart_mode_enabled = not self.settings.smart_mode_enabled
        else:
            self.mode = Mode.SHOW

    @property
    def _brush_stroke_text(self) -> str:
        return f'Brush Stroke #{self._STROKE_ID}'

    def draw_brush_event(self, event: QEvent):
        # if not self.viewer.has_image():
        #     return

        self.update_mode(event)

        # Erase old tool mask
        if self._brush_bbox is not None:
            self.tool_mask.bboxed_pixels(self._brush_bbox).fill(self.settings.tool_background_class)
            self.tool_mask.emit_pixels_modified(self._brush_bbox)

        if self._mode != Mode.HIDE:
            self._draw_brush_in_pos(event.position().toPoint())

    def _draw_brush_in_pos(self, pos: QPoint):
        image_pixel_indexes = self.pos_to_image_pixel_indexes(pos, self.tool_mask)
        self.draw_brush(*image_pixel_indexes)

    def draw_brush(self, row_f: float, col_f: float):
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
                command_text = f'{self._brush_stroke_text}: Erase' \
                    if self._mode == Mode.ERASE \
                    else f'{self._brush_stroke_text}: Draw Class {mask_class}'
                modify_mask_command = ModifyMaskCommand(
                    self.mask, self._brush_bbox, modified_pixels, mask_class, text=command_text)
                self._undo_manager.push(modify_mask_command)

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

            modify_mask_command = ModifyMaskCommand(
                self.mask, self._brush_bbox, drawn_pixels, self.settings.mask_foreground_class,
                text=f'{self._brush_stroke_text}: Draw Class {self.settings.mask_foreground_class}')
            self._undo_manager.push(modify_mask_command)

        self.tool_mask.emit_pixels_modified(self._brush_bbox)
        return

    def _preprocess_downscaled_image_in_brush_bbox(self, image: np.ndarray):
        return image

    def _finish_stroke(self):
        if self._is_stroke_finished:
            return

        finish_stroke_command = FinishModifyMaskCommand()
        self._undo_manager.push(finish_stroke_command)
        self._is_stroke_finished = True

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
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: type[ViewerTool] = WsiSmartBrushImageViewerTool,
            tool_settings_cls: type[ViewerToolSettings] = WsiSmartBrushImageViewerToolSettings,
            tool_settings_widget_cls: type[ViewerToolSettingsWidget] = WsiSmartBrushImageViewerToolSettingsWidget,
            action_name: str = 'Smart Brush (WSI)',
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
