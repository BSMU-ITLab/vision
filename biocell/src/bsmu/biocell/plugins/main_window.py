from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.biocell.plugins.images import icons_rc  # noqa: F401
from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow, MainMenu, MenuBar, FileMenu, EditMenu, \
    ToolsMenu, AlgorithmsMenu, ViewMenu, WindowsMenu, SettingsMenu, HelpMenu

if TYPE_CHECKING:
    from typing import Tuple, Type


class BiocellMenuBar(MenuBar):
    def __init__(
            self,
            menu_order: Tuple[MainMenu] = (
                    FileMenu, EditMenu, ToolsMenu, AlgorithmsMenu, ViewMenu, WindowsMenu, SettingsMenu, HelpMenu)
    ):
        super().__init__(menu_order)


class BiocellMainWindow(MainWindow):
    def __init__(self, title: str = '', icon_file_name: str = '', menu_bar: MenuBar = None):
        super().__init__(title, icon_file_name, BiocellMenuBar() if menu_bar is None else menu_bar)


class BiocellMainWindowPlugin(MainWindowPlugin):
    def __init__(self, main_window_cls: Type[MainWindow] | None = None):
        super().__init__(BiocellMainWindow if main_window_cls is None else main_window_cls)
