from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import List, Tuple


class Palette:
    def __init__(self, array: np.ndarray, row_index_by_name: dict = None):
        self._array = array
        self._premultiplied_array_cache = None

        self._row_index_by_name = row_index_by_name

    @classmethod
    def from_sparse_index_list(cls, sparse_index_list: list, row_index_by_name: dict = None) -> Palette:
        palette_array = cls.sparse_index_list_to_palette_array(sparse_index_list)
        return cls(palette_array, row_index_by_name)

    @classmethod
    def from_row_by_name(cls, row_by_name: dict) -> Palette:
        row_index_by_name = {name: row[0] for name, row in row_by_name.items()}
        return cls.from_sparse_index_list(list(row_by_name.values()), row_index_by_name)

    @classmethod
    def default_binary(
            cls,
            foreground_index: int = 1,
            rgb_color: Tuple[int] | List[int] = (255, 255, 255),
            background_name: str = 'background',
            foreground_name: str = 'foreground',
    ) -> Palette:

        background_index = 0
        return cls.from_sparse_index_list(
            [[background_index, 0, 0, 0, 0], [foreground_index, *rgb_color, 255]],
            {background_name: background_index, foreground_name: foreground_index},
        )

    @classmethod
    def default_soft(cls, rgb_color: Tuple[int] | List[int] = (255, 255, 255)) -> Palette:
        # Have to specify np.uint8 type explicitly, else it will be int32 type
        rgb_color = np.array(rgb_color, dtype=np.uint8)
        rpb_palette_array = np.tile(rgb_color, (256, 1))
        alpha = np.arange(256, dtype=np.uint8)[:, np.newaxis]
        palette_array = np.hstack((rpb_palette_array, alpha))
        return cls(palette_array)

    @staticmethod
    def sparse_index_list_to_palette_array(sparse_index_list: list) -> np.ndarray:
        sparse_index_array = np.array(sparse_index_list)
        palette_array = np.zeros((256, 4), dtype=np.uint8)
        palette_array[sparse_index_array[:, 0]] = sparse_index_array[:, 1:]
        return palette_array

    @property
    def array(self) -> np.ndarray:
        return self._array

    @property
    def premultiplied_array(self) -> np.ndarray:
        if self._premultiplied_array_cache is None:
            self._premultiplied_array_cache = np.zeros_like(self._array)
            self._premultiplied_array_cache[:, :3] = np.rint(self._array[:, :3] * (self._array[:, 3:4] / 255))
            # brackets are required, else multiplication of |self._array| could be overflowed
            # (because it has np.uint8 type)

            self._premultiplied_array_cache[:, 3] = self._array[:, 3]
        return self._premultiplied_array_cache

    def row_index_by_name(self, name: str):
        return self._row_index_by_name.get(name)
