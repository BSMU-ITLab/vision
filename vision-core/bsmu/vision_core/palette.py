from __future__ import annotations

import numpy as np


class Palette:
    def __init__(self, array: ndarray):
        self.array = array
        self._premultiplied_array_cache = None

    @classmethod
    def from_sparse_index_list(cls, sparse_index_list: list) -> Palette:
        sparse_index_array = np.array(sparse_index_list)
        palette_array = np.zeros((256, 4), dtype=np.uint8)
        palette_array[sparse_index_array[:, 0]] = sparse_index_array[:, 1:]
        return cls(palette_array)

    @property
    def premultiplied_array(self) -> ndarray:
        if self._premultiplied_array_cache is None:
            self._premultiplied_array_cache = np.zeros_like(self.array)
            self._premultiplied_array_cache[:, :3] = np.rint(self.array[:, :3] * (self.array[:, 3:4] / 255))
            # brackets are required, else multiplication of |self.array| could be overflowed
            # (because it has np.uint8 type)

            self._premultiplied_array_cache[:, 3] = self.array[:, 3]
        return self._premultiplied_array_cache
