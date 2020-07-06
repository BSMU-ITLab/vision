from __future__ import annotations

from typing import Optional, Tuple, Type

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

        # self.main_window.add_menu_action(FileMenu, 'Load', None, None)
        # self.main_window.add_menu_action(FileMenu, 'Export Results', None, None)
        # self.main_window.add_menu_action(AtlasMenu, 'Male', None, None)
        # self.main_window.add_menu_action(AtlasMenu, 'Female', None, None)

    def _enable(self):
        self.main_window.show()

    def _disable(self):
        self.main_window.hide()


class MainWindow(QMainWindow):
    def __init__(self, title: str = '', menu_order: Optional[Tuple[MainMenu]] = None):
        super().__init__()

        self.resize(800, 600)
        self.move(300, 300)
        self.setWindowTitle(title)

        self.menu_bar = MenuBar(menu_order)
        self.setMenuBar(self.menu_bar)

    def add_menu_action(self, menu_type: MenuType, action_name, method, shortcut):
        return self.menu_bar.add_menu_action(menu_type, action_name, method, shortcut)


class MainMenu(QMenu):
    name = ''

    def __init__(self):
        super().__init__(self.name)


class FileMenu(MainMenu):
    name = 'File'


class ViewMenu(MainMenu):
    name = 'View'


class ToolsMenu(MainMenu):
    name = 'Tools'


class AlgorithmsMenu(MainMenu):
    name = 'Algorithms'


# class AtlasMenu(MainMenu):
#     name = 'Atlas'
#

class HelpMenu(MainMenu):
    name = 'Help'


class MenuBar(QMenuBar):
    def __init__(self, menu_order: Optional[Tuple[MainMenu]] = None):
        super().__init__()

        self._menu_order = menu_order \
            if menu_order is not None else (FileMenu, ViewMenu, ToolsMenu, AlgorithmsMenu, HelpMenu)
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

    def menu(self, menu_type: Type[MainMenu], add_nonexistent: bool = True) -> Optional[MainMenu]:
        menu = self._ordered_added_menus.get(self._menu_order_index(menu_type))
        if menu is None and add_nonexistent:
            menu = self.add_menu(menu_type)
        return menu

    def add_menu_action(self, menu_type: Type[MainMenu], action_name, method, shortcut) -> QAction:
        return self.menu(menu_type).addAction(action_name, method, shortcut)

    def _menu_order_index(self, menu_type: Type[MainMenu]) -> int:
        return self._menus_order_indexes[menu_type]
