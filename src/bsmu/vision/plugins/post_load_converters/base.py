from __future__ import annotations

import abc

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins.processor.base import ProcessorPlugin


class PostLoadConverterPlugin(ProcessorPlugin):
    def __init__(self, post_load_converter_cls):
        super().__init__(post_load_converter_cls)


class PostLoadConverterMeta(type(QObject), abc.ABCMeta):
    _DATA_TYPES = ()

    @property
    def data_types(cls) -> tuple:
        return cls._DATA_TYPES

    @property
    def processed_keys(cls) -> tuple:
        return cls.data_types


class PostLoadConverter(QObject, metaclass=PostLoadConverterMeta):
    data_converted = Signal(Data)

    def __init__(self):
        super().__init__()

    def convert_data(self, data: Data) -> Data:
        converted_data = self._convert_data(data)
        self.data_converted.emit(converted_data)
        return converted_data

    @abc.abstractmethod
    def _convert_data(self, data: Data) -> Data:
        pass
