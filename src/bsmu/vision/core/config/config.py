from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, TypeVar, get_type_hints
from typing import TYPE_CHECKING

import numpy as np
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
            raise ValueError(f'Invalid value {value} for {self.__class__.__name__}')

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
            raise ValueError(f'Invalid value {value}')

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
