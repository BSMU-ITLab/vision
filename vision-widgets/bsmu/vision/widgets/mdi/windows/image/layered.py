from __future__ import annotations

from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow


class LayeredImageViewerSubWindow(DataViewerSubWindow):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)