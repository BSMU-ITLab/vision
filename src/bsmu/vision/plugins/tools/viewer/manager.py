from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject, QEvent, QElapsedTimer, QCoreApplication
from PySide6.QtGui import QActionGroup

from bsmu.vision.core.plugins.observer import ObserverPlugin
from bsmu.vision.plugins.tools.viewer import ViewerToolPlugin
from bsmu.vision.plugins.windows.main import ToolsMenu

if TYPE_CHECKING:
    from bsmu.vision.plugins.tools.viewer import MdiViewerTool
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class ViewerToolManagerPlugin(ObserverPlugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin):
        super().__init__(ViewerToolPlugin)

        self._main_window_plugin = main_window_plugin

        self._viewer_tool_manager: ViewerToolManager | None = None

    @property
    def viewer_tool_manager(self) -> ViewerToolManager:
        return self._viewer_tool_manager

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._viewer_tool_manager = ViewerToolManager(self._main_window)
        self._main_window.add_menu_action(
            ToolsMenu, self.tr('Uncheck Tool'), self._viewer_tool_manager.deactivate_active_tool, Qt.Key_Escape)

        # We install the filter on app instance instead of the main window
        # because the main window doesn't receive mouse press events from subwindow viewports
        QCoreApplication.instance().installEventFilter(self._viewer_tool_manager)

    def _disable(self):
        self._main_window.removeEventFilter(self._viewer_tool_manager)

        self._viewer_tool_manager.clear()
        self._viewer_tool_manager = None
        self._main_window = None

    def on_observed_plugin_enabled(self, viewer_tool_plugin: ViewerToolPlugin):
        self._viewer_tool_manager.add_viewer_tool_plugin(viewer_tool_plugin)

    def on_observed_plugin_disabling(self, viewer_tool_plugin: ViewerToolPlugin):
        self._viewer_tool_manager.remove_viewer_tool_plugin(viewer_tool_plugin)


class ViewerToolManager(QObject):
    def __init__(self, main_window: MainWindow):
        super().__init__()

        self._main_window = main_window

        self._tool_plugins: set[ViewerToolPlugin] = set()
        self._key_to_tool_plugin: dict[Qt.Key, ViewerToolPlugin] = {}

        self._action_group = QActionGroup(main_window.menu(ToolsMenu))
        self._action_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)

        self._pressed_tool_action_shortcut_key: Qt.Key | None = None
        self._pressed_tool_action_shortcut_timer = QElapsedTimer()
        self._is_mouse_used_during_tool_action_shortcut_being_pressed: bool = False

        self._active_viewer_tool: MdiViewerTool | None = None
        # Long press of a tool shortcut allows to temporarily activate the tool.
        # Upon releasing the shortcut (KeyRelease event), the previous active tool is reactivated.
        self._viewer_tool_temporary_deactivated: MdiViewerTool | None = None

    def add_viewer_tool_plugin(self, viewer_tool_plugin: ViewerToolPlugin):
        self._tool_plugins.add(viewer_tool_plugin)
        # TODO: need to update the `self._key_to_tool_plugin` dict if action shortcut changes in runtime
        if viewer_tool_plugin.action_shortcut is not None:
            self._key_to_tool_plugin[viewer_tool_plugin.action_shortcut] = viewer_tool_plugin

        self._action_group.addAction(viewer_tool_plugin.tool_action)

        viewer_tool = viewer_tool_plugin.mdi_viewer_tool
        if viewer_tool.is_active:
            self._on_viewer_tool_activated(viewer_tool)
        viewer_tool.activating.connect(self._on_viewer_tool_activating)
        viewer_tool.activated.connect(self._on_viewer_tool_activated)
        viewer_tool.deactivated.connect(self._on_viewer_tool_deactivated)

    def remove_viewer_tool_plugin(self, viewer_tool_plugin: ViewerToolPlugin):
        self._tool_plugins.remove(viewer_tool_plugin)
        if viewer_tool_plugin.action_shortcut is not None:
            viewer_tool_plugin_by_action_shortcut = self._key_to_tool_plugin.pop(viewer_tool_plugin.action_shortcut)
            assert viewer_tool_plugin_by_action_shortcut == viewer_tool_plugin, (
                f'Invalid value in the dictionary for key: {viewer_tool_plugin.action_shortcut}.\n'
                f'Expected value: {viewer_tool_plugin}.\n'
                f'Actual value: {viewer_tool_plugin_by_action_shortcut}'
            )

        self._action_group.removeAction(viewer_tool_plugin.tool_action)

        viewer_tool = viewer_tool_plugin.mdi_viewer_tool
        viewer_tool.activating.disconnect(self._on_viewer_tool_activating)
        viewer_tool.activated.disconnect(self._on_viewer_tool_activated)
        viewer_tool.deactivated.disconnect(self._on_viewer_tool_deactivated)

    def clear(self):
        for tool_plugin in self._tool_plugins.copy():
            self.remove_viewer_tool_plugin(tool_plugin)

    def deactivate_active_tool(self):
        if self._active_viewer_tool is not None:
            self._active_viewer_tool.deactivate()

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() in (QEvent.MouseButtonPress, QEvent.Wheel):
            self._is_mouse_used_during_tool_action_shortcut_being_pressed = True

        if watched_obj != self._main_window:
            return super().eventFilter(watched_obj, event)

        # We will not get QEvent.KeyPress events for action shortcuts, so use QEvent.ShortcutOverride instead.
        if event.type() == QEvent.ShortcutOverride and not event.isAutoRepeat():
            pressed_key = event.key()
            viewer_tool_plugin_by_key = self._key_to_tool_plugin.get(pressed_key)
            if viewer_tool_plugin_by_key is not None:
                assert viewer_tool_plugin_by_key.action_shortcut == pressed_key, (
                    'Invalid action shortcut in the dictionary'
                )

                self._viewer_tool_temporary_deactivated = self._active_viewer_tool

                self._pressed_tool_action_shortcut_key = pressed_key
                self._pressed_tool_action_shortcut_timer.start()
                self._is_mouse_used_during_tool_action_shortcut_being_pressed = False

        elif (event.type() == QEvent.KeyRelease
              and event.key() == self._pressed_tool_action_shortcut_key
              and not event.isAutoRepeat()):

            pressing_time = self._pressed_tool_action_shortcut_timer.elapsed()
            if pressing_time > 300 or self._is_mouse_used_during_tool_action_shortcut_being_pressed:
                # Activate previous temporary deactivated tool
                if self._viewer_tool_temporary_deactivated is None:
                    self.deactivate_active_tool()
                else:
                    self._viewer_tool_temporary_deactivated.activate()

            self._pressed_tool_action_shortcut_key = None
            self._pressed_tool_action_shortcut_timer.invalidate()

            self._viewer_tool_temporary_deactivated = None

        return super().eventFilter(watched_obj, event)

    def _on_viewer_tool_activating(self, viewer_tool: MdiViewerTool):
        assert self._active_viewer_tool != viewer_tool, (
            f'Invalid value of `self._active_viewer_tool`: {self._active_viewer_tool}'
        )

        self.deactivate_active_tool()

    def _on_viewer_tool_activated(self, viewer_tool: MdiViewerTool):
        assert self._active_viewer_tool != viewer_tool, (
            f'Invalid value of `self._active_viewer_tool`: {self._active_viewer_tool}'
        )

        self._active_viewer_tool = viewer_tool

    def _on_viewer_tool_deactivated(self, viewer_tool: MdiViewerTool):
        assert self._active_viewer_tool == viewer_tool, (
            f'Invalid value of `self._active_viewer_tool`\n'
            f'Expected value: {viewer_tool}\n'
            f'Actual value: {self._active_viewer_tool}'
        )

        self._active_viewer_tool = None
