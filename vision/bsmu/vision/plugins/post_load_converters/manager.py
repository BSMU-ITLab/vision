from __future__ import annotations

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.core.data import Data


class PostLoadConversionManagerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        post_load_converter_registry = app.enable_plugin(
            'bsmu.vision.plugins.post_load_converters.registry.PostLoadConverterRegistryPlugin')\
            .post_load_converter_registry
        self.post_load_conversion_manager = PostLoadConversionManager(post_load_converter_registry)


class PostLoadConversionManager(QObject):
    data_converted = Signal(Data)

    def __init__(self, post_load_converter_registry: PostLoadConverterRegistry):
        super().__init__()

        self.post_load_converter_registry = post_load_converter_registry

    def can_convert_data(self, data: Data) -> bool:
        return self.post_load_converter_registry.contains(type(data))

    def convert_data(self, data: Data) -> Data:
        converted_data = data
        converter_cls = self.post_load_converter_registry.converter_cls(type(data))
        if converter_cls is not None:
            converter = converter_cls()
            converted_data = converter.convert_data(data)
            self.data_converted.emit(converted_data)
        return converted_data
