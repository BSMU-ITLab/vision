from __future__ import annotations

from PySide2.QtCore import QEvent
from PySide2.QtCore import Qt
from skimage import draw

from bsmu.vision.plugins.tools.viewer.base import ViewerToolPlugin, ViewerTool


class SmartBrushImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(self, app: App):
        super().__init__(app, SmartBrushImageViewerTool, 'Smart Brush', Qt.CTRL + Qt.Key_B)


class SmartBrushImageViewerTool(ViewerTool):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)

        self.radius = 20

    # def activate(self):
    #     print('activate SmartBrushImageViewerTool')

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonPress:
            row, col = self.pos_to_image_pixel_coords(event.pos())
            print('row, col', row, col)

            # rr, cc = draw.circle(row, col, self.radius, self.tool_mask.data.shape[:2])
            rr, cc = draw.circle(row, col, self.radius, self.viewer.layers[1].image.array.shape)
            self.viewer.layers[1].image.array[rr, cc] = 1
            self.viewer.layers[1].image.emit_pixels_modified()

            return True

        return super().eventFilter(watched_obj, event)
