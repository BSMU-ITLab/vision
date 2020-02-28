from __future__ import annotations

from bsmu.vision_core.data import Data


class Image(Data):
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None):
        super().__init__(path)

        self.array = array
        self._palette = palette

        self._check_array_palette_matching()

    @property
    def palette(self) -> Palette:
        return self._palette

    @palette.setter
    def palette(self, palette):
        if self._palette != palette:
            self._palette = palette
            self._check_array_palette_matching()

    @property
    def colored_array(self) -> ndarray:
        return self.palette.array[self.array]

    @property
    def colored_premultiplied_array(self) -> ndarray:
        print('colored_premultiplied_array', self.palette.premultiplied_array.shape, self.array.shape)
        print('result', self.palette.premultiplied_array[self.array].shape)
        return self.palette.premultiplied_array[self.array]

    def _check_array_palette_matching(self):
        pass


class FlatImage(Image):
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None):
        super().__init__(array, palette, path)

    def _check_array_palette_matching(self):
        assert (self.palette is None) or (len(self.array.shape) == 2), \
            f'Flat indexed image (shape: {self.array.shape}) (with palette) has to contain no channels'


class VolumeImage(Image):
    def __init__(self, array: ndarray = None, palette: Palette = None, path: Path = None):
        super().__init__(array, palette, path)

    def _check_array_palette_matching(self):
        assert (self.palette is None) or (len(self.array.shape) == 3), \
            f'Volume indexed image (shape: {self.array.shape}) (with palette) has to contain no channels.'
