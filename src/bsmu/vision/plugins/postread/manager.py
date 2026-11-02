from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from bsmu.vision.core.plugins.processor import ProcessorClsWithSettings
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
        return self._converter_cls_with_settings(data) is not None

    def convert_data(self, data: Data) -> Data:
        converted_data = data
        converter_cls_with_settings = self._converter_cls_with_settings(data)
        if converter_cls_with_settings is not None:
            converter = converter_cls_with_settings.processor_cls()
            converted_data = converter.convert_data(data)
            self.data_converted.emit(converted_data)
        return converted_data

    def _converter_cls_with_settings(self, data: Data) -> ProcessorClsWithSettings | None:
        """Return the first converter that matches `data` by type and can_handle()."""
        candidates = self.post_read_converter_registry.processor_classes_with_settings(type(data))
        if candidates is None:
            return None

        for converter_cls_with_settings in candidates:
            if converter_cls_with_settings.processor_cls.can_handle(data):
                return converter_cls_with_settings

        return None
