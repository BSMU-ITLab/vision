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

    def parameter_value_str_by_type(self, parameter_type: Type[ObjectParameter] | None) -> str:
        parameter = self.parameter_by_type(parameter_type)
        parameter_value = parameter and parameter.value
        return ObjectParameter.value_to_str(parameter_value)

    def add_parameter(self, parameter: ObjectParameter):
        assert type(parameter) not in self._parameter_by_type, 'Parameter with such type already exists'
        self._parameters.append(parameter)
        self._parameter_by_type[type(parameter)] = parameter
        self.parameter_added.emit(parameter)
        parameter.value_changed.connect(partial(self._on_parameter_value_changed, parameter))

    def _on_parameter_value_changed(self, parameter: ObjectParameter, value: Any):
        self.parameter_value_changed.emit(parameter)

    @staticmethod
    def _value_str(value: float | None) -> str:
        return ObjectParameter.value_to_str(value)
