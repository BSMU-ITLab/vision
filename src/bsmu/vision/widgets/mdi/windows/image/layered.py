from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.widgets.mdi.windows.data import DataViewerSubWindow

if TYPE_CHECKING:
    from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer
    from bsmu.vision.widgets.viewers.image.layered.slice import VolumeSliceImageViewer


class LayeredImageViewerSubWindow(DataViewerSubWindow):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)

    @property
    def layered_image_viewer(self) -> LayeredImageViewer:
        return self.viewer

    def update_window_title(self):
        title = self.viewer.active_layer_view.data_path_name if self.viewer.data.path is None \
            else self.viewer.data_path_name
        self.setWindowTitle(title)


class VolumeSliceImageViewerSubWindow(LayeredImageViewerSubWindow):
    def __init__(self, viewer: VolumeSliceImageViewer):
        super().__init__(viewer)
