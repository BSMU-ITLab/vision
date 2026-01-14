from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QImage

import bsmu.vision.core.converters.image as image_converter
from bsmu.vision.core.image import Image, FlatImage
from bsmu.vision.core.image.layered import ImageLayer
from bsmu.vision.widgets.viewers.layered import LayeredDataViewer

if TYPE_CHECKING:
    from pathlib import Path

    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.palette import Palette


warnings.warn(
    'The "widgets.viewers.image.layered.layered.py" module is deprecated; use "widgets.viewers.layered.py" instead.',
    DeprecationWarning,
    stacklevel=2,
)


class ImageLayerView(QObject):
    DEFAULT_LAYER_OPACITY = 1

    image_changed = Signal(Image)
    image_shape_changed = Signal(object, object)
    image_view_updated = Signal(FlatImage)
    visibility_changed = Signal(bool)
    opacity_changed = Signal(float)

    def __init__(self, image_layer: ImageLayer, visible: bool = True,
                 opacity: float = DEFAULT_LAYER_OPACITY):
        super().__init__()

        self._image_layer = image_layer
        self._image_layer.data_changed.connect(self._on_layer_image_updated)
        self._image_layer.image_shape_changed.connect(self.image_shape_changed)
        self._image_layer.image_pixels_modified.connect(self._update_image_view)
        self._visible = visible
        self._opacity = opacity

        self._image_view = None

        self._displayed_qimage_cache = None
        # Store numpy array, because QImage uses it's data without copying,
        # and QImage will crash if it's data buffer will be deleted.
        # Moreover, it is used to update only |self._modified_cache_bboxes|.
        self._displayed_pixels = None
        # Bounding boxes of modified regions, which we have to update in the |self._displayed_pixels|.
        self._modified_cache_bboxes = []

        self._view_min_spacing = None

    @property
    def image_view(self) -> FlatImage:
        return self._image_view

    @property
    def image_layer(self) -> ImageLayer:
        return self._image_layer

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

    @property
    def image(self) -> Image:
        return self._image_layer.image

    @property
    def image_palette(self) -> Palette:
        return self._image_layer.image_palette

    @property
    def image_pixels(self) -> np.ndarray:
        return self._image_layer.image_pixels

    @property
    def image_path(self) -> Path:
        return self._image_layer.image_path

    @property
    def image_path_name(self) -> str:
        return self._image_layer.image_path_name

    @property
    def name(self) -> str:
        return self._image_layer.name

    @property
    def view_min_spacing(self) -> float:
        return self._view_min_spacing

    @view_min_spacing.setter
    def view_min_spacing(self, value: float):
        if self._view_min_spacing != value:
            self._view_min_spacing = value

            self._displayed_qimage_cache = None

    @property
    def displayed_image(self) -> QImage:
        if self._displayed_qimage_cache is None or self._modified_cache_bboxes:
            self._update_displayed_qimage_cache()
        return self._displayed_qimage_cache

    def _create_image_view(self) -> FlatImage:
        raise NotImplementedError(f'{self.__class__.__name__} must implement _create_image_view')

    def calculate_view_min_spacing(self) -> float:
        return float(self.image_view.spatial.spacing.min())  # cast to float, else it will have numpy.float type

    def _update_displayed_qimage_cache(self):
        if self.image_view.is_indexed:
            self._displayed_pixels = self.image_view.pixels
            displayed_qimage_format = QImage.Format.Format_Indexed8
        else:
            # self._displayed_pixels = image_converter.converted_to_normalized_uint8(self.image.array)
            # self._displayed_pixels = image_converter.converted_to_rgba(self._displayed_pixels)

            # Conversion to RGBA will consume additional memory,
            # but the QPainter can draw QImage.Format_RGBA8888_Premultiplied faster
            # (when multiple layers is drawn with semi-transparency), unlike QImage.Format_RGB888.
            # See: https://doc.qt.io/qt-6/qimage.html#Format-enum
            self._displayed_pixels = image_converter.converted_to_rgba(self.image_view.array)

            displayed_qimage_format = QImage.Format.Format_RGBA8888_Premultiplied \
                if self._displayed_pixels.itemsize == 1 \
                else QImage.Format.Format_RGBA64_Premultiplied

        if not self._displayed_pixels.flags['C_CONTIGUOUS']:
            self._displayed_pixels = np.ascontiguousarray(self._displayed_pixels)

        self._displayed_qimage_cache = image_converter.numpy_array_to_qimage(
            self._displayed_pixels, displayed_qimage_format)
        if self.image_view.is_indexed:
            self._displayed_qimage_cache.setColorTable(self.image_view.palette.argb_quadruplets)

        # Scale image to take into account spatial attributes (spacings)
        width_spacing = self.image_view.spatial.spacing[1]
        height_spacing = self.image_view.spatial.spacing[0]
        spatial_width = width_spacing / self.view_min_spacing * self._displayed_qimage_cache.width()
        spatial_height = height_spacing / self.view_min_spacing * self._displayed_qimage_cache.height()

        self._displayed_qimage_cache = self._displayed_qimage_cache.scaled(
            spatial_width, spatial_height, mode=Qt.TransformationMode.SmoothTransformation)

        self._modified_cache_bboxes = []

    def _on_layer_image_updated(self, image: Image):
        self.image_changed.emit(image)
        self._update_image_view()

    def _update_image_view(self, bbox: BBox = None):
        if bbox is None:
            # Have to update the whole image
            self._displayed_qimage_cache = None
            self._modified_cache_bboxes = []
        else:
            self._modified_cache_bboxes.append(bbox)

        self._image_view = self._create_image_view()
        if self._image_view is not None and self._image_view.n_channels == 1 and not self._image_view.is_indexed:
            self.intensity_windowing = IntensityWindowing(self._image_view.array)
            self._image_view.array = self.intensity_windowing.windowing_applied()
        self.image_view_updated.emit(self.image_view)


class LayeredImageViewer(LayeredDataViewer):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            '`LayeredImageViewer` is deprecated; use `LayeredDataViewer` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
