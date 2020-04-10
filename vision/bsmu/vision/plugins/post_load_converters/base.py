from __future__ import annotations

import abc

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin
from bsmu.vision_core.data import Data


class PostLoadConverterPlugin(Plugin):
    def __init__(self, app: App, post_load_converter_cls):
        super().__init__(app)

        self.post_load_converter_cls = post_load_converter_cls


class PostLoadConverterMeta(abc.ABCMeta, type(QObject)):
    _DATA_TYPES = ()

    @property
    def data_types(cls) -> tuple:
        return cls._DATA_TYPES


class PostLoadConverter(QObject, metaclass=PostLoadConverterMeta):
    data_converted = Signal(Data)

    def __init__(self):
        super().__init__()

    @property
    def data_types(self):
        return type(self).data_types

    def convert_data(self, data: Data) -> Data:
        converted_data = self._convert_data(data)
        self.data_converted.emit(converted_data)
        return converted_data

    @abc.abstractmethod
    def _convert_data(self, data: Data) -> Data:
        pass
