from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from bsmu.vision.core.constants import PlaneAxis
from bsmu.vision.core.image import FlatImage, SpatialAttrs, VolumeImage
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer, ImageLayerView
from bsmu.vision.widgets.viewers.image.layered.flat import FlatImageLayerView

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.image import Image
    from bsmu.vision.core.image.layered import ImageLayer, LayeredImage
    from bsmu.vision.widgets.viewers.graphics import ImageViewerSettings


class VolumeSliceImageLayerView(ImageLayerView):
    def __init__(self, plane_axis: PlaneAxis, slice_number: int,
                 image_layer: ImageLayer = None, visible: bool = True,
                 opacity: float = ImageLayerView.DEFAULT_LAYER_OPACITY):
        super().__init__(image_layer, visible, opacity)

        self.plane_axis = plane_axis
        self._slice_number = slice_number

        self._flat_image_cache = None

        self._update_image_view()

    @property
    def slice_number(self) -> int:
        return self._slice_number

    @slice_number.setter
    def slice_number(self, value: int):
        if self._slice_number != value:
            self._slice_number = value
            self._update_image_view()

    def show_next_slice(self):
        max_slice_number = self.image.array.shape[self.plane_axis] - 1
        self.slice_number = min(max_slice_number, self.slice_number + 1)

    def show_prev_slice(self):
        self.slice_number = max(0, self.slice_number - 1)

    @property
    def flat_image(self) -> FlatImage:
        if self._flat_image_cache is None and self.image is not None:
            slice_pixels = self.slice_pixels()

            # slice_pixels = np.ascontiguousarray(slice_pixels, dtype=np.uint8)
            # print('min, max', slice_pixels.min(), slice_pixels.max(), slice_pixels.dtype)
            # assert slice_pixels.flags['C_CONTIGUOUS'], 'array of center slice pixels is not CONTIGUOUS'

            slice_origin = np.delete(self.image.spatial.origin, self.plane_axis)
            slice_spacing = np.delete(self.image.spatial.spacing, self.plane_axis)
            slice_direction = np.delete(np.delete(self.image.spatial.direction, self.plane_axis, axis=0),
                                        self.plane_axis, axis=1)
            slice_spatial = SpatialAttrs(slice_origin, slice_spacing, slice_direction)

            self._flat_image_cache = FlatImage(slice_pixels, palette=self.image_palette,
                                               path=self.image_path, spatial=slice_spatial)
            # |flat_image| contains pixel array view (not a copy),
            # so if we change its pixels, the pixels of image will be changed too
            self._flat_image_cache.pixels_modified.connect(self.image.pixels_modified)
        return self._flat_image_cache

    def _create_image_view(self) -> FlatImage:
        return self.flat_image

    def _on_layer_image_updated(self, image: Image):
        if self.image is not None:
            self._slice_number = self.image.center_slice_number(self.plane_axis)
        super()._on_layer_image_updated(image)

    def _update_image_view(self, bbox: BBox = None):
        self._flat_image_cache = None
        super()._update_image_view()

    def slice_pixels(self) -> np.ndarray:
        return self.image.slice_pixels(self.plane_axis, self.slice_number)


class VolumeSliceImageViewer(LayeredImageViewer):
    def __init__(
            self,
            plane_axis: PlaneAxis,
            slice_number: int | None = None,
            data: LayeredImage = None,
            settings: ImageViewerSettings = None,
            parent: QWidget | None = None,
    ):
        self.plane_axis = plane_axis

        if slice_number is None:
            # Use center image slice of first layer
            slice_number = math.floor(data.layers[0].image_pixels.shape[self.plane_axis] / 2)

        self.slice_number = slice_number

        super().__init__(data, settings, parent)

    def _add_layer_view_from_model(self, image_layer: ImageLayer, layer_index: int = None) -> VolumeSliceImageLayerView:
        if isinstance(image_layer.image, VolumeImage):
            layer_view = VolumeSliceImageLayerView(
                self.plane_axis, self.slice_number, image_layer,
                image_layer.visibility.visible, image_layer.visibility.opacity)
        else:
            layer_view = FlatImageLayerView(image_layer, image_layer.visibility.visible, image_layer.visibility.opacity)
        self._add_layer_view(layer_view, layer_index)
        return layer_view

    def show_slice(self, slice_number: int):
        ...

    def center_slice_number(self):
        return math.floor(self.active_layer_view.image_pixels.shape[self.plane_axis] / 2)

    def show_next_slice(self):
        for layer_view in self.layer_views:
            if isinstance(layer_view, VolumeSliceImageLayerView):
                layer_view.show_next_slice()

    def show_prev_slice(self):
        for layer_view in self.layer_views:
            if isinstance(layer_view, VolumeSliceImageLayerView):
                layer_view.show_prev_slice()
