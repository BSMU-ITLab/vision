from __future__ import annotations

from typing import Type

from bsmu.vision.core.plugins.base import Plugin


class ObserverPlugin(Plugin):
    def __init__(self, observed_plugin_class: Type[Plugin]):
        super().__init__()

        self._observed_plugin_cls = observed_plugin_class

    @property
    def observed_plugin_cls(self) -> Type[Plugin]:
        return self._observed_plugin_cls

    def on_observed_plugin_enabled(self, plugin: Plugin):
        ...

    def on_observed_plugin_disabling(self, plugin: Plugin):
        ...
