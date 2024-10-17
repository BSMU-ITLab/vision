from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.config import UnitedConfig
from bsmu.vision.core.data_file import DataFileProvider

if TYPE_CHECKING:
    from typing import Any


class Plugin(QObject, DataFileProvider):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY: dict = {}

    enabling = Signal(QObject)  # Have to be a Plugin instead of QObject, but the Plugin is not defined yet
    enabled = Signal(QObject)  # Same as above
    disabling = Signal(QObject)  # Same as above
    disabled = Signal(QObject)  # Same as above

    def __init__(self):
        super().__init__()

        self.config = UnitedConfig(type(self), Plugin, False)
        # TODO: plugin can contain |config_path| field (if some plugin use different place or name for config file)

        self._dependency_plugin_by_key: dict = {}

        self._log_action('inited')

    def __del__(self):
        self._log_action('deleted')

    @classmethod
    @property
    def default_dependency_plugin_full_name_by_key(cls) -> dict:
        return cls._DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY

    @property
    def dependency_plugin_by_key(self) -> dict:
        return self._dependency_plugin_by_key

    @dependency_plugin_by_key.setter
    def dependency_plugin_by_key(self, value: dict):
        self._dependency_plugin_by_key = value

    def enable(self, enable_gui: bool):
        self.enabling.emit(self)
        self._enable()
        if enable_gui:
            self._enable_gui()
        self._log_action('enabled')
        self.enabled.emit(self)

    def _enable(self):
        pass

    def _enable_gui(self):
        pass

    def disable(self):
        self._log_action('disabling')
        self.disabling.emit(self)
        self._disable()
        self.disabled.emit(self)

    def _disable(self):
        pass

    def config_value(self, key: str, default: Any = None) -> Any:
        return self.config.value(key, default)

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def full_name(cls) -> str:
        return f'{cls.__module__}.{cls.__qualname__}'

    @classmethod
    def _log_action(cls, action_str: str):
        logging.info(f'Plugin {action_str}:\t{cls.name()}')
