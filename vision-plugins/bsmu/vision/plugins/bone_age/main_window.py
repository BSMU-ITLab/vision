from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow, MainMenu, MenuBar, FileMenu, ViewMenu, \
    WindowsMenu, HelpMenu

if TYPE_CHECKING:
    from typing import Tuple, Type


class AtlasMenu(MainMenu):
    name = 'Atlas'


class TableMenu(MainMenu):
    name = 'Table'


class BoneAgeMenuBar(MenuBar):
    def __init__(self, menu_order: Tuple[MainMenu] = (FileMenu, ViewMenu, TableMenu, AtlasMenu, WindowsMenu, HelpMenu)):
        super().__init__(menu_order)


class BoneAgeMainWindow(MainWindow):
    def __init__(self, title: str = '', menu_bar: MenuBar = None):
        super().__init__(title, BoneAgeMenuBar() if menu_bar is None else menu_bar)


class BoneAgeMainWindowPlugin(MainWindowPlugin):
    def __init__(self, main_window_cls: Type[MainWindow] | None = None):
        super().__init__(BoneAgeMainWindow if main_window_cls is None else main_window_cls)
