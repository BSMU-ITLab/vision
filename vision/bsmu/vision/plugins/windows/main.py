from __future__ import annotations

from enum import IntEnum
from typing import Optional

from PySide2.QtWidgets import QMainWindow, QMenuBar, QMenu
from sortedcontainers import SortedDict

from bsmu.vision.app.plugin import Plugin


class MainWindowPlugin(Plugin):
    # setup_info = SetupInfo(name='bsmu-vision-main-window',
    #                        version=Version(0, 0, 1),
    #                        py_modules=('main',))

    def __init__(self, app: App):
        super().__init__(app)

        self.united_config = self.old_config()

        self.main_window = MainWindow(self.united_config.data['title'])

    def _enable(self):
        self.main_window.show()

    def _disable(self):
        self.main_window.hide()


class MainWindow(QMainWindow):
    def __init__(self, title: str = ''):
        super().__init__()

        self.resize(800, 600)
        self.move(300, 300)
        self.setWindowTitle(title)

        self.menu_bar = MenuBar()
        self.setMenuBar(self.menu_bar)

    def add_menu_action(self, menu_type: MenuType, action_name, method, shortcut):
        return self.menu_bar.add_menu_action(menu_type, action_name, method, shortcut)


class MenuType(IntEnum):
    FILE = 1
    VIEW = 2
    TOOLS = 3
    ALGORITHMS = 4
    HELP = 5


class MenuBar(QMenuBar):
    def __init__(self):
        super().__init__()

        self._menus = SortedDict()

    def add_menu(self, menu_type: MenuType) -> QMenu:
        menu = QMenu(menu_type.name.title())
        self._menus[menu_type] = menu

        menu_index = self._menus.index(menu_type)
        # If the menu is the last one
        if menu_index == len(self._menus) - 1:
            self.addMenu(menu)
        else:
            next_menu_index = menu_index + 1
            next_menu = self._menus.peekitem(next_menu_index)[1]
            self.insertMenu(next_menu.menuAction(), menu)

        return menu

    def menu(self, menu_type: MenuType, add_nonexistent: bool = True) -> Optional[QMenu]:
        menu = self._menus.get(menu_type)
        if menu is None and add_nonexistent:
            menu = self.add_menu(menu_type)
        return menu

    def add_menu_action(self, menu_type: MenuType, action_name, method, shortcut) -> QAction:
        return self.menu(menu_type).addAction(action_name, method, shortcut)
