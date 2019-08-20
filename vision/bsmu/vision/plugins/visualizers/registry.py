from __future__ import annotations

from typing import Type, Optional

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin


class DataVisualizerRegistryPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.data_visualizer_registry = DataVisualizerRegistry()

    def _enable(self):
        for plugin in self.app.enabled_plugins():
            self._register_visualizer_plugin(plugin)

        self.app.plugin_enabled.connect(self._register_visualizer_plugin)
        self.app.plugin_disabled.connect(self._unregister_visualizer_plugin)

    def _disable(self):
        self.app.plugin_enabled.disconnect(self._register_visualizer_plugin)
        self.app.plugin_disabled.disconnect(self._unregister_visualizer_plugin)

        self.data_visualizer_registry.clear()

    def _register_visualizer_plugin(self, plugin: Plugin):
        if isinstance(plugin, DataVisualizerPlugin):
            self.data_visualizer_registry.register_visualizer_cls(plugin.data_visualizer_cls)

    def _unregister_visualizer_plugin(self, plugin: Plugin):
        if isinstance(plugin, DataVisualizerPlugin):
            self.data_visualizer_registry.unregister_visualizer_cls(plugin.data_visualizer_cls)


class DataVisualizerRegistry:
    def __init__(self):
        super().__init__()

        self._registry = {}

    def register_visualizer_cls(self, visualizer_cls: Type[DataVisualizer]):
        for data_type in visualizer_cls.data_types:
            assert data_type not in self._registry, 'Duplicate data type of visualizer'
            self._registry[data_type] = visualizer_cls

    def unregister_visualizer_cls(self, visualizer_cls: Type[DataVisualizer]):
        for data_type in visualizer_cls.data_types:
            assert self._registry[data_type] == visualizer_cls, 'Data type registered for other visualizer'
            del self._registry[data_type]

    def visualizer_cls(self, data_type: Type[Data]) -> Optional[Type[DataVisualizer]]:
        return self._registry.get(data_type)

    def contains(self, data_type: Type[Data]) -> bool:
        return data_type in self._registry

    def clear(self):
        self._registry.clear()
