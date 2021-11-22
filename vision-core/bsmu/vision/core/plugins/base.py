from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Signal

from bsmu.vision.core.config.united import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider

if TYPE_CHECKING:
    from typing import Any


class Plugin(QObject, DataFileProvider):
    DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY: dict = {}

    enabling = Signal(QObject)  # Have to be a Plugin instead of QObject, but the Plugin is not defined yet
    enabled = Signal(QObject)  # Same as above
    disabling = Signal(QObject)  # Same as above
    disabled = Signal(QObject)  # Same as above

    def __init__(self):
        super().__init__()

        self.config = UnitedConfig(type(self), Plugin)
        # TODO: plugin can contain |config_path| field (if some plugin use different place or name for config file)

        self._dependency_plugin_by_key: dict = {}

        self._print_action('inited')

    def __del__(self):
        self._print_action('del')

    @property
    def dependency_plugin_by_key(self) -> dict:
        return self._dependency_plugin_by_key

    @dependency_plugin_by_key.setter
    def dependency_plugin_by_key(self, value: dict):
        self._dependency_plugin_by_key = value

    def enable(self):
        self.enabling.emit(self)
        self._enable()
        self._print_action('enabled')
        self.enabled.emit(self)

    def _enable(self):
        pass

    def disable(self):
        self._print_action('disabling')
        self.disabling.emit(self)
        self._disable()
        self.disabled.emit(self)

    def _disable(self):
        pass

    def config_value(self, key: str) -> Any:
        return self.config.value(key)

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def full_name(cls) -> str:
        return f'{cls.__module__}.{cls.__qualname__}'

    @classmethod
    def _print_action(cls, action_str: str):
        print(f'{action_str} {cls.name()} plugin')
