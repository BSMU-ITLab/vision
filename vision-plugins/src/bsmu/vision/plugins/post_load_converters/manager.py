from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Signal

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.data import Data

if TYPE_CHECKING:
    from bsmu.vision.plugins.post_load_converters.registry import PostLoadConverterRegistryPlugin, \
        PostLoadConverterRegistry


class PostLoadConversionManagerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'post_load_converter_registry_plugin':
            'bsmu.vision.plugins.post_load_converters.registry.PostLoadConverterRegistryPlugin',
    }

    def __init__(self, post_load_converter_registry_plugin: PostLoadConverterRegistryPlugin):
        super().__init__()

        self._post_load_converter_registry_plugin = post_load_converter_registry_plugin

        self._post_load_conversion_manager: PostLoadConversionManager | None = None

    @property
    def post_load_conversion_manager(self) -> PostLoadConversionManager:
        return self._post_load_conversion_manager

    def _enable(self):
        self._post_load_conversion_manager = PostLoadConversionManager(
            self._post_load_converter_registry_plugin.processor_registry)

    def _disable(self):
        self._post_load_conversion_manager = None


class PostLoadConversionManager(QObject):
    data_converted = Signal(Data)

    def __init__(self, post_load_converter_registry: PostLoadConverterRegistry):
        super().__init__()

        self.post_load_converter_registry = post_load_converter_registry

    def can_convert_data(self, data: Data) -> bool:
        return self.post_load_converter_registry.contains(type(data))

    def convert_data(self, data: Data) -> Data:
        converted_data = data
        converter_cls = self.post_load_converter_registry.processor_cls(type(data))
        if converter_cls is not None:
            converter = converter_cls()
            converted_data = converter.convert_data(data)
            self.data_converted.emit(converted_data)
        return converted_data
