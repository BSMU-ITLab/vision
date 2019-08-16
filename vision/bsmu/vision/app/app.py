import sys
from pathlib import Path

from PySide2.QtCore import Signal
from PySide2.QtWidgets import QApplication

from bsmu.vision.app.config import Config
from bsmu.vision.app.plugin import Plugin
from bsmu.vision.app.plugin_manager import PluginManager


CONFIG_FILE_PATH = (Path(__file__).parent / 'App.cfg.yaml').resolve()


class App(QApplication):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, argv):
        super().__init__(argv)

        print(f'App started. Prefix: {sys.prefix}')

        self.config = Config(CONFIG_FILE_PATH)
        self.config.load()
        print(f'Config:\n{self.config.data}')

        self.plugin_manager = PluginManager(self)
        self.plugin_manager.plugin_enabled.connect(self.plugin_enabled)
        self.plugin_manager.plugin_disabled.connect(self.plugin_disabled)

        if self.config.data is not None:
            self.plugin_manager.enable_plugins(self.config.data['plugins'])

        # self.aboutToQuit.connect(self.config.config)

    def enable_plugin(self, full_name: str):
        return self.plugin_manager.enable_plugin(full_name)

    def enabled_plugins(self):
        return self.plugin_manager.enabled_plugins

    def run(self):
        sys.exit(self.exec_())
