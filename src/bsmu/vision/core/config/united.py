from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from bsmu.vision.core.freeze import is_app_frozen
from bsmu.vision.core.utils.hierarchy import HierarchyUtils
from bsmu.vision.core.utils.package import PackageUtils

if TYPE_CHECKING:
    from typing import Any, Sequence

    from bsmu.vision.app import App
    from bsmu.vision.core.data_file import DataFileProvider


class UnitedConfig:
    DIR_NAME = 'configs'
    BASE_DIR_NAME = 'base'

    _SENTINEL = object()  # used as default value, when dict does not contain some key
    # (None and empty string can be values, so cannot be used)

    _APP_CLASS: type[App] = None

    def __init__(
            self,
            configurable_cls: type[DataFileProvider],
            last_base_cls_to_unite: type[DataFileProvider],
            include_last_base_cls: bool = True,
    ):
        self._configurable_cls = configurable_cls
        self._last_base_cls_to_unite = last_base_cls_to_unite
        self._include_last_base_cls = include_last_base_cls

        self._data = {}

        self._yaml = None

        self._priority_config_paths = None
        self._last_united_config_index = -1

        self._base_united_classes = None

    def value(self, key: str, default: Any = None) -> Any:
        result = self._data.get(key, self._SENTINEL)
        while result is self._SENTINEL and not self._is_fully_united():
            self._unite_with_next_config()
            result = self._data.get(key, self._SENTINEL)
        return default if result is self._SENTINEL else result

    @property
    def full_data(self) -> dict:
        """
        Return the fully united configuration data.

        Unlike `value()`, which lazily loads configs only until the requested key is found,
        this method ensures that *all* configs in the hierarchy are merged before returning.
        Useful when the complete configuration dictionary is needed.
        """
        while not self._is_fully_united():
            self._unite_with_next_config()
        return self._data

    def _is_fully_united(self) -> bool:
        return self._last_united_config_index == len(self.priority_config_paths) - 1

    @classmethod
    def configure_app_class(cls, app_class: type[App]):
        cls._APP_CLASS = app_class

    @property
    def priority_config_paths(self, profile: str = 'default') -> Sequence[Path]:
        if self._priority_config_paths is None:
            self._priority_config_paths = []
            for base_configurable_class in self.base_united_classes:
                configurable_class_app_name = base_configurable_class.first_regular_package_info().name
                configurable_class_full_package_name = PackageUtils.full_package_name(base_configurable_class)
                configurable_class_package_name_excluding_app_name = configurable_class_full_package_name[
                    len(configurable_class_app_name) + len(PackageUtils.MODULE_SEPARATOR):]
                config_file_name_suffix = f'{base_configurable_class.__name__}.conf.yaml'
                config_file_name = (
                    f'{configurable_class_package_name_excluding_app_name}.{config_file_name_suffix}'
                    if configurable_class_package_name_excluding_app_name
                    else config_file_name_suffix
                )

                base_path = Path('')
                for base_app_class in self._APP_CLASS.base_app_classes():
                    config_path = base_app_class.config_dir()
                    if is_app_frozen():
                        config_path /= base_path
                        base_path /= self.BASE_DIR_NAME
                    config_path = config_path / profile / configurable_class_app_name / config_file_name

                    self._priority_config_paths.append(config_path)

                    # Stop when reaching the application where `base_configurable_class` is declared
                    base_app_name = base_app_class.first_regular_package_info().name
                    if configurable_class_app_name == base_app_name:
                        break

        return self._priority_config_paths

    @property
    def exists(self) -> bool:
        for config_path in self.priority_config_paths:
            if config_path.exists():
                return True
        return False

    @property
    def base_united_classes(self) -> Sequence[type[DataFileProvider]]:
        if self._base_united_classes is None:
            # Get list of base classes up to the `self._last_base_cls_to_unite` (optionally including)
            self._base_united_classes = HierarchyUtils.inheritance_hierarchy(
                self._configurable_cls, self._last_base_cls_to_unite, self._include_last_base_cls)
        return self._base_united_classes

    @property
    def yaml(self):
        if self._yaml is None:
            self._yaml = YAML()
        return self._yaml

    def _unite_with_next_config(self):
        next_united_config_index = self._last_united_config_index + 1
        next_united_config_path = self.priority_config_paths[next_united_config_index]

        if next_united_config_path.exists():
            with open(next_united_config_path) as fp:
                next_united_config_data = self.yaml.load(fp)
                if next_united_config_data is None:
                    next_united_config_data = {}

            for config_key, config_value in next_united_config_data.items():
                if config_key not in self._data:
                    self._data[config_key] = config_value

        self._last_united_config_index = next_united_config_index

    def save(self):
        raise NotImplementedError()
