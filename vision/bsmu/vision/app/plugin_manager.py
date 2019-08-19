from __future__ import annotations

import importlib
from functools import partial
from typing import List

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin


class PluginManager(QObject):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, app: App):
        super().__init__()

        self.app = app

        self.enabled_plugins = {}

    def enable_plugin(self, full_name: str):
        if full_name in self.enabled_plugins:
            return self.enabled_plugins[full_name]

        module_name, class_name = full_name.rsplit(".", 1)
        plugin_class = getattr(importlib.import_module(module_name), class_name)
        plugin = plugin_class(self.app)

        plugin.enabled.connect(self.plugin_enabled)
        plugin.disabled.connect(self.plugin_disabled)

        plugin.enable()
        self.enabled_plugins[full_name] = plugin
        # print('plugin_module', module_name)
        # print('class', class_name)
        # print('plugin', plugin)
        return plugin

    def enable_plugins(self, full_names: List[str]):
        for full_name in full_names:
            self.enable_plugin(full_name)

    def enabled_plugin(self, full_name):
        return self.enabled_plugins.get(full_name)
