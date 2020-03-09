from __future__ import annotations

import math

import numpy as np
from PySide2.QtWidgets import QVBoxLayout

from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer
from bsmu.vision_core.constants import PlaneAxis
from bsmu.vision_core.image import FlatImage


class VolumeSliceImageViewer(LayeredImageViewer):
    def __init__(self, plane_axis: PlaneAxis, data: VolumeImage = None, zoomable: bool = True):
        super().__init__(data, zoomable)

        self.plane_axis = plane_axis

        # TODO: transfer windowing to class ImageItemLayer
        self.window_width = self.data.array.max() - self.data.array.min() + 1
        self.window_level = (self.data.array.max() + self.data.array.min() + 1) / 2

        center_slice_pixels = self.slice_pixels(self.center_slice_number())
        windowed_center_slice_pixels = self.windowing(center_slice_pixels)
        # Temporary assert
        assert windowed_center_slice_pixels.flags['C_CONTIGUOUS'], 'array of center slice pixels is not CONTIGUOUS'

        self.add_layer(FlatImage(windowed_center_slice_pixels))

        # self._layered_image_viewer = LayeredImageViewer(FlatImage(windowed_center_slice_pixels), zoomable)
        #
        # self.layout = QVBoxLayout()
        # self.layout.addWidget(self._layered_image_viewer)
        # self.setLayout(self.layout)

    def show_slice(self, slice_number: int):
        ...

    def slice_pixels(self, slice_number: int):
        # Do not use np.take, because that will copy data
        plane_slice_indexing = [slice(None)] * 3
        plane_slice_indexing[self.plane_axis] = slice_number
        return self.data.array[tuple(plane_slice_indexing)]

    def center_slice_number(self):
        return math.floor(self.data.array.shape[self.plane_axis] / 2)

    def windowing(self, slice_pixels):
        #  https://github.com/dicompyler/dicompyler-core/blob/master/dicompylercore/dicomparser.py
        slice_pixels = np.piecewise(
            slice_pixels,
            [slice_pixels <= (self.window_level - 0.5 - (self.window_width - 1) / 2),
             slice_pixels > (self.window_level - 0.5 + (self.window_width - 1) / 2)],
            [0, 255, lambda slice_pixels:
                ((slice_pixels - (self.window_level - 0.5)) / (self.window_width - 1) + 0.5) * (255 - 0)])
        slice_pixels = slice_pixels.astype(np.uint8, copy=False)
        return slice_pixels
