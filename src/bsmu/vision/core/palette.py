from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import List, Tuple


class Palette:
    def __init__(self, array: np.ndarray, row_index_by_name: dict = None):
        self._array = array
        self._premultiplied_array_cache = None

        self._argb_quadruplets_cache = None

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

    @classmethod
    def from_config(cls, palette_config_data: list | dict | None) -> Palette | None:
        """
        # Examples of palette configs:
        # 1) custom palette using list of lists. The format is
        # - [index, R, G, B, A]
        palette:
          - [0, 0, 0, 0, 0]
          - [1, 0, 255, 0, 255]
          - [5, 255, 0, 0, 255]

        # 2) custom palette with added names for each row. The format is
        # row-by-name:
        #   name: [index, R, G, B, A]
        palette:
          row-by-name:
            background: [0, 0, 0, 0, 0]
            foreground: [1, 50, 170, 230, 255]

        # 3) palette will be generated using 'rgb-color' property and optional 'foreground-value' property.
        # If only 'rgb-color' property is specified, then will be created soft palette
        # from transparent 'rgb-color' to opaque. The format of the 'rgb-color' property is: [R, G, B]
        palette:
          rgb-color: [0, 255, 0]

        # 4) If both 'rgb-color' and 'foreground-value' properties are specified, then binary palette will be created.
        # It's the same as:
        # palette:
        #   - [0, 0, 0, 0, 0]
        #   - [foreground-value, r, g, b, 255]
        palette:
          rgb-color: [0, 255, 0]
          foreground-value: 1
        """
        if palette_config_data is None:
            return None

        if isinstance(palette_config_data, list):
            return Palette.from_sparse_index_list(palette_config_data)

        if isinstance(palette_config_data, dict):
            row_by_name_prop = palette_config_data.get('row-by-name')
            rgb_color_prop = palette_config_data.get('rgb-color')
            if not (row_by_name_prop is None or rgb_color_prop is None):
                warnings.warn('Palette cannot use "row-by-name" and "rgb-color" properties simultaneously')
                return None

            if row_by_name_prop is not None:
                return Palette.from_row_by_name(row_by_name_prop)

            if rgb_color_prop is not None:
                foreground_value_prop = palette_config_data.get('foreground-value')
                if foreground_value_prop is None:
                    return Palette.default_soft(rgb_color_prop)
                else:
                    return Palette.default_binary(foreground_value_prop, rgb_color_prop)

        warnings.warn('Incorrect Palette config')
        return None

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

    @property
    def argb_quadruplets(self) -> list[int]:
        """
        :return: a list of ARGB quadruplets on the format #AARRGGBB, equivalent to an unsigned int.
        It can be used e.g., for QImage.setColorTable(colors: Sequence[int])
        see: https://doc.qt.io/qt-6/qimage.html#setColorTable
        """
        if self._argb_quadruplets_cache is None:
            # PySide6.QtGui.qRgba(*rgba) can be used, to get ARGB quadruplet, but int.from_bytes works faster
            # and need no import of PySide6.QtGui module.
            self._argb_quadruplets_cache = \
                [int.from_bytes([rgba[3], rgba[0], rgba[1], rgba[2]], byteorder='big') for rgba in self._array]
        return self._argb_quadruplets_cache

    def row_index_by_name(self, name: str, default: int = None) -> int:
        row_index = self._row_index_by_name.get(name, default)
        if not isinstance(row_index, int):
            raise KeyError(f'`{name}` not found in the dictionary and no valid default integer value provided.')
        return row_index
