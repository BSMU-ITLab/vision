from __future__ import annotations

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.united_config import UnitedConfig


class Plugin(QObject):
    DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY: dict = {}

    DATA_DIRS = ['DataDir']
    # setup_info = None

    enabling = Signal(QObject)  # Have to be a Plugin instead of QObject, but the Plugin is not defined yet
    enabled = Signal(QObject)  # Same as above
    disabling = Signal(QObject)  # Same as above
    disabled = Signal(QObject)  # Same as above

    def __init__(self):
        super().__init__()

        self.config = UnitedConfig(self, Plugin)
        # TODO: plugin can contain |config_path| field (if some plugin use different place or name for config file)

        self._dependency_plugin_by_key: dict = {}

        self.print_action('inited')

    def __del__(self):
        self.print_action('del')

    @property
    def dependency_plugin_by_key(self) -> dict:
        return self._dependency_plugin_by_key

    @dependency_plugin_by_key.setter
    def dependency_plugin_by_key(self, value):
        self._dependency_plugin_by_key = value

    def enable(self):
        self.enabling.emit(self)
        self._enable()
        self.print_action('enabled')
        self.enabled.emit(self)

    def _enable(self):
        pass

    def disable(self):
        self.print_action('disabling')
        self.disabling.emit(self)
        self._disable()
        self.disabled.emit(self)

    def _disable(self):
        pass

    def print_action(self, action_str):
        print(f'{action_str} {self.name()} plugin')

    def config_value(self, key: str):
        return self.config.value(key)

    def old_config(self, relative_config_dir=''): #relative_config_file_path=''):
        import sys
        from pathlib import Path
        plugin_dir = Path(sys.modules[self.__module__].__file__).parent
        config_dir = plugin_dir / relative_config_dir

        print('config_dir', config_dir)

        # import inspect
        # plugin_file_path = inspect.getfile(self.__class__)

        # if not relative_config_file_path:
        class_name = self.__class__.__name__
        # print('ccccc', class_name)
        # relative_config_file_path = class_name + '.conf.yaml'
        # full_name = self.__module__ + '.' + class_name
        # print('full_name', full_name)

        config_file_name = class_name + '.conf.yaml'
        config_file_full_name = f'{self.__module__}.{config_file_name}'

        united_config = self.app.config_uniter.unite_configs(config_dir, config_file_name, config_file_full_name)
        return united_config

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def full_name(cls) -> str:
        return f'{cls.__module__}.{cls.__qualname__}'
