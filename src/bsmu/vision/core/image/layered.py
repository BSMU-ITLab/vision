import warnings
from pathlib import Path

from bsmu.vision.core.data.layered import LayeredData
from bsmu.vision.core.layers import RasterLayer

warnings.warn(
    'The "core.image.layered.py" module is deprecated; use "core.layers.layer.py" instead.',
    DeprecationWarning,
    stacklevel=2
)

class ImageLayer(RasterLayer):
    def __init__(self, *args, **kwargs):
        warnings.warn('`ImageLayer` is deprecated; use `RasterLayer` instead.', DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)


class LayeredImage(LayeredData):
    def __init__(self, path: Path = None):
        warnings.warn('`LayeredImage` is deprecated; use `LayeredData` instead.', DeprecationWarning, stacklevel=2)
        super().__init__(path)
