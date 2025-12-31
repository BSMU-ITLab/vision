from __future__ import annotations

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
    from PySide6.QtCore import QObject

    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.data import Data
    from bsmu.vision.core.palette import Palette

LayerT = TypeVar('LayerT', bound=Layer)


class LayerActor(Generic[LayerT, ItemT], GraphicsActor[LayerT, ItemT]):
    DEFAULT_LAYER_OPACITY = 1

    visibility_changed = Signal(bool)
    opacity_changed = Signal(float)

    def __init__(
            self,
            model: LayerT | None = None,
            visible: bool = True,
            opacity: float = DEFAULT_LAYER_OPACITY,
            parent: QObject | None = None,
    ):
        self._visible = visible
        self._opacity = opacity

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
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        if self._visible != value:
            self._visible = value
            self.visibility_changed.emit(self._visible)

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        if self._opacity != value:
            self._opacity = value
            self.opacity_changed.emit(self._opacity)


class RasterLayerActor(LayerActor[RasterLayer, QGraphicsPixmapItem]):
    image_changed = Signal(Raster)
    image_shape_changed = Signal(object, object)
    image_view_updated = Signal(FlatImage)

    def __init__(
            self,
            model: RasterLayer | None = None,
            visible: bool = True,
            opacity: float = LayerActor.DEFAULT_LAYER_OPACITY,
            parent: QObject | None = None):

        # Store numpy array, because QImage uses it's data without copying,
        # and QImage will crash if it's data buffer will be deleted.
        self._displayed_pixels = None
        # Bounding boxes of modified regions, which we have to update in the `_displayed_pixels`.
        # This field is not currently in use (full `_displayed_pixels` is recalculated). But later can be used for optimization.
        self._modified_bboxes = []

        self._image_view = None

        super().__init__(model, visible, opacity, parent)

        self.layer.data_changed.connect(self._on_layer_data_changed)
        self.layer.image_shape_changed.connect(self.image_shape_changed)
        self.layer.image_pixels_modified.connect(self._on_image_pixels_modified)

    def _create_graphics_item(self) -> QGraphicsPixmapItem:
        graphics_item = QGraphicsPixmapItem()
        graphics_item.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        graphics_item.setOpacity(self._opacity)
        graphics_item.setVisible(self._visible)
        return graphics_item

    @property
    def raster(self) -> Raster | None:
        return self.data
        # if self.layer is not None:
        #     return self.layer.data
        # return None

    @property
    def raster_palette(self) -> Palette:
        return self.layer.palette

    @property
    def raster_pixels(self) -> np.ndarray:
        return self.layer.raster_pixels

    def _model_about_to_change(self, new_model: RasterLayer | None) -> None:
        pass

    def _model_changed(self) -> None:
        pass

    @property
    def image_view(self) -> FlatImage:
        if self._image_view is None:
            self._image_view = self.flat_image
            if self._image_view is not None and self._image_view.n_channels == 1 and not self._image_view.is_indexed:
                intensity_windowing = IntensityWindowing(self._image_view.pixels)
                self._image_view.pixels = intensity_windowing.windowing_applied()
            self.image_view_updated.emit(self.image_view)

        return self._image_view

    @property
    def flat_image(self) -> Raster | None:
        return self.layer.data

    def _update_graphics_item(self) -> None:
        if self.raster is None:
            pixmap = QPixmap()
        else:
            pixmap = QPixmap.fromImage(self._create_display_qimage())
        self.graphics_item.setPixmap(pixmap)

        #TODO: Try using current transform of the `_graphics_item` instead of creating a new one
        spatial_transform = QTransform.fromScale(self.image_view.spatial.spacing[1], self.image_view.spatial.spacing[0])
        self._graphics_item.setTransform(spatial_transform)

    def _create_display_qimage(self) -> QImage:
        if self.image_view.is_indexed:
            self._displayed_pixels = self.image_view.pixels
            display_qimage_format = QImage.Format.Format_Indexed8
        else:
            # self._displayed_pixels = image_converter.converted_to_normalized_uint8(self.image.array)
            # self._displayed_pixels = image_converter.converted_to_rgba(self._displayed_pixels)

            # Conversion to RGBA will consume additional memory,
            # but the QPainter can draw QImage.Format_RGBA8888_Premultiplied faster
            # (when multiple layers is drawn with semi-transparency), unlike QImage.Format_RGB888.
            # See: https://doc.qt.io/qt-6/qimage.html#Format-enum
            self._displayed_pixels = image_converter.converted_to_rgba(self.image_view.pixels)
            display_qimage_format = (
                QImage.Format.Format_RGBA8888_Premultiplied
                if self._displayed_pixels.itemsize == 1
                else QImage.Format.Format_RGBA64_Premultiplied
            )

        if not self._displayed_pixels.flags['C_CONTIGUOUS']:
            self._displayed_pixels = np.ascontiguousarray(self._displayed_pixels)

        display_qimage = image_converter.numpy_array_to_qimage(self._displayed_pixels, display_qimage_format)
        if self.image_view.is_indexed:
            display_qimage.setColorTable(self.image_view.palette.argb_quadruplets)

        self._modified_bboxes = []
        return display_qimage

    def _on_layer_data_changed(self, data: Raster | None) -> None:
        self.image_changed.emit(data)
        self._on_image_pixels_modified()

    def _on_image_pixels_modified(self, bbox: BBox = None) -> None:  # TODO: rename the method
        if bbox is not None:
            self._modified_bboxes.append(bbox)

        self._update_graphics_item()

        self._image_view = None


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
