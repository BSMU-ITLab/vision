from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, TypeVar, get_type_hints
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

if TYPE_CHECKING:
    from pathlib import Path

Self = TypeVar('Self', bound='Config')  # Use `from typing import Self` in Python 3.11


@dataclass
class Config:
    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> Self:
        SENTINEL = object()
        field_name_to_config_value: dict[str, Any] = {}
        # Get actual type hints for the fields, resolving forward references. See:
        # https://stackoverflow.com/questions/55937859/dataclasses-field-doesnt-resolve-type-annotation-to-actual-type
        type_hints = get_type_hints(cls)
        for field in fields(cls):
            field_name = field.name
            if (config_value := config_dict.get(field_name, SENTINEL)) == SENTINEL:
                continue

            # Do not use field.type, because it can contain string instead of actual resolved type.
            field_type = type_hints[field_name]
            # Check if config_value type is not the same as field_type.
            if type(config_value) != field_type:
                # If config_value is a dictionary and the field_type is a subclass of Config,
                # then recursively call from_dict to create a nested Config object.
                if isinstance(config_value, dict) and issubclass(field_type, Config):
                    config_value = field_type.from_dict(config_value)
                else:
                    # Convert config_value to field_type by calling its constructor.
                    # This is useful, e.g. to create Path object from a string.
                    config_value = field_type(config_value)

            field_name_to_config_value[field_name] = config_value

        return cls(**field_name_to_config_value)

    def save_to_yaml(self, file_path: Path):
        yaml = YAML()
        with open(file_path, 'w') as file:
            yaml.dump(asdict(self), file)
