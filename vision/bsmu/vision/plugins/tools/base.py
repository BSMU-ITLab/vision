from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType

if TYPE_CHECKING:
    from PySide2.QtCore import Qt


class ToolPlugin(Plugin):
    def __init__(self, app: App, tool_cls: Type[Tool], action_name: str = '', action_shortcut: Qt.Key = None):
        super().__init__(app)

        self.tool_cls = tool_cls
        self.action_name = action_name
        self.action_shortcut = action_shortcut

        self.tool = None

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window

    def _enable(self):
        if not self.action_name:
            return

        self.main_window.add_menu_action(MenuType.TOOLS, self.action_name, self._activate_tool, self.action_shortcut)

    def _disable(self):
        raise NotImplemented()

    def _create_tool(self):
        self.tool = self.tool_cls()

    def _activate_tool(self):
        if self.tool is None:
            self._create_tool()

        self.tool.activate()


class Tool(QObject):
    def __init__(self):
        super().__init__()

    def activate(self):
        pass
