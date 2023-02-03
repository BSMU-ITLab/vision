from __future__ import annotations

from collections import defaultdict
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

        # Store list of processor classes for every key
        self._registry = defaultdict(list)

    def register_processor_cls(self, processor_cls: Type[Processor]):
        for processed_key in processor_cls.processed_keys:
            if processed_key in self._registry:
                print(f'Warning: the <{processed_key}> key already has processors: {self._registry[processed_key]}')
            self._registry[processed_key].append(processor_cls)

    def unregister_processor_cls(self, processor_cls: Type[Processor]):
        for processed_key in processor_cls.processed_keys:
            self._registry[processed_key].remove(processor_cls)
            # Remove empty list of processor classes
            if not self._registry[processed_key]:
                del self._registry[processed_key]

    def processor_cls(self, processed_key: Hashable) -> Type[Processor] | None:
        """
        :param processed_key: key to get the processor class
        :return: None or the first processor class the the |processed_key|
        """
        result = self.processor_classes(processed_key)
        return result and result[0]

    def processor_classes(self, processed_key: Hashable) -> list[Type[Processor]] | None:
        result = self._registry.get(processed_key)
        assert result != [], f'Empty list of processor classes for the <{processed_key}> key has to be deleted'
        return result

    def contains(self, processed_key: Hashable) -> bool:
        return processed_key in self._registry

    def clear(self):
        self._registry.clear()
