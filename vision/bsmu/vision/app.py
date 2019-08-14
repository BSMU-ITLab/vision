import sys
from pathlib import Path
from typing import Type, List, Union

from PySide2.QtWidgets import QApplication
import yaml

from bsmu.vision.plugin_manager import PluginManager


CONFIG_FILE_PATH = (Path(__file__).parent / 'config.yml').resolve()


# def test():
#     with open(CONFIG_FILE_PATH, 'w') as config_file:
#         yaml.dump({'plugins': ['bsmu.vision_main_window.MainWindowPlugin']}, config_file)


class App(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

        config = self.load_config()
        print('config', config)
        # print(config['plugins'])

        self.plugin_manager = PluginManager(self)

        if config is not None:
            self.plugin_manager.enable_plugins(config['plugins'])

        # exit() ###
        # self.aboutToQuit.connect(self.save_config)

    def enable_plugin(self, full_name: str):
        return self.plugin_manager.enable_plugin(full_name)

    def load_config(self):
        config = None
        print('config path', CONFIG_FILE_PATH.absolute())
        if CONFIG_FILE_PATH.exists():
            with open(CONFIG_FILE_PATH, 'r') as config_file:
                config = yaml.safe_load(config_file)
        return config

    def save_config(self):
        print('save_config')

        with open(CONFIG_FILE_PATH, 'w') as config_file:
            yaml.dump(self.plugin_manager.plugins, config_file)

    def run(self):
        sys.exit(self.exec_())
