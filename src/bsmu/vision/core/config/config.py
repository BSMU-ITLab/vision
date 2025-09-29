from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import get_args, get_origin, get_type_hints, Union, TYPE_CHECKING

import numpy as np
from ruamel.yaml import YAML

if TYPE_CHECKING:
    from typing import Any, Self, Type


_SENTINEL: object = object()

# Define the permissible source types that can be cast to the specified target types.
# The keys are the target types, and the values are the unions of source types
# that can be safely cast to the corresponding key type.
_TARGET_CASTING_TO_SOURCE_TYPES: dict[Type, Type | UnionType] = {
    float: int,
    Path: str,
}


@dataclass
class Config:
    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> Self:
        field_name_to_config_value: dict[str, Any] = {}
        # Get actual type hints for the fields, resolving forward references. See:
        # https://stackoverflow.com/questions/55937859/dataclasses-field-doesnt-resolve-type-annotation-to-actual-type
        type_hints = get_type_hints(cls)
        for field in fields(cls):
            field_name = field.name
            if (config_value := config_dict.get(field_name, _SENTINEL)) is _SENTINEL:
                continue

            # Do not use field.type, because it can contain string instead of actual resolved type.
            field_type = type_hints[field_name]

            origin_field_type = get_origin(field_type)
            if origin_field_type in (UnionType, Union):
                # Iterate through individual types from the UnionType
                # and try to find a suitable one to convert the `config_value`
                is_converted = False
                for union_member_type in get_args(field_type):
                    config_value, is_converted = cls._converted_value_to_type(config_value, union_member_type)
                    if is_converted:
                        break
                if not is_converted:
                    raise ValueError(
                        f"Cannot convert {config_value} to any type from {field_type} "
                        f"for field name {field_name!r} of {cls}")
            else:
                config_value, is_converted = cls._converted_value_to_type(config_value, field_type)
                if not is_converted:
                    raise ValueError(
                        f"Cannot convert {config_value} to {field_type} for field name {field_name!r} of {cls}")

            field_name_to_config_value[field_name] = config_value

        return cls(**field_name_to_config_value)

    @classmethod
    def _converted_value_to_type(cls, value: Any, type_: Type) -> tuple[Any, bool]:
        if isinstance(value, type_):
            return value, True

        if issubclass(type_, ValueWrapper):
            if type_.can_wrap(value):
                return type_(value), True
            else:
                return value, False

        # If `value` is a dictionary and the `type_` is a subclass of Config,
        # then recursively call from_dict to create a nested Config object.
        if isinstance(value, dict) and issubclass(type_, Config):
            return type_.from_dict(value), True

        if isinstance(value, (str, int)) and issubclass(type_, Enum):
            try:
                if isinstance(value, str):
                    return type_[value.upper()], True
                return type_(value), True
            except (ValueError, KeyError):
                return value, False

        # Try to cast `value` to `type_` according to the `_TARGET_CASTING_TO_SOURCE_TYPES`.
        for target_type, source_type in _TARGET_CASTING_TO_SOURCE_TYPES.items():
            if issubclass(type_, target_type) and isinstance(value, source_type):
                return type_(value), True

        return value, False

    def save_to_yaml(self, file_path: Path):
        yaml = YAML()
        with open(file_path, 'w') as file:
            yaml.dump(asdict(self), file)


class ValueWrapper:
    """Base class for types that can validate and wrap raw config values."""

    @classmethod
    def can_wrap(cls, value: Any) -> bool:
        raise NotImplementedError


class NamesOrAll(ValueWrapper):
    """
    Represents either a sequence of strings or the keyword 'all'.
    """
    ALL_KEYWORD = 'all'

    def __init__(self, value: str | Sequence[str]):
        match value:
            case self.ALL_KEYWORD:
                self._names: Sequence[str] | None = None
            case Sequence() if not isinstance(value, str):
                self._names = value
            case _:
                raise ValueError(
                    f"Invalid value {value!r} for {self.__class__.__name__}. "
                    f"Expected 'all' or a sequence of strings."
                )

    @classmethod
    def all(cls) -> Self:
        return cls(value=cls.ALL_KEYWORD)

    @classmethod
    def empty(cls) -> Self:
        return cls(value=())

    @classmethod
    def from_names(cls, names: Sequence[str]) -> Self:
        return cls(value=names)

    @classmethod
    def can_wrap(cls, value: Any) -> bool:
        return (
                value == cls.ALL_KEYWORD
                or (isinstance(value, Sequence) and not isinstance(value, str)
                    and all(isinstance(x, str) for x in value))
        )

    @property
    def names(self) -> Sequence[str] | None:
        return self._names

    @property
    def is_all(self) -> bool:
        return self._names is None

    def __contains__(self, name: str) -> bool:
        return True if self._names is None else name in self._names

    def __repr__(self) -> str:
        if self.is_all:
            return f"{self.__class__.__name__}('all')"
        return f"{self.__class__.__name__}({list(self._names)!r})"


class IntList:
    """
    A class to represent a list of integers or a range of integers.

    This class can be initialized with a list of integers, a dictionary representing a range,
    or a string 'all' to represent an infinite range of integers.

    Start value of range is included, stop value is excluded.

    Examples:
        # Example 1: Initialize with a list of integers
        int_list = IntList([1, 2, 3, 4, 5])
        print(3 in int_list)  # Output: True
        print(6 in int_list)  # Output: False

        # Example 2: Initialize with a dictionary representing a range
        int_list = IntList({'start': 1, 'stop': 6})
        print(3 in int_list)  # Output: True
        print(6 in int_list)  # Output: False

        # Example 3: Initialize to represent all integers
        int_list = IntList('all')
        print(3 in int_list)  # Output: True
        print(-1 in int_list) # Output: True
        print('a' in int_list) # Raises ValueError

        # Example 4: Invalid initialization
        try:
            int_list = IntList(100)
        except ValueError as e:
            print(e)  # Output: Invalid value 100 for IntList
    """
    def __init__(self, value: list | str | dict):
        if value == 'all':
            self._values = None  # represents all integers
        elif isinstance(value, list):
            self._values = value
        elif isinstance(value, dict):
            self._values = range(value['start'], value['stop'])
        else:
            raise ValueError(f"Invalid value {value} for {self.__class__.__name__}")

    @property
    def values(self) -> list[int] | range | None:
        return self._values

    @property
    def contains_all_values(self) -> bool:
        return self._values is None

    def __contains__(self, value: int):
        """
        Returns True if the given integer is contained within the list or range.
        If the class instance represents all integers, it always returns True.
        """
        if not isinstance(value, int):
            raise ValueError(f"Invalid value {value}")

        return True if self._values is None else value in self._values

    def elements_in_list_mask(self, array: np.ndarray) -> np.ndarray:
        """
        Returns a boolean array where each element indicates whether the corresponding
        element in the input array is contained within the IntList.
        """
        if self.contains_all_values:
            # Returns an array of True values
            return np.ones(array.shape, dtype=bool)
        elif isinstance(self._values, range):
            # The next check is usually faster for range, than using np.isin
            return (array >= self._values.start) & (array < self._values.stop)
        else:
            return np.isin(array, self._values)
