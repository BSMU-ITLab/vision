from __future__ import annotations

from bsmu.vision.core.plugins.processor.registry import ProcessorRegistryPlugin, ProcessorRegistry
from bsmu.vision.plugins.postread import PostReadConverterPlugin


class PostReadConverterRegistryPlugin(ProcessorRegistryPlugin):
    def __init__(self):
        super().__init__(ProcessorRegistry, PostReadConverterPlugin)
