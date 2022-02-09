from __future__ import annotations

import collections.abc
import importlib
import re
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.plugins.observer import ObserverPlugin

if TYPE_CHECKING:
    from typing import List

    from bsmu.vision.app.base import App


class PluginManager(QObject):
    plugin_enabling = Signal(Plugin)
    plugin_enabled = Signal(Plugin)
    plugin_disabling = Signal(Plugin)
    plugin_disabled = Signal(Plugin)

    def __init__(self, app: App):
        super().__init__()

        self._app = app

        self._plugin_expression_pattern_str = \
            r'((?P<alias>.+)=)?(?P<full_name>[^->\(]+)(\((?P<args>.*)\))?\s*(->(?P<replace_full_name>.+))?'
        self._plugin_expression_pattern = re.compile(self._plugin_expression_pattern_str)

        self._created_plugin_by_full_name = {}  # { full_name: Plugin }
        self._enabled_plugin_by_full_name = {}  # { full_name: Plugin }
        self._created_plugin_by_alias = {}  # { alias: Plugin }

    @property
    def enabled_plugins(self) -> List[Plugin]:
        return list(self._enabled_plugin_by_full_name.values())

    def _enable_created_plugin(self, plugin: Plugin, replace_full_name: str = None):
        full_name = plugin.full_name()

        assert full_name in self._created_plugin_by_full_name, \
            f'Plugin {full_name} have to be created before enabling'

        if full_name in self._enabled_plugin_by_full_name:
            return

        plugin.enabling.connect(self._enable_dependency_plugins)
        plugin.enabling.connect(self.plugin_enabling)
        plugin.enabled.connect(self.plugin_enabled)
        plugin.disabling.connect(self.plugin_disabling)
        plugin.disabled.connect(self.plugin_disabled)

        self._setup_observer_plugin_connections(plugin)

        plugin.enable()
        self._enabled_plugin_by_full_name[full_name] = plugin
        if replace_full_name is not None:
            self._enabled_plugin_by_full_name[replace_full_name] = plugin

    def _create_plugin(
            self,
            full_name: str,
            args: List[str] | None = None,
            replace_full_name: str | None = None,
            alias: str | None = None,
    ) -> Plugin:
        if replace_full_name is not None:
            assert replace_full_name not in self._created_plugin_by_full_name, \
                'Create plugins with a replace property in the beginning before any other plugins, ' \
                'because the replaced plugin can be created as other plugin dependency ' \
                'and cannot be used after replacement'

        plugin = self._created_plugin_by_full_name.get(full_name)   #### or self._aliases_plugins.get(full_name)
        if plugin is None:
            module_name, class_name = full_name.rsplit(".", 1)
            plugin_class = getattr(importlib.import_module(module_name), class_name)

            dependency_plugin_by_key = {}
            for plugin_key, plugin_full_name in plugin_class.default_dependency_plugin_full_name_by_key.items():
                dependency_plugin_by_key[plugin_key] = self._create_plugin(plugin_full_name)

            plugins_as_args = [self._created_plugin_by_alias.get(arg) or arg for arg in args] \
                if args is not None else ()

            plugin = plugin_class(*plugins_as_args, **dependency_plugin_by_key)
            plugin.dependency_plugin_by_key = dependency_plugin_by_key

            self._created_plugin_by_full_name[plugin.full_name()] = plugin
            if replace_full_name is not None:
                self._created_plugin_by_full_name[replace_full_name] = plugin
            if alias is not None:
                self._created_plugin_by_alias[alias] = plugin

        return plugin

    def _create_and_enable_plugin_from_expression(self, plugin_expression: str) -> Plugin:
        plugin_expression = plugin_expression.replace(' ', '')

        match = self._plugin_expression_pattern.match(plugin_expression)
        alias = match.group('alias')
        full_name = match.group('full_name')
        args = match.group('args')
        replace_full_name = match.group('replace_full_name')

        plugin = self._enabled_plugin_by_full_name.get(full_name)
        if plugin is None:
            if replace_full_name is not None:
                replace_full_name = replace_full_name.replace(' ', '')

            if args is not None:
                args = [arg.replace(' ', '') for arg in args.split(',')]

            plugin = self._create_plugin(full_name, args, replace_full_name, alias)
            self._enable_created_plugin(plugin, replace_full_name)

        return plugin

    def _create_and_enable_plugin_from_mapping(self, plugin_mapping: collections.Mapping) -> Plugin:
        assert len(plugin_mapping) == 1, 'Mapping has to contain only one element: plugin and its properties'

        full_name, plugin_properties = next(iter(plugin_mapping.items()))
        assert plugin_properties is not None, \
            f'Plugin {full_name} is declared as Mapping ' \
            f'and has to contain properties after colon, but it has no declared properties. ' \
            f'Remove colon after plugin name or declare plugin properties.'

        plugin = self._enabled_plugin_by_full_name.get(full_name)
        if plugin is None:
            replace_full_name = plugin_properties.get('replace')
            alias = plugin_properties.get('alias')
            plugin = self._create_plugin(full_name, replace_full_name=replace_full_name, alias=alias)
            self._enable_created_plugin(plugin, replace_full_name)

        return plugin

    def enable_plugin(self, plugin: str | collections.Mapping | Plugin) -> Plugin:
        if isinstance(plugin, collections.abc.Mapping):
            return self._create_and_enable_plugin_from_mapping(plugin)

        if isinstance(plugin, Plugin):
            self._enable_created_plugin(plugin)
            return plugin

        return self._create_and_enable_plugin_from_expression(plugin)

    def enable_plugins(self, plugins: List[str | collections.Mapping | Plugin]):
        for plugin in plugins:
            self.enable_plugin(plugin)

    def enabled_plugin(self, full_name) -> Plugin | None:
        return self._enabled_plugin_by_full_name.get(full_name)

    def _enable_dependency_plugins(self, plugin: Plugin):
        for dependency_plugin in plugin.dependency_plugin_by_key.values():
            self._enable_created_plugin(dependency_plugin)

    def _setup_observer_plugin_connections(self, plugin: Plugin):
        if not isinstance(plugin, ObserverPlugin):
            return

        plugin.enabled.connect(self._on_observer_plugin_enabled)
        plugin.disabling.connect(self._on_observer_plugin_disabling)

    def _on_observer_plugin_enabled(self, observer_plugin: ObserverPlugin):
        for enabled_plugin in self._enabled_plugin_by_full_name.values():
            self._notify_observer_about_changed_plugin(
                observer_plugin, observer_plugin.on_observed_plugin_enabled, enabled_plugin)

        self.plugin_enabled.connect(partial(
            self._notify_observer_about_changed_plugin, observer_plugin, observer_plugin.on_observed_plugin_enabled))
        self.plugin_disabling.connect(partial(
            self._notify_observer_about_changed_plugin, observer_plugin, observer_plugin.on_observed_plugin_disabling))

    def _notify_observer_about_changed_plugin(
            self,
            observer_plugin: ObserverPlugin,
            observer_plugin_callback,
            changed_plugin: Plugin,
    ):
        if isinstance(changed_plugin, observer_plugin.observed_plugin_cls):
            observer_plugin_callback(changed_plugin)

    def _on_observer_plugin_disabling(self, observer_plugin: ObserverPlugin):
        # TODO: check, maybe to we cannot correctly use disconnect using 'partial'
        #  and have to store references to them during connect
        self.plugin_enabled.disconnect(partial(
            self._notify_observer_about_changed_plugin, observer_plugin, observer_plugin.on_observed_plugin_enabled))
        self.plugin_disabling.disconnect(partial(
            self._notify_observer_about_changed_plugin, observer_plugin, observer_plugin.on_observed_plugin_disabling))
