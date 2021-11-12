from __future__ import annotations

from typing import Tuple

from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow, MainMenu, MenuBar, FileMenu, ViewMenu, \
    WindowsMenu, HelpMenu


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
    # setup_info = SetupInfo(name='bsmu-vision-main-window',
    #                        version=Version(0, 0, 1),
    #                        py_modules=('main',))

    def __init__(self, app: App, main_window: MainWindow = None):
        super().__init__(app, BoneAgeMainWindow() if main_window is None else main_window)
