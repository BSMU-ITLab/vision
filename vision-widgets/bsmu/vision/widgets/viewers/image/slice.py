from __future__ import annotations

import numpy as np

from bsmu.vision.widgets.viewers.base import DataViewer
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer
from bsmu.vision_core.constants import PlaneAxis
from bsmu.vision_core.image import FlatImage


class VolumeSliceImageViewer(DataViewer):
    def __init__(self, plane_axis: PlaneAxis, image: VolumeImage = None, zoomable: bool = True):
        super().__init__(image)

        self.plane_axis = plane_axis

        slice_array = self.slice_array(20)
        slice_array = self.windowing(slice_array)

        print('slice array shape', slice_array.shape, slice_array.flags['C_CONTIGUOUS'])
        # slice_array = np.copy(slice_array)
        self._layered_image_viewer = LayeredImageViewer(FlatImage(slice_array), zoomable)

    def show_slice(self, n: int):
        ...

    def slice_array(self, n: int):
        plane_slice = [slice(None), slice(None), slice(None)]
        plane_slice[self.plane_axis] = n
        return self.data.array[tuple(plane_slice)]

    def windowing(self, slice_array):
        window_width = self.data.array.max() - self.data.array.min()
        window_level = (self.data.array.max() + self.data.array.min()) / 2

        print('before', slice_array.min(), slice_array.max())
        lutvalue = np.piecewise(slice_array,
                                [slice_array <= (window_level - 0.5 - (window_width - 1) / 2),
                                 slice_array > (window_level - 0.5 + (window_width - 1) / 2)],
                                [0, 255, lambda slice_array:
                                ((slice_array - (window_level - 0.5)) / (window_width - 1) + 0.5) *
                                (255 - 0)])

        slice_array = lutvalue
        print('after', slice_array.min(), slice_array.max(), slice_array.dtype)
        slice_array = slice_array.astype(np.uint8, copy=False)
        print('after astype', slice_array.min(), slice_array.max(), slice_array.dtype)
        return slice_array
