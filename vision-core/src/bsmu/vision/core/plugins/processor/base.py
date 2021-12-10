from __future__ import annotations

from typing import Type

from bsmu.vision.core.plugins.base import Plugin


class ProcessorPlugin(Plugin):
    def __init__(self, processor_cls: Type[Processor]):
        super().__init__()

        self._processor_cls = processor_cls

    @property
    def processor_cls(self) -> Type[Processor]:
        return self._processor_cls


class Processor:
    # processed_keys

    def process(self):
        ...
