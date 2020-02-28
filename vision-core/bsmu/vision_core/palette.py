from __future__ import annotations

import numpy as np


class Palette:
    def __init__(self, array: ndarray):
        self.array = array
        self._premultiplied_array_cache = None

    @classmethod
    def from_sparse_index_list(cls, sparse_index_list: list):
        sparse_index_array = np.array(sparse_index_list)
        palette_array = np.zeros((256, 4))
        palette_array[sparse_index_array[:, 0]] = sparse_index_array[:, 1:]
        return cls(palette_array)

    @property
    def premultiplied_array(self) -> ndarray:
        print('Palette array', self.array.shape)
        if self._premultiplied_array_cache is None:
            self._premultiplied_array_cache = np.zeros_like(self.array)
            print('AAAAAAAAA', self._premultiplied_array_cache.shape, self.array.shape)
            self._premultiplied_array_cache[:, :3] = np.rint(self.array[:, :3] * self.array[:, 3:4] / 255)
            self._premultiplied_array_cache[:, 3] = self.array[:, 3]
            print('BBBBBBBBB', self._premultiplied_array_cache.shape)
        return self._premultiplied_array_cache
