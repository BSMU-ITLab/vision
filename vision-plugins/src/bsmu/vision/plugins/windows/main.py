from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QMainWindow, QMenuBar, QMenu
from sortedcontainers import SortedDict

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.widgets.images import icons_rc  # noqa: F401

if TYPE_CHECKING:
    from typing import Tuple, Type


class MainMenu(QMenu):
    name = ''

    def __init__(self):
        super().__init__(self.name)


class FileMenu(MainMenu):
    name = 'File'


class ToolsMenu(MainMenu):
    name = 'Tools'


class AlgorithmsMenu(MainMenu):
    name = 'Algorithms'


class ViewMenu(MainMenu):
    name = 'View'


class WindowsMenu(MainMenu):
    name = 'Windows'


class SettingsMenu(MainMenu):
    name = 'Settings'


class HelpMenu(MainMenu):
    name = 'Help'


class MenuBar(QMenuBar):
    def __init__(
            self,
            menu_order: Tuple[MainMenu] = (
                    FileMenu, ToolsMenu, AlgorithmsMenu, ViewMenu, WindowsMenu, SettingsMenu, HelpMenu)
    ):
        super().__init__()

        self._menu_order = menu_order
        self._menus_order_indexes = {menu_type: i for (i, menu_type) in enumerate(self._menu_order)}

        self._ordered_added_menus = SortedDict()  # {order_index: MainMenu class}

    def add_menu(self, menu_type: Type[MainMenu]) -> MainMenu:
        menu = menu_type()
        menu_order_index = self._menu_order_index(menu_type)
        self._ordered_added_menus[menu_order_index] = menu

        menu_index_in_ordered_added_menus = self._ordered_added_menus.index(menu_order_index)
        # If the menu is the last one
        if menu_index_in_ordered_added_menus == len(self._ordered_added_menus) - 1:
            self.addMenu(menu)
        else:
            next_menu_index_in_ordered_added_menus = menu_index_in_ordered_added_menus + 1
            next_menu = self._ordered_added_menus.peekitem(next_menu_index_in_ordered_added_menus)[1]
            self.insertMenu(next_menu.menuAction(), menu)

        return menu

    def menu(self, menu_type: Type[MainMenu], add_nonexistent: bool = True) -> MainMenu | None:
        menu = self._ordered_added_menus.get(self._menu_order_index(menu_type))
        if menu is None and add_nonexistent:
            menu = self.add_menu(menu_type)
        return menu

    def add_menu_action(
            self,
            menu_type: Type[MainMenu],
            action_name,
            method=None,
            shortcut=None,
            checkable: bool = False
    ) -> QAction:
        menu = self.menu(menu_type)
        action = QAction(action_name, menu)
        action.setCheckable(checkable)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(method)
        menu.addAction(action)
        return action

    def _menu_order_index(self, menu_type: Type[MainMenu]) -> int:
        return self._menus_order_indexes[menu_type]


class MainWindow(QMainWindow):
    def __init__(self, title: str = '', icon_file_name: str = '', menu_bar: MenuBar = None):
        super().__init__()

        self.resize(1200, 800)
        self.move(100, 100)

        self.setWindowTitle(title)

        icon = QIcon(icon_file_name)
        self.setWindowIcon(icon)

        self._menu_bar = MenuBar() if menu_bar is None else menu_bar
        self.setMenuBar(self._menu_bar)

    def add_menu_action(
            self,
            menu_type: Type[MainMenu],
            action_name,
            method=None,
            shortcut=None,
            checkable: bool = False
    ) -> QAction:
        return self._menu_bar.add_menu_action(menu_type, action_name, method, shortcut, checkable)

    def menu(self, menu_type: Type[MainMenu], add_nonexistent: bool = True) -> MainMenu | None:
        return self._menu_bar.menu(menu_type, add_nonexistent)


class MainWindowPlugin(Plugin):
    def __init__(self, main_window_cls: Type[MainWindow] | None = None):
        super().__init__()

        self._main_window_cls = MainWindow if main_window_cls is None else main_window_cls
        self._main_window: MainWindow | None = None

    @property
    def main_window(self) -> MainWindow:
        return self._main_window

    def _enable(self):
        title = self.config.value('title', 'Vision')
        icon_file_name = self.config.value('icon_file_name', ':/icons/vision.svg')

        self._main_window = self._main_window_cls(title, icon_file_name)
        self._main_window.setAttribute(Qt.WA_DeleteOnClose)

        self._main_window.show()

    def _disable(self):
        self._main_window.close()
        self._main_window = None
