from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QUndoGroup, QUndoStack, QUndoCommand, QKeySequence
from PySide6.QtWidgets import QUndoView, QDockWidget

from bsmu.vision.core.abc import QABCMeta
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import EditMenu, WindowsMenu

if TYPE_CHECKING:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMdiSubWindow

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

        self._undo_view = None
        self._history_dock_widget = None

    @property
    def undo_manager(self) -> UndoManager:
        return self._undo_manager

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._undo_manager = UndoManager(self._mdi, self.config_value('stack_limit', 0))

    def _enable_gui(self):
        edit_menu = self._main_window.menu(EditMenu)

        undo_action = self._undo_manager.create_undo_action(edit_menu)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)

        redo_action = self._undo_manager.create_redo_action(edit_menu)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)

        self._main_window.add_menu_action(WindowsMenu, 'History', self._on_history_action_triggered, checkable=True)

    def _disable(self):
        self._undo_manager.clean()
        self._undo_manager = None

        self._mdi = None
        self._main_window = None

        raise NotImplementedError

    def _on_history_action_triggered(self, checked: bool):
        if checked:
            self._undo_view = QUndoView(self._undo_manager.undo_group)

            self._history_dock_widget = QDockWidget('History')
            self._history_dock_widget.setWidget(self._undo_view)
            self._main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._history_dock_widget)
        else:
            self._main_window.removeDockWidget(self._history_dock_widget)
            self._history_dock_widget = None

            self._undo_view = None


class UndoManager(QObject):
    def __init__(self, mdi: Mdi, stack_limit: int):
        super().__init__()

        self._mdi = mdi
        self._stack_limit = stack_limit

        self._undo_group = QUndoGroup()

        self._undo_stack_by_sub_window: defaultdict[QMdiSubWindow, QUndoStack] = defaultdict(self._create_undo_stack)
        self._mdi.subWindowActivated.connect(self._activate_undo_stack_of_sub_window)
        # TODO: remove undo stacks of closed (deleted) sub windows from |self._undo_stack_by_sub_window|
        self._activate_undo_stack_of_sub_window(self._mdi.activeSubWindow())

    def clean(self):
        self._activate_undo_stack_of_sub_window(None)
        self._mdi.subWindowActivated.disconnect(self._activate_undo_stack_of_sub_window)
        self._undo_stack_by_sub_window = None

        self._undo_group = None
        self._mdi = None

    @property
    def undo_group(self) -> QUndoGroup:
        return self._undo_group

    def create_undo_action(self, parent: QObject, prefix: str = '') -> QAction:
        return self._undo_group.createUndoAction(parent, prefix)

    def create_redo_action(self, parent: QObject, prefix: str = '') -> QAction:
        return self._undo_group.createRedoAction(parent, prefix)

    def push(self, command: UndoCommand):
        self._undo_group.activeStack().push(command)

    def _create_undo_stack(self) -> QUndoStack:
        undo_stack = QUndoStack(self._undo_group)
        undo_stack.setUndoLimit(self._stack_limit)
        return undo_stack

    def _activate_undo_stack_of_sub_window(self, sub_window: QMdiSubWindow | None):
        if sub_window is None:
            self._undo_group.setActiveStack(None)
            return

        undo_stack = self._undo_stack_by_sub_window[sub_window]
        undo_stack.setActive()


class UndoCommandMeta(QABCMeta):
    MAX_ID = 0

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        mcs.MAX_ID += 1
        cls._id = mcs.MAX_ID  # every inherited class type should have unique ID
        return cls


class UndoCommand(QUndoCommand, metaclass=UndoCommandMeta):
    def __init__(self, text: str = '', parent: QUndoCommand = None):
        super().__init__(text, parent)

        # print(f'{self.__class__.__name__} id={self._id}')

    @classmethod
    def command_type_id(cls) -> int:
        return cls._id
