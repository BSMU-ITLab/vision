from __future__ import annotations

from bsmu.vision.core.plugins.processor.registry import ProcessorRegistryPlugin, ProcessorRegistry
from bsmu.vision.plugins.post_load_converters.base import PostLoadConverterPlugin


class PostLoadConverterRegistryPlugin(ProcessorRegistryPlugin):
    def __init__(self):
        super().__init__(ProcessorRegistry, PostLoadConverterPlugin)
