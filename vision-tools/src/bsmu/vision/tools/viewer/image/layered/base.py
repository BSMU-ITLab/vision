from __future__ import annotations


class LayeredImageViewerTool(DataViewerTool):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)
