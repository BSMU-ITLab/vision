from __future__ import annotations

import math
from typing import Optional

import numpy as np

from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer, _ImageLayerView
from bsmu.vision_core.constants import PlaneAxis
from bsmu.vision_core.image.base import FlatImage, SpatialAttrs


class _VolumeSliceImageLayerView(_ImageLayerView):
    def __init__(self, plane_axis: PlaneAxis, slice_number: int,
                 image_layer: ImageLayer = None, visible: bool = True,
                 opacity: float = _ImageLayerView.DEFAULT_LAYER_OPACITY):
        self.plane_axis = plane_axis
        self.slice_number = slice_number
        super().__init__(image_layer, visible, opacity)

    def _create_image_view(self) -> FlatImage:
        slice_pixels = self.image.slice_pixels(self.plane_axis, self.slice_number)

        slice_origin = np.delete(self.image.spatial.origin, self.plane_axis)
        slice_spacing = np.delete(self.image.spatial.spacing, self.plane_axis)
        slice_direction = np.delete(np.delete(self.image.spatial.direction, self.plane_axis, axis=0),
                                    self.plane_axis, axis=1)
        slice_spatial = SpatialAttrs(slice_origin, slice_spacing, slice_direction)

        return FlatImage(slice_pixels, palette=self.image_layer.image.palette, spatial=slice_spatial)


class VolumeSliceImageViewer(LayeredImageViewer):
    def __init__(self, plane_axis: PlaneAxis, slice_number: Optional[int] = None, data: LayeredImage = None,
                 zoomable: bool = True):

        self.plane_axis = plane_axis
        self.slice_number = 15  ### slice_number if slice_number is not None else self.center_slice_number()

        super().__init__(data, zoomable)

        # TODO: transfer windowing to class ImageItemLayer
###        self.window_width = self.data.array.max() - self.data.array.min() + 1
###        self.window_level = (self.data.array.max() + self.data.array.min() + 1) / 2

        # center_slice_pixels = self.slice_pixels(self.center_slice_number())
        # windowed_center_slice_pixels = self.windowing(center_slice_pixels)
        # # Temporary assert
        # assert windowed_center_slice_pixels.flags['C_CONTIGUOUS'], 'array of center slice pixels is not CONTIGUOUS'

        # slice_origin = np.delete(data.spatial.origin, self.plane_axis)
        # slice_spacing = np.delete(data.spatial.spacing, self.plane_axis)
        # slice_direction = np.delete(np.delete(data.spatial.direction, self.plane_axis, axis=0), self.plane_axis, axis=1)
        # slice_spatial = SpatialAttrs(slice_origin, slice_spacing, slice_direction)
        # self.add_layer(FlatImage(windowed_center_slice_pixels, spatial=slice_spatial), name=data.dir_name)

        # self._layered_image_viewer = LayeredImageViewer(FlatImage(windowed_center_slice_pixels), zoomable)
        #
        # self.layout = QVBoxLayout()
        # self.layout.addWidget(self._layered_image_viewer)
        # self.setLayout(self.layout)

    def _add_layer_view_from_layer(self, image_layer: ImageLayer) -> _VolumeSliceImageLayerView:
        layer_view = _VolumeSliceImageLayerView(self.plane_axis, self.slice_number, image_layer)
        self._add_layer_view(layer_view)
        return layer_view

    def show_slice(self, slice_number: int):
        ...

    # def slice_pixels(self, slice_number: int):
    #     # Do not use np.take, because that will copy data
    #     plane_slice_indexing = [slice(None)] * 3
    #     plane_slice_indexing[self.plane_axis] = slice_number
    #     return self.data.array[tuple(plane_slice_indexing)]

    def center_slice_number(self):
        return math.floor(self.data.active_layer_view.image_pixels.shape[self.plane_axis] / 2)

    def show_next_slice(self):
        ...

    def show_previous_slice(self):
        ...
