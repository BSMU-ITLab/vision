from __future__ import annotations

import math
from typing import Optional

import numpy as np

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, ImageLayerView, IntensityWindowing
from bsmu.vision_core.constants import PlaneAxis
from bsmu.vision_core.image.base import FlatImage, SpatialAttrs


class VolumeSliceImageLayerView(ImageLayerView):
    def __init__(self, plane_axis: PlaneAxis, slice_number: int,
                 image_layer: ImageLayer = None, visible: bool = True,
                 opacity: float = ImageLayerView.DEFAULT_LAYER_OPACITY):
        super().__init__(image_layer, visible, opacity)

        self.plane_axis = plane_axis
        self.slice_number = slice_number

        self._image_view = self._create_image_view()
        if self._image_view.n_channels == 1 and not self._image_view.is_indexed:
            # TODO: transfer windowing to class ImageLayerView
            self.intensity_windowing = IntensityWindowing(self._image_view.array)
            self._image_view.array = self.intensity_windowing.windowing_applied()

    def _create_image_view(self) -> FlatImage:
        slice_pixels = self.slice_pixels()

        # slice_pixels = np.ascontiguousarray(slice_pixels, dtype=np.uint8)
        # print('min, max', slice_pixels.min(), slice_pixels.max(), slice_pixels.dtype)
        # assert slice_pixels.flags['C_CONTIGUOUS'], 'array of center slice pixels is not CONTIGUOUS'

        slice_origin = np.delete(self.image.spatial.origin, self.plane_axis)
        slice_spacing = np.delete(self.image.spatial.spacing, self.plane_axis)
        slice_direction = np.delete(np.delete(self.image.spatial.direction, self.plane_axis, axis=0),
                                    self.plane_axis, axis=1)
        slice_spatial = SpatialAttrs(slice_origin, slice_spacing, slice_direction)

        return FlatImage(slice_pixels, palette=self.image_palette, spatial=slice_spatial)

    def slice_pixels(self) -> np.ndarray:
        return self.image.slice_pixels(self.plane_axis, self.slice_number)


class VolumeSliceImageViewer(LayeredImageViewer):
    def __init__(self, plane_axis: PlaneAxis, slice_number: Optional[int] = None, data: LayeredImage = None,
                 zoomable: bool = True):
        super().__init__(data, zoomable)

        self.plane_axis = plane_axis

        first_layer_image_center_slice_number = math.floor(self.data.layers[0].image_pixels.shape[self.plane_axis] / 2)
        self.slice_number = slice_number if slice_number is not None else first_layer_image_center_slice_number

        self._add_layer_views_from_model()

    def _add_layer_view_from_model(self, image_layer: ImageLayer) -> VolumeSliceImageLayerView:
        layer_view = VolumeSliceImageLayerView(self.plane_axis, self.slice_number, image_layer)
        self._add_layer_view(layer_view)
        return layer_view

    def show_slice(self, slice_number: int):
        ...

    def center_slice_number(self):
        return math.floor(self.active_layer_view.image_pixels.shape[self.plane_axis] / 2)

    def show_next_slice(self):
        ...

    def show_previous_slice(self):
        ...
