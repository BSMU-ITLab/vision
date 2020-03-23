from __future__ import annotations

from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow


class LayeredImageViewerSubWindow(DataViewerSubWindow):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)

    def update_window_title(self):
        title = self.viewer.active_displayed_layer.image_path_name if self.viewer.data.path is None \
            else self.viewer.data_path_name
        self.setWindowTitle(title)


class VolumeSliceImageViewerSubWindow(LayeredImageViewerSubWindow):
    def __init__(self, viewer: VolumeSliceImageViewer):
        super().__init__(viewer)
