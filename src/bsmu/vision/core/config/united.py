from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from bsmu.vision.core.utils.package import PackageUtils

if TYPE_CHECKING:
    from typing import Any, Sequence

    from bsmu.vision.app import App
    from bsmu.vision.core.data_file import DataFileProvider


class UnitedConfig:
    _SENTINEL = object()  # used as default value, when dict does not contain some key
    # (None and empty string can be values, so cannot be used)

    _APP_HIERARCHY: Sequence[type[App]] = None

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
        while result is self._SENTINEL and self._last_united_config_index != len(self.priority_config_paths) - 1:
            self._unite_with_next_config()
            result = self._data.get(key, self._SENTINEL)
        return default if result is self._SENTINEL else result

    @staticmethod
    def inheritance_hierarchy(cls: type, base_cls: type, include_base_cls: bool = True) -> Sequence[type]:
        """
        Returns the sequence of classes representing the inheritance hierarchy
        from the given class up to and optionally including the specified base class.
        """
        mro = cls.mro()
        base_cls_index = mro.index(base_cls)
        last_cls_index = base_cls_index + 1 if include_base_cls else base_cls_index
        return mro[:last_cls_index]

    @classmethod
    def configure_app_hierarchy(cls, app_cls: type[App], base_app_cls: type[App]):
        cls._APP_HIERARCHY = cls.inheritance_hierarchy(app_cls, base_app_cls)

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

                for base_app_class in self._APP_HIERARCHY:
                    config_path = (base_app_class.first_regular_package_info().path / 'configs' / profile
                                   / configurable_class_app_name / config_file_name)
                    self._priority_config_paths.append(config_path)

                    # Stop when reaching the application where `base_configurable_class` is declared
                    base_app_name = base_app_class.first_regular_package_info().name
                    if configurable_class_app_name == base_app_name:
                        break

        return self._priority_config_paths

    @property
    def base_united_classes(self) -> Sequence[type[DataFileProvider]]:
        if self._base_united_classes is None:
            # Get list of base classes up to the `self._last_base_cls_to_unite` (optionally including)
            self._base_united_classes = self.inheritance_hierarchy(
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
