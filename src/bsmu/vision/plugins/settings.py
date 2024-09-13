from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from typing import Type

    from bsmu.vision.core.settings import Settings
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class SettingsPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin, settings_cls: Type[Settings]):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._settings_cls = settings_cls
        self._settings: Settings | None = None

    @property
    def settings(self) -> Settings:
        return self._settings

    def _enable(self):
        self._settings = self._settings_cls.from_config(self.config)

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window

    def _disable(self):
        self._main_window = None

        self._settings = None

        raise NotImplemented()
