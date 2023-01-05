from __future__ import annotations

import locale
import sys
import traceback
import warnings
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QCoreApplication
from PySide6.QtWidgets import QApplication

from bsmu.vision.app.plugin_manager import PluginManager
from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.config.united import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.config import OnnxConfig

if TYPE_CHECKING:
    from typing import List


class App(QObject, DataFileProvider):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self):
        super().__init__()

        print(f'App started. Prefix: {sys.prefix}')

        # Set to users preferred locale to output correct decimal point (comma or point):
        locale.setlocale(locale.LC_NUMERIC, '')

        self._config = UnitedConfig(type(self), App)

        self._gui_enabled = self._config.value('enable-gui')
        self._qApp = QApplication(sys.argv) if self._gui_enabled else QCoreApplication(sys.argv)

        ThreadPool.init_executor(self._config.value('max_thread_count'))

        if self._config.value('warn-with-traceback'):
            warnings.showwarning = warn_with_traceback
            warnings.simplefilter('always')

        OnnxConfig.providers = self._config.value('onnx_providers')

        self._plugin_manager = PluginManager(self)
        self._plugin_manager.plugin_enabled.connect(self.plugin_enabled)
        self._plugin_manager.plugin_disabled.connect(self.plugin_disabled)

        configured_plugins = self._config.value('plugins')
        if configured_plugins is not None:
            self._plugin_manager.enable_plugins(configured_plugins)

    @property
    def gui_enabled(self) -> bool:
        return self._gui_enabled

    def enabled_plugins(self) -> List[Plugin]:
        return self._plugin_manager.enabled_plugins

    def run(self):
        sys.exit(self._qApp.exec())


def warn_with_traceback(message, category, filename, lineno, file=None, line=None):
    log = file if hasattr(file, 'write') else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))
