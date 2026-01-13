from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Generic, TypeVar

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap, QImage, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.core.data.raster import Raster
from bsmu.vision.core.image import FlatImage
from bsmu.vision.core.layers import Layer, RasterLayer, VectorLayer
from bsmu.vision.widgets.actors import GraphicsActor, ItemT

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtCore import QObject

    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.data import Data
    from bsmu.vision.core.palette import Palette

LayerT = TypeVar('LayerT', bound=Layer)


class LayerActor(Generic[LayerT, ItemT], GraphicsActor[LayerT, ItemT]):
    visible_changed = Signal(bool)
    opacity_changed = Signal(float)

    def __init__(self, model: LayerT | None = None, parent: QObject | None = None):
        # Overrides store viewer-specific visible/opacity values when the same layer
        # is shown in multiple viewers; the model remains the single source of truth.
        self._visible_override: bool | None = None
        self._opacity_override: float | None = None

        super().__init__(model, parent)

    @property
    def layer(self) -> LayerT | None:
        return self.model

    @property
    def data(self) -> Data | None:
        if self.layer is not None:
            return self.layer.data
        return None

    @property
    def data_path(self) -> Path | None:
        return self.layer.data_path if self.layer is not None else None

    @property
    def data_path_name(self) -> str:
        return self.layer.data_path_name if self.layer is not None else ''

    @property
    def name(self) -> str:
        return self.layer.name if self.layer is not None else ''

    @property
    def visible(self) -> bool:
        if self._visible_override is not None:
            return self._visible_override
        return False if self.layer is None else self.layer.visible

    @property
    def visible_override(self) -> bool | None:
        """View-specific visibility override. Set to None to follow the layer's visibility."""
        return self._visible_override

    @visible_override.setter
    def visible_override(self, value: bool | None):
        if self._visible_override != value:
            self._visible_override = value
            self._update_visible()

    def reset_visible_override(self) -> None:
        self.visible_override = None

    def _update_visible(self) -> None:
        self._apply_visible_to_graphics_item()
        self.visible_changed.emit(self.visible)

    @property
    def opacity(self) -> float:
        if self._opacity_override is not None:
            return self._opacity_override
        return 1.0 if self.layer is None else self.layer.opacity

    @property
    def opacity_override(self) -> float | None:
        """View-specific opacity override. Set to None to follow the layer's opacity."""
        return self._opacity_override

    @opacity_override.setter
    def opacity_override(self, value: float | None):
        if value is not None and not (0.0 <= value <= 1.0):
            raise ValueError('Opacity must be between 0.0 and 1.0 or None')
        if self._opacity_override != value:
            self._opacity_override = value
            self._update_opacity()

    def reset_opacity_override(self) -> None:
        self.opacity_override = None

    def _update_opacity(self) -> None:
        self._apply_opacity_to_graphics_item()
        self.opacity_changed.emit(self.opacity)

    def _apply_visible_to_graphics_item(self) -> None:
        if self.graphics_item is not None:
            self.graphics_item.setVisible(self.visible)

    def _apply_opacity_to_graphics_item(self) -> None:
        if self.graphics_item is not None:
            self.graphics_item.setOpacity(self.opacity)

    def _on_layer_visible_changed(self, visible: bool) -> None:
        if self._visible_override is None:
            self._apply_visible_to_graphics_item()
            self.visible_changed.emit(visible)

    def _on_layer_opacity_changed(self, opacity: float) -> None:
        if self._opacity_override is None:
            self._apply_opacity_to_graphics_item()
            self.opacity_changed.emit(opacity)

    def _model_about_to_change(self, new_model: RasterLayer | None) -> None:
        super()._model_about_to_change(new_model)

        if self.layer is not None:
            self.layer.visible_changed.disconnect(self._on_layer_visible_changed)
            self.layer.opacity_changed.disconnect(self._on_layer_opacity_changed)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.layer is not None:
            self.layer.visible_changed.connect(self._on_layer_visible_changed)
            self.layer.opacity_changed.connect(self._on_layer_opacity_changed)
            self._apply_visible_to_graphics_item()
            self._apply_opacity_to_graphics_item()


class RasterLayerActor(LayerActor[RasterLayer, QGraphicsPixmapItem]):
    image_changed = Signal(Raster)  # TODO: rename into raster_changed
    image_shape_changed = Signal(object, object)  # TODO: rename into raster_shape_changed
    image_view_updated = Signal(FlatImage)  # TODO: remove this signal or rename into display_slice_updated

    def __init__(
            self,
            model: RasterLayer | None = None,
            parent: QObject | None = None):

        # Store numpy array, because QImage uses it's data without copying,
        # and QImage will crash if it's data buffer will be deleted.
        self._displayed_pixels = None
        # Bounding boxes of modified regions, which we have to update in the `_displayed_pixels`.
        # This field is not currently in use (full `_displayed_pixels` is recalculated). But later can be used for optimization.
        self._modified_bboxes = []

        self._display_slice: Raster | None = None

        self.slice_number: int | None = None

        super().__init__(model, parent)

    def _create_graphics_item(self) -> QGraphicsPixmapItem:
        graphics_item = QGraphicsPixmapItem()
        graphics_item.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        graphics_item.setOpacity(self.opacity)
        graphics_item.setVisible(self.visible)
        return graphics_item

    @property
    def raster(self) -> Raster | None:
        return self.data

    @property
    def raster_palette(self) -> Palette:
        return self.layer.palette

    @property
    def raster_pixels(self) -> np.ndarray:
        return self.layer.raster_pixels

    def _model_about_to_change(self, new_model: RasterLayer | None) -> None:
        super()._model_about_to_change(new_model)

        if self.layer is not None:
            self.layer.data_changed.disconnect(self._on_layer_data_changed)
            self.layer.image_shape_changed.disconnect(self.image_shape_changed)
            self.layer.image_pixels_modified.disconnect(self._on_image_pixels_modified)

    def _model_changed(self) -> None:
        super()._model_changed()

        if self.layer is not None:
            self.layer.data_changed.connect(self._on_layer_data_changed)
            self.layer.image_shape_changed.connect(self.image_shape_changed)
            self.layer.image_pixels_modified.connect(self._on_image_pixels_modified)

    @property
    def display_slice(self) -> Raster | None:
        """Display-ready version of `current_slice` with intensity windowing applied; used to create QImage."""
        if self._display_slice is None:
            current_slice = self.current_slice
            if current_slice is not None and current_slice.n_channels == 1 and not current_slice.is_indexed:
                # Apply intensity windowing -> must NOT modify original slice.pixels
                windowed_pixels = IntensityWindowing(current_slice.pixels).windowing_applied()
                self._display_slice = current_slice.with_new_pixels(windowed_pixels)
            else:
                self._display_slice = current_slice

            self.image_view_updated.emit(self._display_slice)

        return self._display_slice

    @property
    def current_slice(self) -> Raster | None:
        """
        Current 2D raster slice - raw data with no processing applied.
        Is used by both 2D tools (e.g., Smart Brush) and the display system.
        """
        return self.data

    @property
    def flat_image(self) -> Raster | None:
        warnings.warn('`flat_image` is deprecated; use `current_slice` instead.', DeprecationWarning, stacklevel=2)
        return self.current_slice

    def _update_graphics_item(self) -> None:
        old_scene_bounding_rect = None if self.graphics_item is None else self.graphics_item.sceneBoundingRect()

        if self.raster is None:
            pixmap = QPixmap()
        else:
            pixmap = QPixmap.fromImage(self._create_display_qimage())
        self.graphics_item.setPixmap(pixmap)

        if self.display_slice is not None:
            # TODO: Try using current transform of the `_graphics_item` instead of creating a new one
            spatial_transform = QTransform.fromScale(
                self.display_slice.spatial.spacing[1],
                self.display_slice.spatial.spacing[0],
            )
            self._graphics_item.setTransform(spatial_transform)

        if old_scene_bounding_rect != self.graphics_item.sceneBoundingRect():
            self.scene_bounding_rect_changed.emit()

    def _create_display_qimage(self) -> QImage:
        if self.display_slice.is_indexed:
            self._displayed_pixels = self.display_slice.pixels
            display_qimage_format = QImage.Format.Format_Indexed8
        else:
            # self._displayed_pixels = image_converter.converted_to_normalized_uint8(self.image.array)
            # self._displayed_pixels = image_converter.converted_to_rgba(self._displayed_pixels)

            # Conversion to RGBA will consume additional memory,
            # but the QPainter can draw QImage.Format_RGBA8888_Premultiplied faster
            # (when multiple layers is drawn with semi-transparency), unlike QImage.Format_RGB888.
            # See: https://doc.qt.io/qt-6/qimage.html#Format-enum
            self._displayed_pixels = image_converter.converted_to_rgba(self.display_slice.pixels)
            display_qimage_format = (
                QImage.Format.Format_RGBA8888_Premultiplied
                if self._displayed_pixels.itemsize == 1
                else QImage.Format.Format_RGBA64_Premultiplied
            )

        if not self._displayed_pixels.flags['C_CONTIGUOUS']:
            self._displayed_pixels = np.ascontiguousarray(self._displayed_pixels)

        display_qimage = image_converter.numpy_array_to_qimage(self._displayed_pixels, display_qimage_format)
        if self.display_slice.is_indexed:
            display_qimage.setColorTable(self.display_slice.palette.argb_quadruplets)

        self._modified_bboxes = []
        return display_qimage

    def _on_layer_data_changed(self, data: Raster | None) -> None:
        self.image_changed.emit(data)
        self._on_image_pixels_modified()

    def _on_image_pixels_modified(self, bbox: BBox = None) -> None:  # TODO: rename the method
        if bbox is not None:
            self._modified_bboxes.append(bbox)

        self._display_slice = None

        self._update_graphics_item()


class IntensityWindowing:
    def __init__(self, pixels: np.ndarray, window_width: float | None = None, window_level: float | None = None):
        self.pixels = pixels
        # Use explicit conversion from numpy type (e.g. np.uint8) to int, to prevent possible overflow
        pixels_min = int(pixels.min())
        pixels_max = int(pixels.max())
        self.window_width = window_width if window_width is not None else \
            pixels_max - pixels_min + 1
        self.window_level = window_level if window_level is not None else \
            (pixels_max + pixels_min + 1) / 2

    def windowing_applied(self) -> np.ndarray:
        #  https://github.com/dicompyler/dicompyler-core/blob/master/dicompylercore/dicomparser.py
        windowed_pixels = np.piecewise(
            self.pixels,
            [self.pixels <= (self.window_level - 0.5 - (self.window_width - 1) / 2),
             self.pixels > (self.window_level - 0.5 + (self.window_width - 1) / 2)],
            [0, 255, lambda pixels:
                ((pixels - (self.window_level - 0.5)) / (self.window_width - 1) + 0.5) * (255 - 0)])
        windowed_pixels = windowed_pixels.astype(np.uint8, copy=False)
        return windowed_pixels


class VectorLayerActor(LayerActor[VectorLayer, QGraphicsItem]):
    def __init__(self, model: Layer | None = None, parent: QObject | None = None):
        super().__init__(model, parent)
