from __future__ import annotations

from bsmu.vision.tools.viewer.image.layered import LayeredImageViewerTool


class SmartBrushImageViewerTool(LayeredImageViewerTool):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)
