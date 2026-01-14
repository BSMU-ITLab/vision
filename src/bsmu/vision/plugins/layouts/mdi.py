from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject

from bsmu.vision.core.plugins import Plugin
from bsmu.vision.widgets.viewers.layered import LayeredDataViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.doc_interfaces.mdi import Mdi
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.core.data import Data
    from bsmu.vision.widgets.mdi.windows.data import DataViewerSubWindow


class MdiLayoutPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'data_visualization_manager_plugin': 'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
    }

    def __init__(self, data_visualization_manager_plugin: DataVisualizationManagerPlugin):
        super().__init__()

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager | None = None

        self._mdi_layout: MdiLayout | None = None

    def _enable(self):
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._mdi_layout = MdiLayout(self._data_visualization_manager.mdi)

        self._data_visualization_manager.data_visualized.connect(self._mdi_layout.lay_out_data_sub_windows)

    def _disable(self):
        self._data_visualization_manager.data_visualized.disconnect(self._mdi_layout.lay_out_data_sub_windows)

        self._mdi_layout = None


class MdiLayout(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self.mdi = mdi

    def lay_out_data_sub_windows(self, data: Data, sub_windows: DataViewerSubWindow):
        mdi_rect = self.mdi.rect()

        n_sub_windows = len(sub_windows)
        if n_sub_windows == 1:
            sub_window = sub_windows[0]
            sub_window.setGeometry(mdi_rect)
            sub_window.showMaximized()
        elif n_sub_windows == 3:
            layered_image_viewers = [sub_window.viewer for sub_window in sub_windows
                                     if isinstance(sub_window.viewer, LayeredDataViewer)]
            best_resolution_viewer = self.find_best_resolution_viewer(layered_image_viewers)
            best_resolution_sub_window = next(sub_window for sub_window in sub_windows
                                              if sub_window.viewer == best_resolution_viewer)
            other_sub_windows = [sub_window for sub_window in sub_windows
                                 if sub_window.viewer != best_resolution_viewer]

            x_border_anchor = 0.65
            y_border_anchor = 0.5
            best_resolution_sub_window.layout_anchors = np.array([[0, 0], [x_border_anchor, 1]])
            other_sub_windows[0].layout_anchors = np.array([[x_border_anchor, 0], [1, y_border_anchor]])
            other_sub_windows[1].layout_anchors = np.array([[x_border_anchor, y_border_anchor], [1, 1]])

            for sub_window in sub_windows:
                sub_window.lay_out_to_anchors()

    def find_best_resolution_viewer(self, layered_image_viewers: list[LayeredDataViewer]):
        best_resolution_viewer = None
        best_resolution = 0
        for viewer in layered_image_viewers:
            flat_image_shape = viewer.active_layer_actor.flat_image.array.shape
            resolution = flat_image_shape[0] * flat_image_shape[1]
            if resolution > best_resolution:
                best_resolution = resolution
                best_resolution_viewer = viewer
        return best_resolution_viewer
