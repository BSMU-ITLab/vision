from __future__ import annotations

from typing import Type, Optional

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.loaders.base import FileLoaderPlugin


class FileLoaderRegistryPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.file_loader_registry = FileLoaderRegistry()

    def _enable(self):
        for plugin in self.app.enabled_plugins():
            self._register_loader_plugin(plugin)

        self.app.plugin_enabled.connect(self._register_loader_plugin)
        self.app.plugin_disabled.connect(self._unregister_loader_plugin)

    def _disable(self):
        self.app.plugin_enabled.disconnect(self._register_loader_plugin)
        self.app.plugin_disabled.disconnect(self._unregister_loader_plugin)

        self.file_loader_registry.clear()

    def _register_loader_plugin(self, plugin: Plugin):
        if isinstance(plugin, FileLoaderPlugin):
            self.file_loader_registry.register_loader_cls(plugin.file_loader_cls)

    def _unregister_loader_plugin(self, plugin: Plugin):
        if isinstance(plugin, FileLoaderPlugin):
            self.file_loader_registry.unregister_loader_cls(plugin.file_loader_cls)


class FileLoaderRegistry:
    def __init__(self):
        super().__init__()

        self._registry = {}

    def register_loader_cls(self, loader_cls: Type[FileLoader]):
        for file_format in loader_cls.formats:
            assert file_format not in self._registry, 'Duplicate format of file loader'
            self._registry[file_format] = loader_cls

    def unregister_loader_cls(self, loader_cls: Type[FileLoader]):
        for file_format in loader_cls.formats:
            assert self._registry[file_format] == loader_cls, 'Format registered for other file loader'
            del self._registry[file_format]

    def loader_cls(self, file_format: str) -> Optional[Type[FileLoader]]:
        return self._registry.get(file_format)

    def contains(self, file_format: str) -> bool:
        return file_format in self._registry

    def clear(self):
        self._registry.clear()
