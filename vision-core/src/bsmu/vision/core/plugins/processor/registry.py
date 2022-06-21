from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.core.plugins.observer import ObserverPlugin

if TYPE_CHECKING:
    from bsmu.vision.core.plugins.base import Plugin
    from bsmu.vision.core.plugins.processor.base import Processor
    from typing import Type, Hashable


class ProcessorRegistryPlugin(ObserverPlugin):
    def __init__(
            self,
            processor_registry_cls: Type[ProcessorRegistry],
            observed_plugin_cls: Type[Plugin],
    ):
        super().__init__(observed_plugin_cls)

        self._processor_registry_cls = processor_registry_cls
        self._processor_registry: ProcessorRegistry | None = None

    @property
    def processor_registry(self) -> ProcessorRegistry:
        return self._processor_registry

    def _enable(self):
        self._processor_registry = self._processor_registry_cls()

    def _disable(self):
        self._processor_registry = None

    def on_observed_plugin_enabled(self, plugin: Plugin):
        self._register_processor_plugin(plugin)

    def on_observed_plugin_disabling(self, plugin: Plugin):
        self._unregister_processor_plugin(plugin)

    def _register_processor_plugin(self, plugin: Plugin):
        self._processor_registry.register_processor_cls(plugin.processor_cls)

    def _unregister_processor_plugin(self, plugin: Plugin):
        self._processor_registry.unregister_processor_cls(plugin.processor_cls)


class ProcessorRegistry:
    def __init__(self):
        super().__init__()

        self._registry = {}

    def register_processor_cls(self, processor_cls: Type[Processor]):
        for processed_key in processor_cls.processed_keys:
            assert processed_key not in self._registry, f'Duplicate processed key: {processed_key}'
            self._registry[processed_key] = processor_cls

    def unregister_processor_cls(self, processor_cls: Type[Processor]):
        for processed_key in processor_cls.processed_keys:
            assert self._registry[processed_key] == processor_cls, \
                f'Processed key is registered for other processor {processed_key}'
            del self._registry[processed_key]

    def processor_cls(self, processed_key: Hashable) -> Type[Processor] | None:
        return self._registry.get(processed_key)

    def contains(self, processed_key: Hashable) -> bool:
        return processed_key in self._registry

    def clear(self):
        self._registry.clear()
