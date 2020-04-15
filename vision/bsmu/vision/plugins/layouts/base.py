from __future__ import annotations

from typing import List

from PySide2.QtCore import QObject, QRect

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


class MdiLayoutPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager

        self.layout = MdiLayout(self.data_visualization_manager.mdi)

    def _enable(self):
        self.data_visualization_manager.data_visualized.connect(self.layout.lay_out_data_sub_windows)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.layout.lay_out_data_sub_windows)


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
                                     if isinstance(sub_window.viewer, LayeredImageViewer)]
            best_resolution_viewer = self.find_best_resolution_viewer(layered_image_viewers)
            best_resolution_sub_window = next(sub_window for sub_window in sub_windows
                                              if sub_window.viewer == best_resolution_viewer)
            other_sub_windows = [sub_window for sub_window in sub_windows
                                 if sub_window.viewer != best_resolution_viewer]

            best_resolution_sub_window_rect = QRect(mdi_rect)
            best_resolution_sub_window_rect.setWidth(mdi_rect.width() * 0.65)
            best_resolution_sub_window.setGeometry(best_resolution_sub_window_rect)

            top_right_sub_window = other_sub_windows[0]
            bottom_right_sub_window = other_sub_windows[1]

            right_sub_windows_x = best_resolution_sub_window_rect.width()
            right_sub_windows_width = mdi_rect.width() - right_sub_windows_x
            top_right_sub_window_rect = QRect(right_sub_windows_x, mdi_rect.y(),
                                              right_sub_windows_width, mdi_rect.height() * 0.5)
            top_right_sub_window.setGeometry(top_right_sub_window_rect)

            bottom_right_sub_window_y = top_right_sub_window.height()
            bottom_right_sub_window_height = mdi_rect.height() - bottom_right_sub_window_y
            bottom_right_sub_window_rect = QRect(right_sub_windows_x, bottom_right_sub_window_y,
                                                 right_sub_windows_width, bottom_right_sub_window_height)
            bottom_right_sub_window.setGeometry(bottom_right_sub_window_rect)


    def find_best_resolution_viewer(self, layered_image_viewers: List[LayeredImageViewer]):
        best_resolution_viewer = None
        best_resolution = 0
        for viewer in layered_image_viewers:
            flat_image_shape = viewer.active_layer_view.flat_image.array.shape
            resolution = flat_image_shape[0] * flat_image_shape[1]
            if resolution > best_resolution:
                best_resolution = resolution
                best_resolution_viewer = viewer
        return best_resolution_viewer
