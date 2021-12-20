from __future__ import annotations

import locale
import sys
import traceback
import warnings
from typing import TYPE_CHECKING

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QApplication

from bsmu.vision.app.plugin_manager import PluginManager
from bsmu.vision.core.config.united import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import List


class App(QApplication, DataFileProvider):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self):
        super().__init__(sys.argv)

        print(f'App started. Prefix: {sys.prefix}')

        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

        # Set to users preferred locale to output correct decimal point (comma or point):
        locale.setlocale(locale.LC_NUMERIC, '')

        warnings.showwarning = warn_with_traceback
        warnings.simplefilter('always')

        self._plugin_manager = PluginManager(self)
        self._plugin_manager.plugin_enabled.connect(self.plugin_enabled)
        self._plugin_manager.plugin_disabled.connect(self.plugin_disabled)

        self._config = UnitedConfig(type(self), App)
        configured_plugins = self._config.value('plugins')
        if configured_plugins is not None:
            self._plugin_manager.enable_plugins(configured_plugins)

    def enabled_plugins(self) -> List[Plugin]:
        return self._plugin_manager.enabled_plugins

    def run(self):
        sys.exit(self.exec_())


def warn_with_traceback(message, category, filename, lineno, file=None, line=None):
    log = file if hasattr(file, 'write') else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))
