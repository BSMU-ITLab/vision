from __future__ import annotations

from typing import Type, Optional

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.post_load_converters.base import PostLoadConverterPlugin


class PostLoadConverterRegistryPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.post_load_converter_registry = PostLoadConverterRegistry()

    def _enable(self):
        for plugin in self.app.enabled_plugins():
            self._register_post_load_converter_plugin(plugin)

        self.app.plugin_enabled.connect(self._register_post_load_converter_plugin)
        self.app.plugin_disabled.connect(self._unregister_post_load_converter_plugin)

    def _disable(self):
        self.app.plugin_enabled.disconnect(self._register_post_load_converter_plugin)
        self.app.plugin_disabled.disconnect(self._unregister_post_load_converter_plugin)

        self.post_load_converter_registry.clear()

    def _register_post_load_converter_plugin(self, plugin: Plugin):
        if isinstance(plugin, PostLoadConverterPlugin):
            self.post_load_converter_registry.register_post_load_converter_cls(plugin.post_load_converter_cls)

    def _unregister_post_load_converter_plugin(self, plugin: Plugin):
        if isinstance(plugin, PostLoadConverterPlugin):
            self.post_load_converter_registry.unregister_post_load_converter_cls(plugin.post_load_converter_cls)


class PostLoadConverterRegistry:
    def __init__(self):
        super().__init__()

        self._registry = {}

    def register_post_load_converter_cls(self, post_load_converter_cls: Type[PostLoadConverter]):
        for data_type in post_load_converter_cls.data_types:
            assert data_type not in self._registry, 'Duplicate data type of post load converter'
            self._registry[data_type] = post_load_converter_cls

    def unregister_post_load_converter_cls(self, post_load_converter_cls: Type[PostLoadConverter]):
        for data_type in post_load_converter_cls.data_types:
            assert self._registry[data_type] == post_load_converter_cls, 'Data type registered for other post load converter'
            del self._registry[data_type]

    def converter_cls(self, data_type: Type[Data]) -> Optional[Type[PostLoadConverter]]:
        return self._registry.get(data_type)

    def contains(self, data_type: Type[Data]) -> bool:
        return data_type in self._registry

    def clear(self):
        self._registry.clear()
