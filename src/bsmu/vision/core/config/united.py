from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

if TYPE_CHECKING:
    from typing import Type, List, Any

    from bsmu.vision.core.data_file import DataFileProvider


class UnitedConfig:
    _SENTINEL = object()  # used as default value, when dict does not contain some key
    # (None and empty string can be values, so cannot be used)

    def __init__(self, configurable_cls: Type[DataFileProvider], last_base_cls_to_unite: Type[DataFileProvider]):
        self._configurable_cls = configurable_cls
        self._last_base_cls_to_unite = last_base_cls_to_unite

        self._data = {}

        self._yaml = None

        self._base_united_classes = None
        self._last_united_base_class = None
        self._last_united_base_class_index = -1

    def value(self, key: str, default: Any = None) -> Any:
        result = self._data.get(key, self._SENTINEL)
        while result is self._SENTINEL and self._last_united_base_class != self._last_base_cls_to_unite:
            self._unite_with_next_base_class()
            result = self._data.get(key, self._SENTINEL)
        return default if result is self._SENTINEL else result

    @property
    def base_united_classes(self) -> List[Type[DataFileProvider]]:
        if self._base_united_classes is None:
            # Get list of base classes up to the |self._last_base_cls_to_unite| (including)
            mro = self._configurable_cls.mro()
            last_base_cls_to_unite_index = mro.index(self._last_base_cls_to_unite)
            self._base_united_classes = mro[:last_base_cls_to_unite_index + 1]
        return self._base_united_classes

    @property
    def yaml(self):
        if self._yaml is None:
            self._yaml = YAML()
        return self._yaml

    def _unite_with_next_base_class(self):
        next_base_class_to_unite_index = self._last_united_base_class_index + 1
        next_base_class_to_unite = self.base_united_classes[next_base_class_to_unite_index]

        next_base_class_to_unite_config_file_name = f'{next_base_class_to_unite.__name__}.conf.yaml'
        # next_base_class_to_unite_config_file_name = \
        #     f'{next_base_class_to_unite.__module__}.{next_base_class_to_unite.__name__}.conf.yaml'
        next_base_class_to_unite_config_path = next_base_class_to_unite.data_path(
            'configs', next_base_class_to_unite_config_file_name)

        # TODO: if base class already contains config data, use its data instead of config file loading
        if next_base_class_to_unite_config_path.exists():
            with open(next_base_class_to_unite_config_path) as fp:
                next_base_class_to_unite_config_data = self.yaml.load(fp)
                if next_base_class_to_unite_config_data is None:
                    next_base_class_to_unite_config_data = {}

            for base_class_config_key, base_class_config_value in next_base_class_to_unite_config_data.items():
                if base_class_config_key not in self._data:
                    self._data[base_class_config_key] = base_class_config_value

        self._last_united_base_class_index = next_base_class_to_unite_index
        self._last_united_base_class = next_base_class_to_unite

    def save(self):
        raise NotImplementedError()
