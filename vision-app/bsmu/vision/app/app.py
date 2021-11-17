from __future__ import annotations

import locale
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide2.QtCore import Signal
from PySide2.QtWidgets import QApplication

from bsmu.vision.app.plugin_manager import PluginManager
from bsmu.vision.core.config.uniter import ConfigUniter
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import List


# CONFIG_FILE_PATH = (Path(__file__).parent / 'App.conf.yaml').resolve()

class App(QApplication):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, argv, child_config_paths: tuple = ()):
        super().__init__(argv)

        # Set to users preferred locale to output correct decimal point (comma or point):
        locale.setlocale(locale.LC_NUMERIC, '')

        self._config_uniter = ConfigUniter(child_config_paths)
        self._united_config = self._config_uniter.unite_configs(Path(__file__).parent.resolve(), 'App.conf.yaml')

        print(f'App started. Prefix: {sys.prefix}')

        # self.config = Config(CONFIG_FILE_PATH)
        # self.config.load()
        # print(f'Config:\n{self.config.data}')

        self._plugin_manager = PluginManager(self)
        self._plugin_manager.plugin_enabled.connect(self.plugin_enabled)
        self._plugin_manager.plugin_disabled.connect(self.plugin_disabled)

        if self._united_config.data is not None:
            self._plugin_manager.enable_plugins(self._united_config.data['plugins'])

    def enabled_plugins(self) -> List[Plugin]:
        return self._plugin_manager.enabled_plugins

    def run(self):
        sys.exit(self.exec_())
