from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML


class UnitedConfig:
    def __init__(self, plugin: Plugin, last_base_plugin_class, config_dir: Path):
        self.plugin = plugin
        self.last_base_plugin_class = last_base_plugin_class
        self.config_dir = config_dir

        self._data = {}

        self._yaml = None

        self._base_plugin_classes = None
        self._last_united_plugin_base_class = None
        self._last_united_plugin_base_class_index = -1

    def value(self, key: str):
        result = self._data.get(key)
        while result is None and self._last_united_plugin_base_class != self.last_base_plugin_class:
            self.unite_with_next_base_class()
            result = self._data.get(key)
        return result

    @property
    def base_plugin_classes(self):
        if self._base_plugin_classes is None:
            # Get list of base classes up to the |last_base_plugin_class|
            plugin_mro = type(self.plugin).mro()
            last_base_plugin_class_index = plugin_mro.index(self.last_base_plugin_class)
            self._base_plugin_classes = plugin_mro[:last_base_plugin_class_index + 1]
        return self._base_plugin_classes

    @property
    def yaml(self):
        if self._yaml is None:
            self._yaml = YAML()
        return self._yaml

    def unite_with_next_base_class(self):
        next_plugin_base_class_index = self._last_united_plugin_base_class_index + 1
        next_plugin_base_class = self.base_plugin_classes[next_plugin_base_class_index]

        next_plugin_base_class_config_dir = Path(sys.modules[next_plugin_base_class.__module__].__file__).parent
        next_plugin_base_class_config_file_name = f'{next_plugin_base_class.__name__}.conf.yaml'
        next_plugin_base_class_config_path = next_plugin_base_class_config_dir / next_plugin_base_class_config_file_name

        # next_plugin_base_class_config_path = \
        #     self.config_dir / f'{next_plugin_base_class.__module__}.{next_plugin_base_class.__name__}.conf.yaml'
        # print('Config path', next_plugin_base_class_config_path)

        # TODO: if base class already contains config data, use its data instead of config file loading
        if next_plugin_base_class_config_path.exists():
            with open(next_plugin_base_class_config_path) as fp:
                base_class_config_data = self.yaml.load(fp)
                if base_class_config_data is None:
                    base_class_config_data = {}

            for base_class_config_key, base_class_config_value in base_class_config_data.items():
                if base_class_config_key not in self._data:
                    self._data[base_class_config_key] = base_class_config_value

        self._last_united_plugin_base_class_index = next_plugin_base_class_index
        self._last_united_plugin_base_class = next_plugin_base_class

    def save(self):
        raise NotImplementedError()
