from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Type

from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from bsmu.vision.plugins.settings import SettingsPlugin
    from bsmu.vision.core.settings import Settings


class ProcessorPlugin(Plugin):
    def __init__(self, processor_cls: Type[Processor], processor_settings_plugin: SettingsPlugin = None):
        super().__init__()

        self._processor_cls = processor_cls
        self._processor_settings_plugin = processor_settings_plugin
        self._processor_settings: Settings | None = None

    def _enable(self):
        self._processor_settings = self._processor_settings_plugin and self._processor_settings_plugin.settings

    def _disable(self):
        self._processor_settings = None

    @property
    def processor_cls(self) -> Type[Processor]:
        return self._processor_cls

    @property
    def processor_settings(self) -> Settings:
        return self._processor_settings

    @property
    def processor_cls_with_settings(self) -> ProcessorClsWithSettings:
        return ProcessorClsWithSettings(self._processor_cls, self._processor_settings)


class Processor:
    # processed_keys

    def __init__(self, settings: Settings = None):
        self._settings = settings

    def process(self):
        ...


@dataclass
class ProcessorClsWithSettings:
    processor_cls: Type[Processor]
    processor_settings: Settings

    def processor(self) -> Processor:
        return self.processor_cls(self.processor_settings)
