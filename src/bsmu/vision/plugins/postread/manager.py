from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from bsmu.vision.plugins.postread.registry import (
        PostReadConverterRegistryPlugin, PostReadConverterRegistry)


class PostReadConversionManagerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'post_read_converter_registry_plugin':
            'bsmu.vision.plugins.postread.registry.PostReadConverterRegistryPlugin',
    }

    def __init__(self, post_read_converter_registry_plugin: PostReadConverterRegistryPlugin):
        super().__init__()

        self._post_read_converter_registry_plugin = post_read_converter_registry_plugin

        self._post_read_conversion_manager: PostReadConversionManager | None = None

    @property
    def post_read_conversion_manager(self) -> PostReadConversionManager:
        return self._post_read_conversion_manager

    def _enable(self):
        self._post_read_conversion_manager = PostReadConversionManager(
            self._post_read_converter_registry_plugin.processor_registry)

    def _disable(self):
        self._post_read_conversion_manager = None


class PostReadConversionManager(QObject):
    data_converted = Signal(Data)

    def __init__(self, post_read_converter_registry: PostReadConverterRegistry):
        super().__init__()

        self.post_read_converter_registry = post_read_converter_registry

    def can_convert_data(self, data: Data) -> bool:
        return self.post_read_converter_registry.contains(type(data))

    def convert_data(self, data: Data) -> Data:
        converted_data = data
        converter_cls = self.post_read_converter_registry.processor_cls(type(data))
        if converter_cls is not None:
            converter = converter_cls()
            converted_data = converter.convert_data(data)
            self.data_converted.emit(converted_data)
        return converted_data
