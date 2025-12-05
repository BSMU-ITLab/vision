import warnings

from bsmu.vision.core.data.raster import Raster

warnings.warn(
    'The "core.image.image.py" module is deprecated; use "core.data.raster.py" instead.',
    DeprecationWarning,
    stacklevel=2
)


class Image(Raster):
    def __init__(self, *args, **kwargs):
        warnings.warn('`Image` is deprecated; use `Raster` instead.', DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)


class FlatImage(Raster):
    def __init__(self, *args, **kwargs):
        warnings.warn('`FlatImage` is deprecated; use `Raster.raster_2d` instead.', DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)
