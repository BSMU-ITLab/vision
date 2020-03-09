from __future__ import annotations

from PySide2.QtWidgets import QMainWindow, QMenuBar

from bsmu.vision.app.plugin import Plugin

from enum import Enum


class MainWindowPlugin(Plugin):
    # setup_info = SetupInfo(name='bsmu-vision-main-window',
    #                        version=Version(0, 0, 1),
    #                        py_modules=('main',))

    def __init__(self, app: App):
        super().__init__(app)

        self.united_config = self.config()

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


class MenuType(Enum):
    FILE = 1
    VIEW = 2
    TOOLS = 3
    HELP = 4


class MenuBar(QMenuBar):
    def __init__(self):
        super().__init__()

        self._menus = {}

        self.add_menu(MenuType.FILE)
        self.add_menu(MenuType.VIEW)
        self.add_menu(MenuType.TOOLS)
        self.add_menu(MenuType.HELP)
        # TODO: It's better to add menus at runtime (if they needed), but we have to keep correct menus order,
        #  using self.insertMenu instead of self.addMenu

    def add_menu(self, menu_type: MenuType):
        menu = self.addMenu(menu_type.name.title())
        # menu.menuAction().setVisible(False) # to hide menu (while no actions)
        self._menus[menu_type] = menu
        return menu

    def menu(self, menu_type: MenuType):
        return self._menus[menu_type]

    def add_menu_action(self, menu_type: MenuType, action_name, method, shortcut):
        return self.menu(menu_type).addAction(action_name, method, shortcut)
