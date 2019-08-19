from __future__ import annotations

from bsmu.vision_core.data import Data


class Image(Data):
    def __init__(self, array=None, palette=None, path: Path = None):
        super().__init__(path)

        self.array = array
        self.palette = palette  # for indexed images


class FlatImage(Image):
    def __init__(self, array=None, palette=None, path: Path = None):
        super().__init__(array, palette, path)


class VolumeImage(Image):
    def __init__(self, array=None, palette=None, path: Path = None):
        super().__init__(array, palette, path)
