from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtGui import QUndoGroup

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import EditMenu

if TYPE_CHECKING:
    from PySide6.QtGui import QAction

    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi


class UndoPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin, mdi_plugin: MdiPlugin):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._undo_manager: UndoManager | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._undo_manager = UndoManager()

    def _enable_gui(self):
        edit_menu = self._main_window.menu(EditMenu)
        edit_menu.addAction(self._undo_manager.create_undo_action(edit_menu))
        edit_menu.addAction(self._undo_manager.create_redo_action(edit_menu))

    def _disable(self):
        self._undo_manager = None

        self._mdi = None
        self._main_window = None

        raise NotImplementedError


class UndoManager(QObject):
    def __init__(self):
        super().__init__()

        self._undo_group = QUndoGroup()

    def create_undo_action(self, parent: QObject, prefix: str = '') -> QAction:
        return self._undo_group.createUndoAction(parent, prefix)

    def create_redo_action(self, parent: QObject, prefix: str = '') -> QAction:
        return self._undo_group.createRedoAction(parent, prefix)
