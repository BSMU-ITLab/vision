from __future__ import annotations

import warnings

from bsmu.vision.widgets.actors.layer import RasterLayerActor
from bsmu.vision.widgets.viewers.layered import LayeredDataViewer


warnings.warn(
    'The "widgets.viewers.image.layered.layered.py" module is deprecated; use "widgets.viewers.layered.py" instead.',
    DeprecationWarning,
    stacklevel=2,
)


class ImageLayerView(RasterLayerActor):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            '`ImageLayerView` is deprecated; use `RasterLayerActor` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class LayeredImageViewer(LayeredDataViewer):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            '`LayeredImageViewer` is deprecated; use `LayeredDataViewer` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
