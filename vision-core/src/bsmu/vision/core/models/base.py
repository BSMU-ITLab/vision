from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from typing import Any, Sequence, Type


class ObjectParameter(QObject):
    NAME = ''

    UNKNOWN_VALUE_STR: str = '?'

    value_changed = Signal(object)

    def __init__(self, value: Any = None):
        super().__init__()

        self._value = value

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, value: Any):
        if self._value != value:
            self._value = value
            self.value_changed.emit(self._value)

    def value_str(self) -> str:
        return ObjectParameter.value_to_str(self._value)

    @classmethod
    def value_to_str(cls, value: float | None) -> str:
        if value is None:
            return cls.UNKNOWN_VALUE_STR

        return f'{value:.2f}' if isinstance(value, (float, np.single)) else str(value)


class Connection:
    def __init__(self, signal, handler):
        self._signal = signal
        self._handler = handler

        self._signal.connect(self._handler)

    def disconnect(self):
        self._signal.disconnect(self._handler)


class ObjectRecord(QObject):
    parameter_added = Signal(ObjectParameter)
    parameter_value_changed = Signal(ObjectParameter)

    def __init__(self, parameters: Sequence[ObjectParameter] = ()):
        super().__init__()

        self._parameters = []
        self._parameter_by_type = {}
        for parameter in parameters:
            self.add_parameter(parameter)

    def parameter_by_type(self, parameter_type: Type[ObjectParameter] | None) -> ObjectParameter | None:
        return self._parameter_by_type.get(parameter_type)

    def parameter_value_by_type(self, parameter_type: Type[ObjectParameter] | None) -> Any:
        parameter = self.parameter_by_type(parameter_type)
        return parameter and parameter.value

    def parameter_value_str_by_type(self, parameter_type: Type[ObjectParameter] | None) -> str:
        return ObjectParameter.value_to_str(self.parameter_value_by_type(parameter_type))

    def add_parameter(self, parameter: ObjectParameter):
        assert type(parameter) not in self._parameter_by_type, 'Parameter with such type already exists'
        self._parameters.append(parameter)
        self._parameter_by_type[type(parameter)] = parameter
        self.parameter_added.emit(parameter)
        parameter.value_changed.connect(partial(self._on_parameter_value_changed, parameter))

    def add_parameter_or_modify_value(self, parameter: ObjectParameter) -> ObjectParameter:
        existed_parameter = self.parameter_by_type(type(parameter))
        if existed_parameter is None:
            self.add_parameter(parameter)
        else:
            existed_parameter.value = parameter.value
            parameter = existed_parameter
        return parameter

    def create_connection(self, signal, slot) -> Connection:
        handler = partial(slot, self)
        return Connection(signal, handler)

    def _on_parameter_value_changed(self, parameter: ObjectParameter, value: Any):
        self.parameter_value_changed.emit(parameter)

    @staticmethod
    def _value_str(value: float | None) -> str:
        return ObjectParameter.value_to_str(value)


def positive_list_insert_index(some_list: list, index: int | None) -> int:
    """
    :param some_list: list to insert some element into |index|
    :param index: index to insert element in the |some_list| which can be negative
    (to insert the element into position from the end of the list),
    or can be None (to insert some element into the end of the list).
    :return: positive not None index for list.insert.
    """
    list_len = len(some_list)
    if index is None or index > list_len:
        index = list_len
    elif index < 0:
        index += list_len
        index = max(index, 0)
    return index


def positive_list_remove_index(some_list: list, index: int | None) -> int:
    """
    :param some_list: list to remove some element by |index|
    :param index: index to remove element in the |some_list| which can be negative
    (to remove an element from the end of the list),
    or can be None (to remove the last element of the list).
    :return: positive not None index for del list[index].
    """
    list_len = len(some_list)
    if index is None or index > list_len:
        index = list_len - 1
    elif index < 0:
        index += list_len
        index = max(index, 0)
    return index
