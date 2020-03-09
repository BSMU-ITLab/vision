from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow

if TYPE_CHECKING:
    from PySide2.QtCore import Qt


class ViewerToolPlugin(Plugin):
    def __init__(self, app: App, tool_cls: Type[ViewerTool], action_name: str = '', action_shortcut: Qt.Key = None):
        super().__init__(app)

        self.tool_cls = tool_cls
        self.action_name = action_name
        self.action_shortcut = action_shortcut

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        self.mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi

        self.mdi_tool = MdiViewerTool(self.mdi, self.tool_cls)

    def _enable(self):
        if not self.action_name:
            return

        self.main_window.add_menu_action(MenuType.TOOLS, self.action_name,
                                         self.mdi_tool.activate, self.action_shortcut)

    def _disable(self):
        raise NotImplemented()


class MdiViewerTool(QObject):
    def __init__(self, mdi: Mdi, tool_cls: Type[ViewerTool]):
        super().__init__()

        self.mdi = mdi
        self.tool_csl = tool_cls

        self.sub_windows_viewer_tools = {}  # DataViewerSubWindow: ViewerTool

    def activate(self):
        for sub_window in self.mdi.subWindowList():
            viewer_tool = self._sub_window_viwer_tool(sub_window)
            if viewer_tool is not None:
                viewer_tool.activate()

    def _sub_window_viwer_tool(self, sub_window: DataViewerSubWindow):
        if not isinstance(sub_window, LayeredImageViewerSubWindow):
            return None

        viewer_tool = self.sub_windows_viewer_tools.get(sub_window)
        if viewer_tool is None:
            viewer_tool = self.tool_csl(sub_window.viewer)
            self.sub_windows_viewer_tools[sub_window] = viewer_tool
        return viewer_tool


class ViewerTool(QObject):
    def __init__(self, viewer: DataViewer):
        super().__init__()

        self.viewer = viewer

    def activate(self):
        # self.viewer.viewport().installEventFilter(self)
        print('aCT type', type(self.viewer))
        self.viewer.installEventFilter(self)
