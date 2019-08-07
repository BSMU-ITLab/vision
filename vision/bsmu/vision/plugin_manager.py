import importlib


class PluginManager:
    def __init__(self):
        self.plugins = []

    def enable_plugin(self, plugin_full_name):
        plugin_module_name, plugin_class_name = plugin_full_name.rsplit(".", 1)
        plugin_class = getattr(importlib.import_module(plugin_module_name),
                               plugin_class_name)
        plugin = plugin_class()
        plugin.enable()
        self.plugins.append(plugin)

        # print('plugin_module', plugin_module_name)
        # print('class', plugin_class_name)
        # print('plugin', plugin)

    def enable_plugins(self, plugins):
        for plugin_full_name in plugins:
            self.enable_plugin(plugin_full_name)
