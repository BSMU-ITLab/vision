from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow, MenuBar, FileMenu, ViewMenu, ToolsMenu, \
    WindowsMenu, HelpMenu

if TYPE_CHECKING:
    from bsmu.vision.app import App
    from bsmu.vision.plugins.windows.main import MainMenu


class RetinalFundusMenuBar(MenuBar):
    def __init__(self, menu_order: Tuple[MainMenu] = (FileMenu, ViewMenu, ToolsMenu, WindowsMenu, HelpMenu)):
        super().__init__(menu_order)


class RetinalFundusMainWindow(MainWindow):
    def __init__(self, title: str = '', menu_bar: MenuBar = RetinalFundusMenuBar()):
        super().__init__(title, menu_bar)


class RetinalFundusMainWindowPlugin(MainWindowPlugin):
    def __init__(self, app: App, main_window: MainWindow = RetinalFundusMainWindow()):
        super().__init__(app, main_window)
