from __future__ import annotations

from PySide2.QtCore import QEvent
from PySide2.QtCore import Qt

from bsmu.vision.plugins.tools.base import ToolPlugin, Tool
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow


class SmartBrushImageViewerToolPlugin(ToolPlugin):
    def __init__(self, app: App):
        super().__init__(app, SmartBrushImageViewerTool, 'Smart Brush', Qt.CTRL + Qt.Key_B)

        self.mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi

        self.smart_brush_tool = SmartBrushImageViewerTool(self.mdi)


class SmartBrushImageViewerTool(Tool):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self.mdi = mdi

    def activate(self):
        print('activate SmartBrushImageViewerTool')
        for sub_window in self.mdi.subWindowList():
            if not isinstance(sub_window, LayeredImageViewerSubWindow):
                continue

            layered_image_viewer = sub_window.viewer
            layered_image_viewer.viewport().installEventFilter(self)

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonPress:
            print('on mouse pressed', event)
            return True
