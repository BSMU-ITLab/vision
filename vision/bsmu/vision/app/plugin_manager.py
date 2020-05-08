from __future__ import annotations

import importlib
from functools import partial
from typing import List
import re

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin


class PluginManager(QObject):
    plugin_enabled = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, app: App):
        super().__init__()

        self.app = app

        self._plugin_expression_pattern_str = r'((?P<name>.+)=)?(?P<full_name>[^=\(]+)(\((?P<params>.*)\))?'
        self._plugin_expression_pattern = re.compile(self._plugin_expression_pattern_str)

        self.enabled_plugins = {}
        self._names_plugins = {}

    def enable_plugin(self, plugin_expression: str):
        plugin_expression = plugin_expression.replace(' ', '')

        match = self._plugin_expression_pattern.match(plugin_expression)
        name = match.group('name')
        full_name = match.group('full_name')
        params = match.group('params')

        plugin = self.enabled_plugins.get(full_name)
        if plugin is None:
            module_name, class_name = full_name.rsplit(".", 1)
            plugin_class = getattr(importlib.import_module(module_name), class_name)

            if params is not None:
                params = params.split(',')

            plugin = plugin_class(self.app)

            plugin.enabled.connect(self.plugin_enabled)
            plugin.disabled.connect(self.plugin_disabled)

            plugin.enable()
            self.enabled_plugins[full_name] = plugin

            # print('plugin_module', module_name)
            # print('class', class_name)
            # print('plugin', plugin)

        if name is not None:
            self._names_plugins[name] = plugin

        return plugin

    def enable_plugins(self, plugin_expressions: List[str]):
        for plugin_expression in plugin_expressions:
            self.enable_plugin(plugin_expression)

    def enabled_plugin(self, full_name):
        return self.enabled_plugins.get(full_name)
