from __future__ import annotations

from PySide2.QtCore import QEvent
from PySide2.QtCore import Qt

from bsmu.vision.plugins.tools.viewer.base import ViewerToolPlugin, ViewerTool


class SmartBrushImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(self, app: App):
        super().__init__(app, SmartBrushImageViewerTool, 'Smart Brush', Qt.CTRL + Qt.Key_B)


class SmartBrushImageViewerTool(ViewerTool):
    def __init__(self, viewer: LayeredImageViewer):
        super().__init__(viewer)

    # def activate(self):
    #     print('activate SmartBrushImageViewerTool')

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonPress:
            print('on mouse pressed', event, event.pos())

            # image_coords = self.viewer.pos_to_image_coords(event.pos())
            p_coords = self.viewer.pos_to_image_pixel_coords(event.pos())
            print('p_coords', p_coords)

            return True

        return super().eventFilter(watched_obj, event)
