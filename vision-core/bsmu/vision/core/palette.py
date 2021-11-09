from __future__ import annotations

import numpy as np


class Palette:
    def __init__(self, array: np.ndarray, row_names_indexes: dict = None):
        self.array = array
        self._premultiplied_array_cache = None

        self.row_names_indexes = row_names_indexes

    @classmethod
    def from_sparse_index_list(cls, sparse_index_list: list, row_names_indexes: dict = None) -> Palette:
        palette_array = cls.sparse_index_list_to_palette_array(sparse_index_list)
        return cls(palette_array, row_names_indexes)

    @classmethod
    def from_names_rows_dict(cls, names_rows: dict) -> Palette:
        row_names_indexes = {name: row[0] for name, row in names_rows.items()}
        return cls.from_sparse_index_list(list(names_rows.values()), row_names_indexes)

    def row_index_by_name(self, name: str):
        return self.row_names_indexes.get(name)

    @property
    def premultiplied_array(self) -> np.ndarray:
        if self._premultiplied_array_cache is None:
            self._premultiplied_array_cache = np.zeros_like(self.array)
            self._premultiplied_array_cache[:, :3] = np.rint(self.array[:, :3] * (self.array[:, 3:4] / 255))
            # brackets are required, else multiplication of |self.array| could be overflowed
            # (because it has np.uint8 type)

            self._premultiplied_array_cache[:, 3] = self.array[:, 3]
        return self._premultiplied_array_cache

    @staticmethod
    def sparse_index_list_to_palette_array(sparse_index_list: list) -> np.ndarray:
        sparse_index_array = np.array(sparse_index_list)
        palette_array = np.zeros((256, 4), dtype=np.uint8)
        palette_array[sparse_index_array[:, 0]] = sparse_index_array[:, 1:]
        return palette_array
