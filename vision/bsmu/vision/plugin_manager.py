from __future__ import annotations

import importlib
from typing import List


class PluginManager:
    def __init__(self, app: App):
        self.app = app

        self.plugins = {}

    def enable_plugin(self, full_name: str):
        if full_name in self.plugins:
            return self.plugins[full_name]

        module_name, class_name = full_name.rsplit(".", 1)
        plugin_class = getattr(importlib.import_module(module_name), class_name)
        plugin = plugin_class(self.app)
        plugin.enable()
        self.plugins[full_name] = plugin
        # print('plugin_module', module_name)
        # print('class', class_name)
        # print('plugin', plugin)
        return plugin

    def enable_plugins(self, full_names: List[str]):
        for full_name in full_names:
            self.enable_plugin(full_name)

    def plugin(self, full_name):
        return self.plugins.get(full_name)
